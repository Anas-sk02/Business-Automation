"""Settings and Suppression audit endpoints per docs/UI-UX.md Section 6.12."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.database import get_supabase_client
from backend.dependencies import get_current_user
from backend.models.settings import SuppressionListResponse, SuppressionRecord

logger = logging.getLogger("signalforge.settings")

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get(
    "/suppression-list",
    summary="Get Suppression Audit List",
    description="Returns read-only list of opted-out / suppressed phone numbers with dates and source campaigns.",
    status_code=status.HTTP_200_OK,
)
async def get_suppression_list(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, max_length=100, description="Optional search by phone, business name, or campaign"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve suppressed phone numbers for the authenticated tenant."""
    db = get_supabase_client()
    user_id = user["id"]

    try:
        # 1. Fetch campaigns owned by this user
        camp_res = db.table("campaigns").select("id, name").eq("user_id", user_id).execute()
        campaigns = camp_res.data or []
        if not campaigns:
            return {
                "data": SuppressionListResponse(
                    suppressed_contacts=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                ).model_dump(),
                "message": "Suppression list retrieved successfully",
            }

        campaign_map = {c["id"]: c.get("name", "Unnamed Campaign") for c in campaigns}
        campaign_ids = list(campaign_map.keys())

        # 2. Query leads for those campaigns that are suppressed or in opted_out stage
        leads_res = (
            db.table("leads")
            .select("id, phone, business_name, campaign_id, is_suppressed, suppression_reason, pipeline_stage, updated_at, created_at")
            .in_("campaign_id", campaign_ids)
            .execute()
        )
        all_leads = leads_res.data or []

        # Filter strictly for suppressed or opted-out leads
        suppressed_leads: List[Dict[str, Any]] = [
            l for l in all_leads
            if l.get("is_suppressed") is True or l.get("pipeline_stage") == "opted_out"
        ]

        # 3. Sort descending by updated_at / created_at (most recent opt-outs first)
        suppressed_leads.sort(
            key=lambda x: x.get("updated_at") or x.get("created_at") or "",
            reverse=True,
        )

        # 4. Deduplicate by normalized phone number (retaining most recent opt-out record)
        seen_phones = set()
        unique_suppressed: List[Dict[str, Any]] = []
        for l in suppressed_leads:
            phone_raw = (l.get("phone") or "").strip()
            if phone_raw:
                if phone_raw not in seen_phones:
                    seen_phones.add(phone_raw)
                    unique_suppressed.append(l)
            else:
                unique_suppressed.append(l)

        # 5. Apply optional search query
        if search:
            search_lower = search.strip().lower()
            if search_lower:
                unique_suppressed = [
                    l for l in unique_suppressed
                    if (
                        search_lower in (l.get("phone") or "").lower()
                        or search_lower in (l.get("business_name") or "").lower()
                        or search_lower in campaign_map.get(l.get("campaign_id", ""), "").lower()
                        or search_lower in (l.get("suppression_reason") or "").lower()
                    )
                ]

        total_count = len(unique_suppressed)

        # 6. Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_leads = unique_suppressed[start_idx:end_idx]

        records = [
            SuppressionRecord(
                id=l["id"],
                phone=l.get("phone") or "Not listed",
                business_name=l.get("business_name") or "",
                campaign_id=l["campaign_id"],
                campaign_name=campaign_map.get(l["campaign_id"], "Unknown Campaign"),
                suppression_reason=l.get("suppression_reason") or "Opted out",
                opted_out_at=l.get("updated_at") or l.get("created_at") or "",
            )
            for l in paginated_leads
        ]

        envelope = SuppressionListResponse(
            suppressed_contacts=records,
            total=total_count,
            page=page,
            page_size=page_size,
        )

        return {
            "data": envelope.model_dump(),
            "message": "Suppression list retrieved successfully",
        }
    except Exception as exc:
        logger.error("Failed to retrieve suppression list for user %s: %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve suppression list",
        ) from exc

