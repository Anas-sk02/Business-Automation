"""Pydantic models for Pipeline and Kanban board stage transitions (Stage 6 Task 3)."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ManualPipelineStage(str, Enum):
    """Stages that users are allowed to move leads into manually per decisions.md §5."""
    MEETING_SCHEDULED = "meeting_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    WON = "won"
    CLOSED_LOST = "closed_lost"
    NOT_INTERESTED = "not_interested"


# Set of valid manual drop targets per decisions.md §5 and UI-UX.md §6.8
ALLOWED_MANUAL_STAGES = {stage.value for stage in ManualPipelineStage}

# Stages that must transition automatically via system events
AUTOMATED_STAGES = {
    "discovered",
    "research_pending",
    "researched",
    "qualified",
    "contacted",
    "followup_due",
    "replied",
}

# The 9 active working columns displayed on the Kanban board (UI-UX.md §6.8)
ACTIVE_PIPELINE_COLUMNS = [
    "qualified",
    "contacted",
    "followup_due",
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
]

# The closed rail stages (UI-UX.md §6.8)
CLOSED_RAIL_COLUMNS = [
    "not_interested",
    "no_response",
    "closed_lost",
    "opted_out",
]


class PipelineLeadCard(BaseModel):
    """Compact lead card representation on the Pipeline Kanban board."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    campaign_name: Optional[str] = None
    business_name: str
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website_url: Optional[str] = None
    fit_score: int = 0
    pipeline_stage: str
    rating: Optional[float] = None
    review_count: int = 0
    notes: Optional[str] = ""
    is_suppressed: bool = False
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PipelineBoardResponse(BaseModel):
    """Aggregated Kanban board response with working columns, closed rail, and counters."""
    columns: Dict[str, List[PipelineLeadCard]]
    closed: Dict[str, List[PipelineLeadCard]]
    stage_counts: Dict[str, int]
    total_active_leads: int
    total_leads: int


class UpdateLeadStageRequest(BaseModel):
    """Payload for manual lead pipeline stage transition."""
    stage: str = Field(
        ...,
        description="Target pipeline stage. Must be one of the permitted manual stages.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional notes detailing the deal or reason for transition.",
    )

