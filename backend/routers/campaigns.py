import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import supabase
from backend.dependencies import get_current_user, get_owned_campaign
from backend.models.campaign import (
    CreateCampaignRequest,
    UpdateCampaignRequest,
    CampaignResponse,
)
from backend.models.common import ResponseEnvelope, PaginatedEnvelope

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
    try:
        response = (
            supabase.table("campaigns")
            .update({"status": "paused"})
            .eq("id", campaign["id"])
            .eq("user_id", user["id"])
            .execute()
        )
        return ResponseEnvelope(
            data=CampaignResponse(**response.data[0]),
            message="Campaign paused successfully",
        )
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
    try:
        response = (
            supabase.table("campaigns")
            .update({"status": "active"})
            .eq("id", campaign["id"])
            .eq("user_id", user["id"])
            .execute()
        )
        return ResponseEnvelope(
            data=CampaignResponse(**response.data[0]),
            message="Campaign resumed successfully",
        )
    except Exception as exc:
        logger.error(f"Error resuming campaign {campaign['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to resume campaign",
        ) from exc
