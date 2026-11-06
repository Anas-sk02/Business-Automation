"""Pydantic models for Settings and Suppression audit per docs/UI-UX.md Section 6.12."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SuppressionRecord(BaseModel):
    """Single opted-out or suppressed contact audit item."""

    id: str = Field(..., description="Unique lead ID")
    phone: str = Field(..., description="Suppressed phone number in E.164 format")
    business_name: Optional[str] = Field("", description="Associated business name")
    campaign_id: str = Field(..., description="Campaign ID where the contact originated")
    campaign_name: str = Field(..., description="Campaign name for context")
    suppression_reason: Optional[str] = Field(
        "Opted out", description="Reason for suppression (e.g. Requested STOP, Stop command, etc.)"
    )
    opted_out_at: str = Field(
        ..., description="ISO 8601 timestamp when suppression was recorded"
    )


class SuppressionListResponse(BaseModel):
    """Paginated envelope for GET /api/settings/suppression-list."""

    suppressed_contacts: List[SuppressionRecord] = Field(
        default_factory=list, description="List of suppressed contacts"
    )
    total: int = Field(0, ge=0, description="Total number of suppressed contacts")
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

