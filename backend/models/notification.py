"""Pydantic schemas and models for Notification system."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    """Permitted notification types conforming to database schema check constraint."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ACTION_REQUIRED = "action_required"


class NotificationResponse(BaseModel):
    """Notification response schema for API consumption."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    message: str
    type: NotificationType
    link_url: Optional[str] = None
    lead_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    """List response with unread count envelope."""
    notifications: List[NotificationResponse]
    unread_count: int = 0
    total: int = 0


class MarkReadResponse(BaseModel):
    """Response after marking notification(s) as read."""
    success: bool = True
    marked_count: int = 1

