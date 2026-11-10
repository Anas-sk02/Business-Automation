"""Notifications router and helper service for SignalForge AI."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.database import get_supabase_client
from backend.dependencies import get_current_user
from backend.models.common import ResponseEnvelope
from backend.models.notification import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
    NotificationType,
)

logger = logging.getLogger("signalforge.notifications")

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def create_notification(
    db: Any,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    link_url: Optional[str] = None,
    lead_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Helper function to insert a notification into the database safely."""
    if not user_id or str(user_id).strip() in ("", "None"):
        return None

    try:
        valid_types = {t.value for t in NotificationType}
        safe_type = notification_type if notification_type in valid_types else "info"

        payload = {
            "user_id": str(user_id),
            "title": title[:200],
            "message": message[:1000],
            "type": safe_type,
            "link_url": link_url,
            "lead_id": str(lead_id) if lead_id else None,
            "campaign_id": str(campaign_id) if campaign_id else None,
            "is_read": False,
        }
        res = db.table("notifications").insert(payload).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as exc:
        logger.warning(f"Failed to create notification for user {user_id}: {exc}")
        return None


@router.get("", response_model=ResponseEnvelope[NotificationListResponse])
async def list_notifications(
    unread_only: bool = Query(default=False, description="Filter for unread notifications only"),
    limit: int = Query(default=20, ge=1, le=100, description="Max notifications to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch notifications for the authenticated user, ordered newest first."""
    db = get_supabase_client()
    user_id = current_user["id"]

    try:
        # Base query for user's notifications
        query = db.table("notifications").select("*").eq("user_id", user_id)
        if unread_only:
            query = query.eq("is_read", False)

        query = query.order("created_at", desc=True).limit(limit)
        res = query.execute()
        rows = res.data or []

        # Calculate total unread count
        unread_res = (
            db.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        unread_count = len(unread_res.data or [])

        notifications = [NotificationResponse.model_validate(r) for r in rows]

        return {
            "data": NotificationListResponse(
                notifications=notifications,
                unread_count=unread_count,
                total=len(notifications),
            ),
            "message": "Notifications retrieved successfully",
        }
    except Exception as exc:
        logger.error(f"Error fetching notifications for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications",
        )


@router.put("/read-all", response_model=ResponseEnvelope[MarkReadResponse])
async def mark_all_notifications_read(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark all unread notifications for the user as read."""
    db = get_supabase_client()
    user_id = current_user["id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # Find unread
        unread_res = (
            db.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        unread_ids = [r["id"] for r in (unread_res.data or [])]

        if unread_ids:
            db.table("notifications").update({
                "is_read": True,
                "read_at": now_iso,
            }).in_("id", unread_ids).execute()

        return {
            "data": MarkReadResponse(success=True, marked_count=len(unread_ids)),
            "message": f"Marked {len(unread_ids)} notifications as read",
        }
    except Exception as exc:
        logger.error(f"Error marking all notifications read for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read",
        )


@router.put("/{notification_id}/read", response_model=ResponseEnvelope[NotificationResponse])
async def mark_notification_read(
    notification_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark a single notification as read."""
    db = get_supabase_client()
    user_id = current_user["id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        existing = (
            db.table("notifications")
            .select("*")
            .eq("id", str(notification_id))
            .eq("user_id", user_id)
            .execute()
        )
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )

        updated = (
            db.table("notifications")
            .update({
                "is_read": True,
                "read_at": now_iso,
            })
            .eq("id", str(notification_id))
            .eq("user_id", user_id)
            .execute()
        )

        item = updated.data[0] if updated.data else existing.data[0]
        return {
            "data": NotificationResponse.model_validate(item),
            "message": "Notification marked as read",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error updating notification {notification_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification",
        )

