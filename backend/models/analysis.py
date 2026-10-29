"""Pydantic models for Stage 4: AI Analysis, Claim Verification, and Scoring.

Conforms to public.ai_analyses in docs/database-schema.md and docs/prompts.md Section 1.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]
VerificationStatus = Literal["verified", "unverified", "contradicted"]


class AnalysisOpportunity(BaseModel):
    """A single digital or business opportunity detected from website audit and evidence."""

    issue: str = Field(..., description="Short title of the identified issue")
    evidence: str = Field(..., description="Specific measured evidence supporting this finding")
    impact: str = Field(..., description="Potential impact using cautious possibility wording (may, could)")
    recommendation: str = Field(..., description="Specific actionable recommendation addressing the issue")


class AIAnalysisResult(BaseModel):
    """Structured JSON output produced by the AI model during lead analysis."""

    business_summary: str = Field(
        ...,
        description="A 2-3 sentence summary of what the business does, strictly grounded in evidence",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Specific digital or operational strengths supported by evidence",
    )
    opportunities: List[AnalysisOpportunity] = Field(
        default_factory=list,
        description="List of identified opportunities backed by audit evidence",
    )
    recommended_service: str = Field(
        ...,
        description="The specific service from our offerings that best matches this business",
    )
    pitch_angle: str = Field(
        ...,
        description="A 1-2 sentence explanation of how our service addresses their needs",
    )
    confidence: ConfidenceLevel = Field(
        default="medium",
        description="Confidence level (high, medium, low) based on evidence verification",
    )


class ClaimVerificationItem(BaseModel):
    """Result of cross-verifying an AI opportunity or claim against stored evidence."""

    claim: str = Field(..., description="The factual claim made in the opportunity or message")
    status: VerificationStatus = Field(
        default="unverified",
        description="Verification outcome: verified, unverified, or contradicted",
    )
    evidence_id: Optional[str] = Field(
        default=None,
        description="UUID of the matching evidence_items record if found",
    )
    matched_finding: Optional[str] = Field(
        default=None,
        description="Title or description of the matching evidence finding",
    )


class VerificationResult(BaseModel):
    """Aggregate result from VerificationService.verify_claims()."""

    items: List[ClaimVerificationItem] = Field(default_factory=list)
    total_claims: int = Field(default=0, ge=0)
    verified_claims: int = Field(default=0, ge=0)
    unverified_claims: int = Field(default=0, ge=0)
    contradicted_claims: int = Field(default=0, ge=0)
    confidence: ConfidenceLevel = Field(default="medium")


class AIAnalysisResponse(BaseModel):
    """Full database representation of an AI analysis record."""

    model_config = {"protected_namespaces": ()}

    id: str
    lead_id: str
    model_used: str
    prompt_version: str = "v1"
    analysis_result: AIAnalysisResult
    recommended_service: Optional[str] = None
    pitch_angle: Optional[str] = None
    confidence: ConfidenceLevel = "medium"
    claim_verifications: List[ClaimVerificationItem] = Field(default_factory=list)
    total_claims: int = Field(default=0, ge=0)
    verified_claims: int = Field(default=0, ge=0)
    unverified_claims: int = Field(default=0, ge=0)
    contradicted_claims: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    api_cost_usd: float = Field(default=0.0, ge=0.0)
    analyzed_at: datetime


class StartAnalysisResponse(BaseModel):
    """Response returned when initiating an AI analysis job for a lead."""

    analysis_id: Optional[str] = None
    lead_id: str
    status: str
    message: str


class BatchAnalysisResponse(BaseModel):
    """Response returned when initiating batch AI analysis for a campaign."""

    campaign_id: str
    total_eligible_leads: int = Field(ge=0)
    analyses_enqueued: int = Field(ge=0)
    status: str
    message: str
