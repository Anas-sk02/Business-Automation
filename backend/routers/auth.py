import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from backend.database import supabase
from backend.dependencies import get_current_user
from backend.models.auth import UserProfileResponse, UpdateProfileRequest
from backend.models.common import ResponseEnvelope

logger = logging.getLogger("signalforge.auth_router")
router = APIRouter()


@router.get("/me", response_model=ResponseEnvelope[UserProfileResponse])
async def get_current_profile(
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[UserProfileResponse]:
    """Retrieve the profile of the currently authenticated user."""
    try:
        response = (
            supabase.table("profiles")
            .select("*")
            .eq("id", user["id"])
            .execute()
        )

        if response.data and len(response.data) > 0:
            profile_record = response.data[0]
        else:
            # Fallback provisioning if profiles row wasn't populated yet
            new_profile = {
                "id": user["id"],
                "email": user["email"],
                "full_name": user.get("metadata", {}).get("full_name", ""),
            }
            create_resp = supabase.table("profiles").insert(new_profile).execute()
            profile_record = create_resp.data[0] if create_resp.data else new_profile

        return ResponseEnvelope(
            data=UserProfileResponse(**profile_record),
            message="User profile retrieved successfully",
        )
    except Exception as exc:
        logger.error(f"Failed to fetch profile for user {user.get('id')}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch user profile",
        ) from exc



@router.put("/profile", response_model=ResponseEnvelope[UserProfileResponse])
async def update_profile(
    request: UpdateProfileRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> ResponseEnvelope[UserProfileResponse]:
    """Update profile details for the authenticated user."""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No valid fields provided to update",
        )

    try:
        response = (
            supabase.table("profiles")
            .update(update_data)
            .eq("id", user["id"])
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found to update",
            )

        return ResponseEnvelope(
            data=UserProfileResponse(**response.data[0]),
            message="Profile updated successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update profile for user {user.get('id')}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update profile",
        ) from exc

