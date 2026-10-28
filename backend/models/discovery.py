"""Pydantic models for business discovery operations."""

from typing import Optional
from pydantic import BaseModel


class StartDiscoveryResponse(BaseModel):
    """Response payload when discovery background job is initiated."""
    campaign_id: str
    status: str = "discovering"
    queries_total: int = 0
    target_leads: int = 50
    estimated_duration_seconds: int = 15
    message: Optional[str] = None


class DiscoveryStatusResponse(BaseModel):
    """Progress and metrics response for campaign discovery."""
    campaign_id: str
    status: str
    discovery_queries_total: int = 0
    discovery_queries_completed: int = 0
    total_leads_found: int = 0
    target_leads: int = 50
    spent_amount: float = 0.0
    max_budget: float = 0.0
    is_near_budget: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

