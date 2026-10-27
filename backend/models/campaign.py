from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CampaignStatus(str, Enum):
    """Campaign status lifecycle states matching database CHECK constraint."""
    DRAFT = "draft"
    DISCOVERING = "discovering"
    DISCOVERY_COMPLETE = "discovery_complete"
    AUDITING = "auditing"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class WhatsAppSettings(BaseModel):
    """WhatsApp campaign configuration matching database schema defaults."""
    auto_send_after_approval: bool = False
    followup_gap_days: int = Field(default=3, ge=1, le=30)
    max_followups: int = Field(default=3, ge=0, le=5)
    quiet_hours_start: str = Field(
        default="21:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Start of quiet hours in HH:MM 24h format",
    )
    quiet_hours_end: str = Field(
        default="09:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="End of quiet hours in HH:MM 24h format",
    )


class CreateCampaignRequest(BaseModel):
    """Campaign creation payload with validation."""
    name: str = Field(min_length=1, max_length=200, description="Campaign name")
    industry: str = Field(min_length=1, max_length=100, description="Industry identifier e.g. coaching_institutes")
    industry_label: str = Field(min_length=1, max_length=100, description="Human-readable industry label")
    location: str = Field(min_length=1, max_length=200, description="Target city/location")
    keywords: List[str] = Field(default_factory=list, description="Search keywords")
    target_leads: int = Field(default=50, ge=1, le=500, description="Target lead count (1-500)")
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Minimum Google rating filter")
    service_offered: str = Field(min_length=1, max_length=200, description="Service offered by user")
    signals: List[str] = Field(default_factory=list, description="Opportunity signals to investigate")
    whatsapp_settings: WhatsAppSettings = Field(default_factory=WhatsAppSettings)
    max_budget: float = Field(default=0.0, ge=0.0, description="Max budget in USD (0 = unlimited per decisions.md)")


class UpdateCampaignRequest(BaseModel):
    """Campaign update payload (partial update). Settings only; lifecycle state changes use dedicated endpoints."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry: Optional[str] = Field(default=None, min_length=1, max_length=100)
    industry_label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location: Optional[str] = Field(default=None, min_length=1, max_length=200)
    keywords: Optional[List[str]] = None
    target_leads: Optional[int] = Field(default=None, ge=1, le=500)
    min_rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    service_offered: Optional[str] = Field(default=None, min_length=1, max_length=200)
    signals: Optional[List[str]] = None
    whatsapp_settings: Optional[WhatsAppSettings] = None
    max_budget: Optional[float] = Field(default=None, ge=0.0)


class CampaignResponse(BaseModel):
    """Full campaign response model matching public.campaigns table."""
    id: str
    user_id: str
    name: str
    industry: str
    industry_label: str
    location: str
    keywords: List[str] = Field(default_factory=list)
    target_leads: int = 50
    min_rating: float = 0.0
    service_offered: str
    signals: List[str] = Field(default_factory=list)
    whatsapp_settings: Dict[str, Any] = Field(default_factory=dict)
    max_budget: float = 0.0
    spent_amount: float = 0.0
    status: str = "draft"
    discovery_queries_total: int = 0
    discovery_queries_completed: int = 0
    total_leads_found: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
