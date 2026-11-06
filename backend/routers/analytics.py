"""Analytics API Router.

Endpoints for performance overview, campaign metrics, and cost tracking
per docs/decisions.md (Sections 4, 11), docs/api-reference.md (Section 6),
and docs/UI-UX.md (Section 6.11).
"""

from datetime import datetime
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.dependencies import get_analytics_service, get_current_user
from backend.services.analytics import AnalyticsService

logger = logging.getLogger("signalforge.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _validate_uuid_or_404(uuid_str: str, resource_name: str = "Campaign") -> None:
    """Validate UUID format, returning 404 if invalid per decisions.md Section 3."""
    if not uuid_str or not isinstance(uuid_str, str) or not uuid_str.strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} with ID '{uuid_str}' not found",
        )
    try:
        UUID(uuid_str.strip())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} with ID '{uuid_str}' not found",
        )


@router.get(
    "/overview",
    summary="Get Account Analytics Overview",
    description="Returns aggregate funnel, messaging metrics, and cost breakdown across all campaigns owned by the user.",
    status_code=status.HTTP_200_OK,
)
async def get_analytics_overview(
    from_date: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    user: Dict[str, Any] = Depends(get_current_user),
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Retrieve full analytics overview for the authenticated user."""
    try:
        data = await analytics_svc.get_overview_analytics(
            user_id=user["id"],
            from_date=from_date,
            to_date=to_date,
        )
        return {
            "data": data.model_dump(),
            "message": "Analytics overview retrieved successfully",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving analytics overview for user %s: %s", user.get("id"), exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics overview",
        )


@router.get(
    "/campaign/{id}",
    summary="Get Campaign Analytics",
    description="Returns funnel, outreach metrics, and cost breakdown for a specific owned campaign.",
    status_code=status.HTTP_200_OK,
)
async def get_campaign_analytics(
    id: str,
    from_date: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    user: Dict[str, Any] = Depends(get_current_user),
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Retrieve campaign-specific analytics metrics."""
    _validate_uuid_or_404(id, "Campaign")

    try:
        data = await analytics_svc.get_campaign_analytics(
            user_id=user["id"],
            campaign_id=id,
            from_date=from_date,
            to_date=to_date,
        )
        return {
            "data": data.model_dump(),
            "message": "Campaign analytics retrieved successfully",
        }
    except ValueError as exc:
        err_msg = str(exc)
        if "not found or unowned" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID '{id}' not found",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving campaign analytics for %s (user %s): %s", id, user.get("id"), exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign analytics",
        )


@router.get(
    "/costs",
    summary="Get Cost and Usage Metrics",
    description="Returns detailed spend per service and unit economics (cost per qualified lead / won deal).",
    status_code=status.HTTP_200_OK,
)
async def get_cost_analytics(
    campaign_id: Optional[str] = Query(default=None, description="Optional campaign ID filter"),
    from_date: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    user: Dict[str, Any] = Depends(get_current_user),
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Retrieve cost metrics breakdown."""
    if campaign_id is not None:
        campaign_id = campaign_id.strip()
        if not campaign_id:
            campaign_id = None
        else:
            _validate_uuid_or_404(campaign_id, "Campaign")

    try:
        data = await analytics_svc.get_cost_breakdown(
            user_id=user["id"],
            campaign_id=campaign_id,
            from_date=from_date,
            to_date=to_date,
        )
        return {
            "data": data.model_dump(),
            "message": "Cost analytics retrieved successfully",
        }
    except ValueError as exc:
        err_msg = str(exc)
        if "not found or unowned" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID '{campaign_id}' not found",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving cost analytics (user %s): %s", user.get("id"), exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cost analytics",
        )

