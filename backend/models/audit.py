"""Pydantic models for Stage 3: Website Audit and Evidence Items.

Conforms to public.website_audits and public.evidence_items tables in
supabase/migrations/001_initial_schema.sql and decisions.md Section 7.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

AuditStatus = Literal["pending", "running", "completed", "failed", "timeout"]
EvidenceType = Literal[
    "audit_check",
    "screenshot",
    "lighthouse_report",
    "link_check",
    "content_scan",
    "industry_check",
]
SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
VerificationStatus = Literal["verified", "unverified", "contradicted"]


class EvidenceItemResponse(BaseModel):
    """Pydantic model representing a single evidence finding item."""

    id: str
    lead_id: str
    audit_id: Optional[str] = None
    finding_title: str
    description: str
    evidence_type: EvidenceType = "audit_check"
    evidence_data: Dict[str, Any] = Field(default_factory=dict)
    severity: SeverityLevel = "medium"
    verification_status: VerificationStatus = "unverified"
    detected_at: datetime


class WebsiteAuditResponse(BaseModel):
    """Pydantic model representing a website audit record."""

    id: str
    lead_id: str
    tested_url: str
    dns_resolves: Optional[bool] = None
    http_status_code: Optional[int] = None
    ssl_valid: Optional[bool] = None
    page_loads: bool = False
    load_time_seconds: Optional[float] = None
    final_url: Optional[str] = None
    mobile_overflow: Optional[bool] = None
    mobile_overflow_pixels: int = 0
    has_contact_form: bool = False
    has_phone_on_site: bool = False
    has_email_on_site: bool = False
    has_whatsapp_link: bool = False
    has_social_links: bool = False
    social_links: List[Dict[str, Any]] = Field(default_factory=list)
    page_title: Optional[str] = None
    meta_description: Optional[str] = None
    h1_headings: List[str] = Field(default_factory=list)
    has_alt_texts: Optional[bool] = None
    missing_alt_count: int = 0
    total_internal_links: int = 0
    broken_links: List[Dict[str, Any]] = Field(default_factory=list)
    broken_link_count: int = 0
    lighthouse_performance: Optional[int] = None
    lighthouse_seo: Optional[int] = None
    lighthouse_accessibility: Optional[int] = None
    lighthouse_best_practices: Optional[int] = None
    screenshot_desktop_url: Optional[str] = None
    screenshot_mobile_url: Optional[str] = None
    industry_checks: Dict[str, Any] = Field(default_factory=dict)
    status: AuditStatus = "pending"
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class StartAuditResponse(BaseModel):
    """Response returned when initiating an audit job."""

    audit_id: Optional[str] = None
    lead_id: str
    status: str
    message: str


class FullAuditReportResponse(BaseModel):
    """Complete audit result payload with associated evidence items."""

    audit: Optional[WebsiteAuditResponse] = None
    evidence: List[EvidenceItemResponse] = Field(default_factory=list)
    signed_screenshot_desktop_url: Optional[str] = None
    signed_screenshot_mobile_url: Optional[str] = None

