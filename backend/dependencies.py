import logging
import uuid
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends

from backend.database import supabase

logger = logging.getLogger("signalforge.auth")


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Validate Supabase JWT from Authorization header and return authenticated user details."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Empty Bearer token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = user_response.user
        return {
            "id": str(user.id),
            "email": user.email or "",
            "metadata": user.user_metadata or {},
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"JWT verification failed: {exc}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _validate_uuid(val: str, entity_name: str) -> None:
    """Validate UUID format; raises 404 if invalid to prevent Postgres syntax errors."""
    try:
        uuid.UUID(str(val))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=404,
            detail=f"{entity_name} with ID '{val}' not found",
        )


async def get_owned_campaign(
    campaign_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Verify campaign exists and belongs to the authenticated user.
    
    Per decisions.md Section 3: If unowned or nonexistent, return 404 (not 403).
    """
    _validate_uuid(campaign_id, "Campaign")

    try:
        response = (
            supabase.table("campaigns")
            .select("*")
            .eq("id", campaign_id)
            .eq("user_id", user["id"])
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"Campaign with ID '{campaign_id}' not found",
            )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error checking ownership for campaign {campaign_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=404,
            detail=f"Campaign with ID '{campaign_id}' not found",
        ) from exc


async def get_owned_lead(
    lead_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Verify lead exists and belongs to a campaign owned by the authenticated user.
    
    Per decisions.md Section 3: If unowned or nonexistent, return 404 (not 403).
    """
    _validate_uuid(lead_id, "Lead")

    try:
        response = (
            supabase.table("leads")
            .select("*, campaigns!inner(user_id)")
            .eq("id", lead_id)
            .eq("campaigns.user_id", user["id"])
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"Lead with ID '{lead_id}' not found",
            )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error checking ownership for lead {lead_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=404,
            detail=f"Lead with ID '{lead_id}' not found",
        ) from exc
