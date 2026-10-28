from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from backend.database import supabase
from backend.dependencies import get_current_user, get_owned_campaign
from backend.models.campaign import (
    CreateCampaignRequest,
    UpdateCampaignRequest,
    CampaignResponse,
)
from backend.models.discovery import (
    StartDiscoveryResponse,
    DiscoveryStatusResponse,
)
from backend.models.common import ResponseEnvelope, PaginatedEnvelope
from backend.services.discovery import DiscoveryService, get_user_semaphore

logger = logging.getLogger("signalforge.campaigns")
router = APIRouter()


@router.post("", response_model=ResponseEnvelope[CampaignResponse], status_code=201)
async def create_campaign(
    request: CreateCampaignRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[CampaignResponse]:
    """Create a new campaign scoped to the authenticated user."""
    payload = request.model_dump()
    payload["user_id"] = user["id"]
    payload["status"] = "draft"
    payload["whatsapp_settings"] = request.whatsapp_settings.model_dump()

    try:
        response = supabase.table("campaigns").insert(payload).execute()
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to create campaign record",
            )
        created_campaign = response.data[0]
        return ResponseEnvelope(
            data=CampaignResponse(**created_campaign),
            message="Campaign created successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating campaign for user {user['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the campaign",
        ) from exc


@router.get("", response_model=PaginatedEnvelope[CampaignResponse])
async def list_campaigns(
    user: Dict[str, Any] = Depends(get_current_user),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
) -> PaginatedEnvelope[CampaignResponse]:
    """List all campaigns belonging to the authenticated user with pagination."""
    try:
        query = (
            supabase.table("campaigns")
            .select("*", count="exact")
            .eq("user_id", user["id"])
        )

        if status:
            query = query.eq("status", status)

        start = (page - 1) * page_size
        end = start + page_size - 1

        response = query.order("created_at", desc=True).range(start, end).execute()
        total_count = response.count if response.count is not None else len(response.data or [])
        items = [CampaignResponse(**row) for row in (response.data or [])]

        return PaginatedEnvelope(
            data=items,
            total=total_count,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error(f"Error listing campaigns for user {user['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve campaigns",
        ) from exc


@router.get("/{id}", response_model=ResponseEnvelope[CampaignResponse])
async def get_campaign(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
) -> ResponseEnvelope[CampaignResponse]:
    """Get single campaign by ID (strictly owned by current user)."""
    return ResponseEnvelope(
        data=CampaignResponse(**campaign),
        message="Campaign retrieved successfully",
    )


@router.put("/{id}", response_model=ResponseEnvelope[CampaignResponse])
async def update_campaign(
    request: UpdateCampaignRequest,
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[CampaignResponse]:
    """Update campaign settings for owned campaign."""
    update_data = {
        k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None
    }
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No valid fields provided to update",
        )

    if "whatsapp_settings" in update_data and hasattr(request.whatsapp_settings, "model_dump"):
        update_data["whatsapp_settings"] = request.whatsapp_settings.model_dump()

    try:
        response = (
            supabase.table("campaigns")
            .update(update_data)
            .eq("id", campaign["id"])
            .eq("user_id", user["id"])
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Campaign not found to update",
            )
        return ResponseEnvelope(
            data=CampaignResponse(**response.data[0]),
            message="Campaign updated successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error updating campaign {campaign['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update campaign",
        ) from exc


@router.delete("/{id}", response_model=ResponseEnvelope[Dict[str, str]])
async def delete_campaign(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[Dict[str, str]]:
    """Delete a campaign and cascade its associated data."""
    try:
        supabase.table("campaigns").delete().eq("id", campaign["id"]).eq("user_id", user["id"]).execute()
        return ResponseEnvelope(
            data={"id": campaign["id"]},
            message="Campaign deleted successfully",
        )
    except Exception as exc:
        logger.error(f"Error deleting campaign {campaign['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete campaign",
        ) from exc


@router.post("/{id}/pause", response_model=ResponseEnvelope[CampaignResponse])
async def pause_campaign(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[CampaignResponse]:
    """Pause an active campaign."""
    current_status = campaign.get("status")
    if current_status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot pause a completed campaign",
        )
    if current_status == "draft":
        raise HTTPException(
            status_code=400,
            detail="Cannot pause a draft campaign",
        )

    try:
        response = (
            supabase.table("campaigns")
            .update({"status": "paused"})
            .eq("id", campaign["id"])
            .eq("user_id", user["id"])
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to pause campaign record",
            )
        return ResponseEnvelope(
            data=CampaignResponse(**response.data[0]),
            message="Campaign paused successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error pausing campaign {campaign['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to pause campaign",
        ) from exc


@router.post("/{id}/resume", response_model=ResponseEnvelope[CampaignResponse])
async def resume_campaign(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[CampaignResponse]:
    """Resume a paused campaign."""
    current_status = campaign.get("status")
    if current_status in ("draft", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume a campaign with status '{current_status}'",
        )

    try:
        response = (
            supabase.table("campaigns")
            .update({"status": "active"})
            .eq("id", campaign["id"])
            .eq("user_id", user["id"])
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to resume campaign record",
            )
        return ResponseEnvelope(
            data=CampaignResponse(**response.data[0]),
            message="Campaign resumed successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error resuming campaign {campaign['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to resume campaign",
        ) from exc


@router.post(
    "/{id}/start-discovery",
    response_model=ResponseEnvelope[StartDiscoveryResponse],
    status_code=202,
)
async def start_discovery(
    background_tasks: BackgroundTasks,
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[StartDiscoveryResponse]:
    """Initiate Google Places business discovery background job for an owned campaign."""
    campaign_id = campaign["id"]
    current_status = campaign.get("status")

    if current_status in ("discovering", "auditing"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start discovery while campaign is in '{current_status}' state",
        )
    if current_status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot run discovery on a completed campaign",
        )

    # Concurrency limit check: 1 discovery per user at a time (docs/decisions.md Section 9)
    # Check in-memory semaphore lock and active database jobs
    user_sem = await get_user_semaphore(user["id"])
    if user_sem.locked():
        raise HTTPException(
            status_code=400,
            detail="Another discovery job is currently in progress for this user. Only 1 concurrent discovery is allowed.",
        )

    try:
        active_discovering = (
            supabase.table("campaigns")
            .select("id")
            .eq("user_id", user["id"])
            .eq("status", "discovering")
            .execute()
        )
        if active_discovering.data:
            raise HTTPException(
                status_code=400,
                detail="Another discovery job is currently in progress for this user. Only 1 concurrent discovery is allowed.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error checking active discovery jobs for user {user['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate discovery job",
        ) from exc

    # Generate queries to establish total query count
    industry = campaign.get("industry_label") or campaign.get("industry", "")
    location = campaign.get("location", "")
    keywords = campaign.get("keywords") or []

    try:
        queries = DiscoveryService.generate_queries(industry, location, keywords)
    except Exception as exc:
        logger.error(f"Failed generating discovery queries for campaign {campaign_id}: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Unable to generate discovery queries: {exc}",
        ) from exc

    # Update DB state to discovering per decisions.md Section 9, resetting completed_at
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        update_res = (
            supabase.table("campaigns")
            .update({
                "status": "discovering",
                "discovery_queries_total": len(queries),
                "discovery_queries_completed": 0,
                "started_at": now_iso,
                "completed_at": None,
            })
            .eq("id", campaign_id)
            .eq("user_id", user["id"])
            .execute()
        )
        if not update_res.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update campaign discovery status",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error updating campaign {campaign_id} status to discovering: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to start discovery",
        ) from exc

    # Dispatch background worker
    discovery_service = DiscoveryService()
    background_tasks.add_task(
        discovery_service.run_discovery_job,
        campaign_id=campaign_id,
        user_id=user["id"],
        queries=queries,
    )

    estimated_duration = max(len(queries) * 2, 5)
    return ResponseEnvelope(
        data=StartDiscoveryResponse(
            campaign_id=campaign_id,
            status="discovering",
            queries_total=len(queries),
            target_leads=int(campaign.get("target_leads") or 50),
            estimated_duration_seconds=estimated_duration,
            message="Discovery task started in background",
        ),
        message="Discovery task accepted and running in background",
    )


@router.get(
    "/{id}/status",
    response_model=ResponseEnvelope[DiscoveryStatusResponse],
)
async def get_discovery_status(
    campaign: Dict[str, Any] = Depends(get_owned_campaign),
) -> ResponseEnvelope[DiscoveryStatusResponse]:
    """Retrieve discovery execution progress, metrics, and budget status."""
    is_near_budget = DiscoveryService.is_near_budget_limit(campaign)
    status_data = DiscoveryStatusResponse(
        campaign_id=campaign["id"],
        status=campaign.get("status", "draft"),
        discovery_queries_total=int(campaign.get("discovery_queries_total") or 0),
        discovery_queries_completed=int(campaign.get("discovery_queries_completed") or 0),
        total_leads_found=int(campaign.get("total_leads_found") or 0),
        target_leads=int(campaign.get("target_leads") or 50),
        spent_amount=float(campaign.get("spent_amount") or 0.0),
        max_budget=float(campaign.get("max_budget") or 0.0),
        is_near_budget=is_near_budget,
        started_at=campaign.get("started_at"),
        completed_at=campaign.get("completed_at"),
    )
    return ResponseEnvelope(
        data=status_data,
        message="Discovery status retrieved successfully",
    )

