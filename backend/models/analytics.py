"""Pydantic models for Analytics, Conversion Funnel, Messaging Performance, and Costs.

Follows docs/decisions.md (Sections 4, 11) and docs/UI-UX.md (Section 6.11).
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FunnelStep(BaseModel):
    """Single stage in the 7-step acquisition funnel."""

    name: str = Field(..., description="Funnel step name (e.g. Found, Audited, Qualified, etc.)")
    count: int = Field(0, ge=0, description="Number of leads in this or downstream stages")
    conversion_rate: float = Field(
        0.0, ge=0.0, le=100.0, description="Conversion percentage from the immediate previous step"
    )
    overall_rate: float = Field(
        0.0, ge=0.0, le=100.0, description="Overall conversion percentage from the top of the funnel (Found)"
    )


class MessagingMetrics(BaseModel):
    """WhatsApp outreach delivery and engagement metrics."""

    total_sent: int = Field(0, ge=0, description="Outbound messages dispatched (sent/delivered/read/replied)")
    total_delivered: int = Field(0, ge=0, description="Messages confirmed delivered")
    total_read: int = Field(0, ge=0, description="Messages marked as read by recipient")
    total_replied: int = Field(0, ge=0, description="Leads that replied to outreach")
    total_failed: int = Field(0, ge=0, description="Messages that failed delivery")
    total_opted_out: int = Field(0, ge=0, description="Leads that requested opt-out/suppression")
    delivery_rate: float = Field(0.0, ge=0.0, le=100.0, description="Delivered / Sent percentage")
    read_rate: float = Field(0.0, ge=0.0, le=100.0, description="Read / Delivered percentage")
    reply_rate: float = Field(0.0, ge=0.0, le=100.0, description="Replied / Sent percentage")


class ServiceCostItem(BaseModel):
    """Spend metrics aggregated for an individual API service."""

    service: str = Field(..., description="Canonical service name (e.g. google_places, ai_analysis, etc.)")
    api_calls: int = Field(0, ge=0, description="Total API operations executed")
    cost_usd: float = Field(0.0, ge=0.0, description="Aggregated spend in USD")
    cost_inr: float = Field(0.0, ge=0.0, description="Aggregated spend in INR")


class CostBreakdown(BaseModel):
    """Service-level cost breakdown and unit economics."""

    services: List[ServiceCostItem] = Field(default_factory=list, description="Per-service cost breakdown")
    total_spend_usd: float = Field(0.0, ge=0.0, description="Total spend across all services in USD")
    total_spend_inr: float = Field(0.0, ge=0.0, description="Total spend across all services in INR")
    cost_per_qualified_lead_inr: Optional[float] = Field(
        None, ge=0.0, description="Total INR spent divided by qualified leads count"
    )
    cost_per_won_deal_inr: Optional[float] = Field(
        None, ge=0.0, description="Total INR spent divided by won deals count"
    )


class AnalyticsKPIs(BaseModel):
    """High-level summary KPI metrics for overview cards."""

    total_campaigns: int = Field(0, ge=0, description="Total campaigns owned by the user")
    total_leads_found: int = Field(0, ge=0, description="Total raw leads discovered across campaigns")
    total_audited: int = Field(0, ge=0, description="Total leads with completed website audits")
    total_qualified: int = Field(0, ge=0, description="Total leads that meet qualification threshold")
    total_messages_sent: int = Field(0, ge=0, description="Total WhatsApp messages sent")
    total_deals_won: int = Field(0, ge=0, description="Total leads in won pipeline stage")
    total_spend_usd: float = Field(0.0, ge=0.0, description="Total USD expenditure")
    total_spend_inr: float = Field(0.0, ge=0.0, description="Total INR expenditure")


class AnalyticsOverviewResponse(BaseModel):
    """Envelope for GET /api/analytics/overview."""

    has_sent_messages: bool = Field(
        ...,
        description="Whether the user has sent at least 1 message. Triggers UI-UX.md §6.11 banner when false."
    )
    kpis: AnalyticsKPIs
    funnel: List[FunnelStep]
    messaging: MessagingMetrics
    costs: CostBreakdown


class CampaignAnalyticsResponse(BaseModel):
    """Envelope for GET /api/analytics/campaign/{id}."""

    campaign_id: str
    campaign_name: str
    has_sent_messages: bool
    kpis: AnalyticsKPIs
    funnel: List[FunnelStep]
    messaging: MessagingMetrics
    costs: CostBreakdown


class CostsOverviewResponse(BaseModel):
    """Envelope for GET /api/analytics/costs per docs/api-reference.md and docs/UI-UX.md."""

    services: List[ServiceCostItem]
    total_spend_usd: float
    total_spend_inr: float
    total_businesses_processed: int
    cost_per_qualified_lead_inr: Optional[float] = None
    cost_per_won_deal_inr: Optional[float] = None
    cost_per_acquired_lead_inr: Optional[float] = Field(
        None, description="Alias for cost_per_won_deal_inr matching docs/api-reference.md"
    )

