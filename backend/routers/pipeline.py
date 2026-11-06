"""Pipeline and Kanban board endpoints for sales stages and transitions (Stage 6 Task 3)."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.database import get_supabase_client
from backend.dependencies import get_current_user, get_owned_lead
from backend.models.pipeline import (
    ACTIVE_PIPELINE_COLUMNS,
    ALLOWED_MANUAL_STAGES,
    AUTOMATED_STAGES,
    CLOSED_RAIL_COLUMNS,
    PipelineBoardResponse,
    PipelineLeadCard,
    UpdateLeadStageRequest,
)
from backend.services.followup import FollowupService

logger = logging.getLogger("signalforge.pipeline")

router = APIRouter(tags=["pipeline"])


@router.get(
    "/pipeline",
    summary="Get Pipeline Kanban Board",
    description="Returns leads grouped into 9 active working columns + 4 closed rail stages scoped to user's campaigns.",
    status_code=status.HTTP_200_OK,
)
async def get_pipeline_board(
    campaign_id: Optional[str] = Query(
        default=None,
        description="Optional campaign ID to filter pipeline leads.",
    ),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve Kanban board structure for active and closed stages."""
    db = get_supabase_client()
    user_id = user["id"]

    # 1. Fetch campaigns belonging to this user
    try:
        camp_query = db.table("campaigns").select("id, name").eq("user_id", user_id)
        if campaign_id:
            campaign_id = campaign_id.strip()
            if campaign_id:
                try:
                    UUID(campaign_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Campaign with ID '{campaign_id}' not found",
                    )
                camp_query = camp_query.eq("id", campaign_id)
            else:
                campaign_id = None

        camp_res = camp_query.execute()
        campaigns = camp_res.data or []
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching campaigns for pipeline (user {user_id}): {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pipeline campaigns",
        ) from exc

    if campaign_id and not campaigns:
        # If user explicitly requested an unowned/non-existent campaign, return 404
        raise HTTPException(
            status_code=404,
            detail=f"Campaign with ID '{campaign_id}' not found",
        )

    # Empty pipeline if user has no campaigns
    if not campaigns:
        empty_columns = {col: [] for col in ACTIVE_PIPELINE_COLUMNS}
        empty_closed = {col: [] for col in CLOSED_RAIL_COLUMNS}
        return {
            "data": PipelineBoardResponse(
                columns=empty_columns,
                closed=empty_closed,
                stage_counts={},
                total_active_leads=0,
                total_leads=0,
            ).model_dump(mode="json"),
            "message": "Pipeline retrieved successfully",
        }

    campaign_map = {c["id"]: c["name"] for c in campaigns}
    allowed_camp_ids = list(campaign_map.keys())

    # 2. Query all leads belonging to user's campaigns
    try:
        leads_res = (
            db.table("leads")
            .select("*")
            .in_("campaign_id", allowed_camp_ids)
            .order("fit_score", desc=True)
            .execute()
        )
        raw_leads = leads_res.data or []
    except Exception as exc:
        logger.error(f"Error fetching leads for pipeline (user {user_id}): {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pipeline leads",
        ) from exc

    # 3. Categorize leads into columns and closed rail
    columns: Dict[str, List[PipelineLeadCard]] = {col: [] for col in ACTIVE_PIPELINE_COLUMNS}
    closed: Dict[str, List[PipelineLeadCard]] = {col: [] for col in CLOSED_RAIL_COLUMNS}
    stage_counts: Dict[str, int] = {}

    total_active = 0
    total_leads = len(raw_leads)

    for lead in raw_leads:
        stage = lead.get("pipeline_stage", "discovered")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

        c_name = campaign_map.get(lead.get("campaign_id"))
        card = PipelineLeadCard(
            id=lead["id"],
            campaign_id=lead["campaign_id"],
            campaign_name=c_name,
            business_name=lead.get("business_name") or "Unnamed Lead",
            category=lead.get("category"),
            address=lead.get("address"),
            phone=lead.get("phone"),
            website_url=lead.get("website_url"),
            fit_score=lead.get("fit_score") or 0,
            pipeline_stage=stage,
            rating=float(lead["rating"]) if lead.get("rating") is not None else None,
            review_count=int(lead.get("review_count") or 0),
            notes=lead.get("notes") or "",
            is_suppressed=bool(lead.get("is_suppressed")),
            last_contacted_at=lead.get("last_contacted_at"),
            next_followup_at=lead.get("next_followup_at"),
            created_at=lead.get("created_at"),
        )

        if stage in columns:
            columns[stage].append(card)
            total_active += 1
        elif stage in closed:
            closed[stage].append(card)

    return {
        "data": PipelineBoardResponse(
            columns=columns,
            closed=closed,
            stage_counts=stage_counts,
            total_active_leads=total_active,
            total_leads=total_leads,
        ).model_dump(mode="json"),
        "message": "Pipeline retrieved successfully",
    }


@router.put(
    "/leads/{id}/stage",
    summary="Update Lead Pipeline Stage",
    description="Manually move a lead to a permitted manual pipeline stage.",
    status_code=status.HTTP_200_OK,
)
async def update_lead_stage(
    id: str,
    payload: UpdateLeadStageRequest,
    lead: Dict[str, Any] = Depends(get_owned_lead),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Manually update the stage of an owned prospect lead."""
    db = get_supabase_client()
    target_stage = payload.stage
    current_stage = lead.get("pipeline_stage")

    # 1. Guard against moving opted-out leads per decisions.md §5 and UI-UX.md §6.8
    if current_stage == "opted_out" or lead.get("is_suppressed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opted-out leads cannot be moved.",
        )

    # 2. Validate target stage against manual stage permissions
    if target_stage not in ALLOWED_MANUAL_STAGES:
        if target_stage in AUTOMATED_STAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stage '{target_stage}' moves automatically based on system events and outreach actions, not manual moves.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid manual stage '{target_stage}'. Permitted stages are: {', '.join(sorted(ALLOWED_MANUAL_STAGES))}",
        )

    # 3. Automatic follow-up cancellation on manual transitions
    # If a lead is closed, won, or taken over manually, cancel automated cold outreach follow-ups
    try:
        followup_svc = FollowupService(db_client=db)
        await followup_svc.cancel_followups(
            lead_id=id,
            reason=f"manual_{target_stage}",
            campaign_id=lead.get("campaign_id"),
        )
    except Exception as exc:
        logger.warning(f"Notice: error cancelling follow-ups on lead {id} manual move: {exc}")

    # 4. Prepare update payload
    now_iso = datetime.now(timezone.utc).isoformat()
    update_data: Dict[str, Any] = {
        "pipeline_stage": target_stage,
        "updated_at": now_iso,
    }
    if payload.notes is not None:
        update_data["notes"] = payload.notes

    # 5. Execute database update
    try:
        upd_res = (
            db.table("leads")
            .update(update_data)
            .eq("id", id)
            .eq("campaign_id", lead["campaign_id"])
            .execute()
        )
        updated_record = upd_res.data[0] if upd_res.data else {**lead, **update_data}
    except Exception as exc:
        logger.error(f"Error updating stage for lead {id} to {target_stage}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update lead pipeline stage",
        ) from exc

    logger.info(f"User {user['id']} moved lead {id} from '{current_stage}' to '{target_stage}'")
    return {
        "data": updated_record,
        "message": f"Lead moved to {target_stage}",
    }

