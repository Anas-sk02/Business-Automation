"""Pydantic models for leads per database-schema.md and decisions.md Section 5."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    """Allowed pipeline stages matching database CHECK constraint (16 stages)."""
    DISCOVERED = "discovered"
    RESEARCH_PENDING = "research_pending"
    RESEARCHED = "researched"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    FOLLOWUP_DUE = "followup_due"
    REPLIED = "replied"
    INTERESTED = "interested"
    MEETING_SCHEDULED = "meeting_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    WON = "won"
    CLOSED_LOST = "closed_lost"
    NOT_INTERESTED = "not_interested"
    NO_RESPONSE = "no_response"
    OPTED_OUT = "opted_out"


class LeadResponse(BaseModel):
    """Lead record response model matching public.leads table."""
    id: str
    campaign_id: str
    place_id: Optional[str] = None
    business_name: str
    category: Optional[str] = ""
    subcategories: List[str] = Field(default_factory=list)
    address: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    postal_code: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    business_status: Optional[str] = "OPERATIONAL"
    opening_hours: Dict[str, Any] = Field(default_factory=dict)
    fit_score: int = 0
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    score_reasons: List[str] = Field(default_factory=list)
    pipeline_stage: str = "discovered"
    source: Optional[str] = "google_places"
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    notes: Optional[str] = ""
    is_suppressed: bool = False
    suppression_reason: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_contacted_at: Optional[str] = None
    next_followup_at: Optional[str] = None


class LeadDetailResponse(LeadResponse):
    """Full lead details response including associated audit, AI analysis, and evidence."""
    audit: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)

