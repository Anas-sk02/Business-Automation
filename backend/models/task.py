"""Pydantic schemas and models for Tasks management (Stage 6 Task 4)."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    """Permitted task types from database schema check constraint."""
    FOLLOWUP = "followup"
    CALLBACK = "callback"
    REVIEW_LEAD = "review_lead"
    REVIEW_REPLY = "review_reply"
    APPROVE_MESSAGE = "approve_message"
    SEND_INFO = "send_info"
    SEND_PRICING = "send_pricing"
    SCHEDULE_MEETING = "schedule_meeting"
    MEETING_FOLLOWUP = "meeting_followup"
    SEND_PROPOSAL = "send_proposal"
    GENERAL = "general"


class TaskStatus(str, Enum):
    """Permitted task statuses from database schema check constraint."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Permitted task priorities from database schema check constraint."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SnoozePreset(str, Enum):
    """Quick snooze presets matching UI-UX.md §6.9."""
    LATER_TODAY = "later_today"
    TOMORROW = "tomorrow"
    NEXT_WEEK = "next_week"


class TaskResponse(BaseModel):
    """Detailed task object enriched with lead and campaign names."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    user_id: str
    task_type: str
    title: str
    description: Optional[str] = ""
    status: str
    priority: str
    due_date: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateTaskRequest(BaseModel):
    """Payload for updating task status, priority, due date, or snooze timer."""
    status: Optional[str] = Field(
        default=None,
        description="Target status ('pending', 'in_progress', 'completed', 'snoozed', 'cancelled')",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Task priority ('urgent', 'high', 'medium', 'low')",
    )
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    snooze_preset: Optional[str] = Field(
        default=None,
        description="Snooze preset: 'later_today', 'tomorrow', or 'next_week'",
    )


class TaskGroupCounts(BaseModel):
    """Counts grouped by timeframe matching UI-UX.md §6.9."""
    overdue: int = 0
    today: int = 0
    upcoming: int = 0
    completed: int = 0
    total: int = 0


class TaskListResponse(BaseModel):
    """Enriched list of tasks with summary group counts."""
    tasks: List[TaskResponse]
    counts: TaskGroupCounts

