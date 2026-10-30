"""Unit tests for Stage 4 Task 5: Analysis Orchestration Service & Pipeline State Machine.

Validates:
- End-to-end orchestration of lead analysis pipeline
- Tenant isolation (user_id enforcement on leads and campaigns)
- Pre-flight campaign budget checks (spent_amount vs max_budget)
- AI structured response integration and prompt generation
- Claim verification integration against audit evidence
- Deterministic Lead Fit Scoring integration
- Database persistence to public.ai_analyses and public.leads
- Automatic pipeline state transitions:
    - fit_score >= 60 and valid phone -> 'qualified'
    - fit_score < 60 -> 'researched'
    - No valid phone -> 'researched' (qualification blocked)
    - Anti-regression guard: already contacted leads do not regress
- Batch campaign orchestration with concurrency and error aggregation
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.models.analysis import (
    AIAnalysisResult,
    AnalysisOpportunity,
)
from backend.services.ai_analysis import (
    AIAnalysisService,
    AnalysisExecutionError,
    CampaignBudgetExceededError,
    LeadNotFoundError,
)
from backend.services.ai_client import AIClient, AIResult


class MockQueryBuilder:
    """Mock chaining query builder simulating Supabase PostgREST queries."""

    def __init__(self, data: Optional[List[Dict[str, Any]]] = None):
        self.data = data if data is not None else []
        self.filter_conditions: Dict[str, Any] = {}
        self.inserted_payload: Optional[Dict[str, Any]] = None
        self.updated_payload: Optional[Dict[str, Any]] = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column: str, value: Any):
        self.filter_conditions[column] = value
        return self

    def in_(self, column: str, values: List[Any]):
        self.filter_conditions[column] = values
        return self

    def order(self, column: str, desc: bool = False):
        return self

    def limit(self, count: int):
        return self

    def insert(self, payload: Dict[str, Any]):
        self.inserted_payload = payload
        self.data = [payload]
        return self

    def update(self, payload: Dict[str, Any]):
        self.updated_payload = payload
        return self

    def execute(self):
        return self


class MockSupabaseClient:
    """Mock Supabase client providing isolated table state for tests."""

    def __init__(self):
        self.leads_data: List[Dict[str, Any]] = []
        self.campaigns_data: List[Dict[str, Any]] = []
        self.audits_data: List[Dict[str, Any]] = []
        self.evidence_data: List[Dict[str, Any]] = []
        self.analyses_data: List[Dict[str, Any]] = []
        self.lead_updates: List[Dict[str, Any]] = []

    def table(self, table_name: str) -> MockQueryBuilder:
        builder = MockQueryBuilder()

        if table_name == "leads":
            # For select queries on leads
            builder.data = self.leads_data

            def leads_execute():
                if builder.updated_payload:
                    self.lead_updates.append(builder.updated_payload)
                    for lead in self.leads_data:
                        if builder.filter_conditions.get("id") == lead.get("id"):
                            lead.update(builder.updated_payload)
                return builder

            builder.execute = leads_execute
            return builder

        elif table_name == "campaigns":
            builder.data = self.campaigns_data
            return builder

        elif table_name == "website_audits":
            builder.data = self.audits_data
            return builder

        elif table_name == "evidence_items":
            builder.data = self.evidence_data
            return builder

        elif table_name == "ai_analyses":
            def analyses_execute():
                if builder.inserted_payload:
                    saved = dict(builder.inserted_payload)
                    saved["id"] = "analysis-uuid-1234"
                    self.analyses_data.append(saved)
                    builder.data = [saved]
                return builder

            builder.execute = analyses_execute
            return builder

        return builder


@pytest.fixture
def sample_ai_result() -> AIAnalysisResult:
    return AIAnalysisResult(
        business_summary="Apex Plumbing is a reputable local commercial plumber in Bristol.",
        strengths=["Strong Google reviews", "Direct phone available"],
        opportunities=[
            AnalysisOpportunity(
                issue="Slow mobile load time",
                evidence="Lighthouse performance score is 42 and mobile load is 4.8s",
                impact="May result in lost inquiries from mobile visitors",
                recommendation="Optimize images and reduce script execution time",
            ),
            AnalysisOpportunity(
                issue="Missing SSL certificate",
                evidence="Site served over insecure HTTP without HTTPS redirect",
                impact="Could deter privacy-conscious clients and trigger browser warnings",
                recommendation="Install an automated Let's Encrypt SSL certificate",
            ),
        ],
        recommended_service="Mobile Speed & Security Optimization",
        pitch_angle="Help convert mobile visitors faster with SSL and speed fixes.",
        confidence="high",
    )


@pytest.fixture
def mock_ai_client(sample_ai_result) -> AIClient:
    client = MagicMock(spec=AIClient)
    client.model = "gemini-2.0-flash"
    client.generate_structured_output = AsyncMock(
        return_value=AIResult(
            parsed=sample_ai_result,
            raw_text="{}",
            input_tokens=450,
            output_tokens=180,
            cost_usd=0.0003,
            cost_inr=0.03,
            model_used="gemini-2.0-flash",
        )
    )
    return client


# ==============================================================================
# 1. State Machine & Qualification Tests
# ==============================================================================


@pytest.mark.anyio
async def test_qualifying_lead_transitions_to_qualified(mock_ai_client):
    """Lead with score >= 60 and valid phone must transition pipeline_stage to 'qualified'."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-qual-001"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Apex Plumbing",
            "category": "Plumber",
            "address": "10 Broadmead, Bristol",
            "phone": "+44 117 900 1234",
            "email": "info@apexplumbing.co.uk",
            "rating": 4.8,
            "website_url": "https://apexplumbing.co.uk",
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumbing", "plumber"],
                "max_budget": 500.0,
                "spent_amount": 10.0,
            },
        }
    ]
    db.audits_data = [
        {
            "id": "audit-001",
            "lead_id": lead_id,
            "performance_score": 42,
            "load_time_seconds": 4.8,
            "ssl_valid": False,
            "page_loads": True,
            "has_contact_form": True,
        }
    ]
    db.evidence_data = [
        {
            "id": "ev-001",
            "lead_id": lead_id,
            "finding_type": "lighthouse_speed",
            "title": "Slow mobile page load",
            "description": "Lighthouse performance score is 42 and mobile load is 4.8s",
            "severity": "high",
        },
        {
            "id": "ev-002",
            "lead_id": lead_id,
            "finding_type": "ssl_invalid",
            "title": "Insecure connection",
            "description": "Site served over insecure HTTP without HTTPS redirect",
            "severity": "critical",
        },
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    # Verification: Lead qualifies and transitions to 'qualified'
    assert res["pipeline_stage"] == "qualified"
    assert res["scoring"]["qualifies"] is True
    assert res["scoring"]["fit_score"] >= 60

    # Ensure public.ai_analyses received the record
    assert len(db.analyses_data) == 1
    saved_analysis = db.analyses_data[0]
    assert saved_analysis["lead_id"] == lead_id
    assert saved_analysis["model_used"] == "gemini-2.0-flash"
    assert saved_analysis["verified_claims"] > 0

    # Ensure public.leads was updated with score and qualified stage
    assert len(db.lead_updates) == 1
    update = db.lead_updates[0]
    assert update["pipeline_stage"] == "qualified"
    assert update["fit_score"] >= 60
    assert "score_breakdown" in update
    assert "score_reasons" in update


@pytest.mark.anyio
async def test_low_score_lead_transitions_to_researched(mock_ai_client):
    """Lead with score < 60 remains/becomes 'researched', never 'qualified'."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-low-002"
    campaign_id = "camp-001"

    # Lead that doesn't match campaign industry, location, or rating
    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Zen Yoga Studio",
            "category": "Yoga Studio",
            "address": "99 Ocean Blvd, Miami",
            "phone": "+1 305 555 1234",
            "email": "",
            "rating": 2.1,
            "website_url": "https://zenyoga.com",
            "pipeline_stage": "discovered",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumbing"],
                "max_budget": 500.0,
                "spent_amount": 10.0,
            },
        }
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    assert res["pipeline_stage"] == "researched"
    assert res["scoring"]["qualifies"] is False
    assert res["scoring"]["fit_score"] < 60

    assert len(db.lead_updates) == 1
    assert db.lead_updates[0]["pipeline_stage"] == "researched"


@pytest.mark.anyio
async def test_lead_without_phone_never_reaches_qualified(mock_ai_client):
    """Per decisions.md §6: No valid phone blocks qualification regardless of score."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-no-phone-003"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Bristol Central Plumbing",
            "category": "Plumber",
            "address": "15 High St, Bristol",
            "phone": None,  # No phone number
            "email": "contact@bristolplumbing.co.uk",
            "rating": 4.9,
            "website_url": "https://bristolplumbing.co.uk",
            "pipeline_stage": "discovered",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumbing"],
                "max_budget": 500.0,
                "spent_amount": 0.0,
            },
        }
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    # Even with high component scores (industry 20 + location 15 + rating 5 + contact 10 = 50+)
    # missing phone blocks qualifies flag
    assert res["scoring"]["has_valid_phone"] is False
    assert res["scoring"]["qualifies"] is False
    assert res["pipeline_stage"] == "researched"
    assert db.lead_updates[0]["pipeline_stage"] == "researched"


@pytest.mark.anyio
async def test_advanced_pipeline_stages_do_not_regress(mock_ai_client):
    """If a lead is already in 'contacted' or 'negotiation', analyzing does not regress the stage."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-contacted-004"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Apex Plumbing",
            "category": "Plumber",
            "address": "10 Broadmead, Bristol",
            "phone": "+44 117 900 1234",
            "rating": 4.8,
            "website_url": "https://apexplumbing.co.uk",
            "pipeline_stage": "contacted",  # Already contacted
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumbing"],
                "max_budget": 500.0,
                "spent_amount": 20.0,
            },
        }
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    # Must preserve 'contacted' stage
    assert res["pipeline_stage"] == "contacted"
    assert db.lead_updates[0]["pipeline_stage"] == "contacted"


# ==============================================================================
# 2. Security, Tenant Isolation & Safeguards
# ==============================================================================


@pytest.mark.anyio
async def test_unauthorized_user_access_rejected(mock_ai_client):
    """Attempting to analyze a lead belonging to another user raises LeadNotFoundError."""
    db = MockSupabaseClient()
    # No matching lead for user 'malicious-user'
    db.leads_data = []

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    with pytest.raises(LeadNotFoundError, match="not found or access denied"):
        await service.analyze_lead(lead_id="lead-other-999", user_id="malicious-user")


@pytest.mark.anyio
async def test_campaign_budget_exceeded_blocks_ai_call(mock_ai_client):
    """Per decisions.md §11: Before every paid AI call, stop when spent_amount exceeds max_budget."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-budget-005"
    campaign_id = "camp-budget-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Bristol Plumbing",
            "category": "Plumber",
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "max_budget": 100.0,
                "spent_amount": 100.0,  # Budget exhausted
            },
        }
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    with pytest.raises(CampaignBudgetExceededError, match="Campaign budget.*would be exceeded"):
        await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    # Ensure AIClient was never invoked
    mock_ai_client.generate_structured_output.assert_not_called()


@pytest.mark.anyio
async def test_ai_invocation_failure_raises_analysis_error(mock_ai_client):
    """If AI client generation fails (e.g. provider network error), service raises AnalysisExecutionError."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-fail-006"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Bristol Plumbing",
            "category": "Plumber",
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "max_budget": 500.0,
                "spent_amount": 0.0,
            },
        }
    ]

    mock_ai_client.generate_structured_output.side_effect = RuntimeError("AI provider timeout")
    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)

    with pytest.raises(AnalysisExecutionError, match="AI generation failed"):
        await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    # Verify no corrupted records were written
    assert len(db.analyses_data) == 0


# ==============================================================================
# 3. No-Website & Batch Processing Tests
# ==============================================================================


@pytest.mark.anyio
async def test_no_website_lead_analysis_handles_empty_audit(mock_ai_client):
    """Lead with no website earns 25 website points and succeeds cleanly."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-no-site-007"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Local Independent Builder",
            "category": "Building Contractor",
            "address": "42 High St, Bristol",
            "phone": "+44 117 999 4444",
            "email": None,
            "rating": 4.5,
            "website_url": None,  # No website
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Construction",
                "location": "Bristol",
                "keywords": ["builder", "construction", "contractor"],
                "max_budget": 500.0,
                "spent_amount": 0.0,
            },
        }
    ]
    # No audits or evidence records in DB
    db.audits_data = []
    db.evidence_data = []

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_lead(lead_id=lead_id, user_id=user_id)

    assert res["scoring"]["breakdown"]["website"] == 25
    assert res["pipeline_stage"] == "qualified"
    assert len(db.analyses_data) == 1


@pytest.mark.anyio
async def test_batch_campaign_leads_orchestration(mock_ai_client):
    """Batch analysis successfully iterates candidate leads and aggregates results."""
    db = MockSupabaseClient()
    user_id = "user-111"
    campaign_id = "camp-batch-100"

    db.campaigns_data = [
        {
            "id": campaign_id,
            "user_id": user_id,
            "max_budget": 500.0,
            "spent_amount": 0.0,
            "status": "discovery_complete",
        }
    ]

    leads = [
        {
            "id": f"lead-b-{i}",
            "campaign_id": campaign_id,
            "business_name": f"Business {i}",
            "category": "Plumber",
            "address": "Bristol",
            "phone": f"+44 117 900 000{i}",
            "rating": 4.8,
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumber"],
                "max_budget": 500.0,
                "spent_amount": 0.0,
            },
        }
        for i in range(3)
    ]
    db.leads_data = leads

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    summary = await service.analyze_campaign_leads(
        campaign_id=campaign_id,
        user_id=user_id,
    )

    assert summary["campaign_id"] == campaign_id
    assert summary["total_eligible"] == 3
    assert summary["processed"] == 3
    assert summary["failed"] == 0
    assert len(summary["errors"]) == 0


@pytest.mark.anyio
async def test_batch_campaign_leads_no_eligible_leads(mock_ai_client):
    """Batch analysis with no candidate leads returns 0 counts immediately."""
    db = MockSupabaseClient()
    user_id = "user-111"
    campaign_id = "camp-empty-200"

    db.campaigns_data = [
        {
            "id": campaign_id,
            "user_id": user_id,
            "max_budget": 500.0,
            "spent_amount": 0.0,
            "status": "discovery_complete",
        }
    ]
    db.leads_data = []

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    summary = await service.analyze_campaign_leads(
        campaign_id=campaign_id,
        user_id=user_id,
    )

    assert summary["total_eligible"] == 0
    assert summary["processed"] == 0
    assert summary["qualified"] == 0


@pytest.mark.anyio
async def test_analyze_lead_input_validation(mock_ai_client):
    """Empty lead_id or user_id must raise ValueError."""
    db = MockSupabaseClient()
    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)

    with pytest.raises(ValueError, match="lead_id is required"):
        await service.analyze_lead(lead_id="", user_id="user-123")

    with pytest.raises(ValueError, match="user_id is required"):
        await service.analyze_lead(lead_id="lead-123", user_id="   ")


@pytest.mark.anyio
async def test_batch_analysis_input_validation(mock_ai_client):
    """Empty campaign_id or user_id in batch analysis must raise ValueError."""
    db = MockSupabaseClient()
    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)

    with pytest.raises(ValueError, match="campaign_id is required"):
        await service.analyze_campaign_leads(campaign_id="", user_id="user-123")

    with pytest.raises(ValueError, match="user_id is required"):
        await service.analyze_campaign_leads(campaign_id="camp-123", user_id="")


@pytest.mark.anyio
async def test_batch_analysis_campaign_paused_exits_gracefully(mock_ai_client):
    """Per decisions.md §9: Paused campaign skips batch analysis without error."""
    db = MockSupabaseClient()
    user_id = "user-111"
    campaign_id = "camp-paused-300"

    db.campaigns_data = [
        {
            "id": campaign_id,
            "user_id": user_id,
            "max_budget": 500.0,
            "spent_amount": 0.0,
            "status": "paused",
        }
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_campaign_leads(campaign_id=campaign_id, user_id=user_id)

    assert res["total_eligible"] == 0
    assert res["processed"] == 0
    assert len(res["errors"]) == 1
    assert "Campaign is paused" in res["errors"][0]["error"]


@pytest.mark.anyio
async def test_batch_analysis_budget_exhaustion_aborts_subsequent_leads(mock_ai_client):
    """When budget is exceeded mid-batch, subsequent candidate leads are skipped."""
    db = MockSupabaseClient()
    user_id = "user-111"
    campaign_id = "camp-budget-abort-400"

    db.campaigns_data = [
        {
            "id": campaign_id,
            "user_id": user_id,
            "max_budget": 100.0,
            "spent_amount": 100.0,  # Exceeded
            "status": "active",
        }
    ]
    db.leads_data = [
        {
            "id": f"lead-ex-{i}",
            "campaign_id": campaign_id,
            "business_name": f"Business {i}",
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "max_budget": 100.0,
                "spent_amount": 100.0,
            },
        }
        for i in range(2)
    ]

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    res = await service.analyze_campaign_leads(campaign_id=campaign_id, user_id=user_id)

    assert res["processed"] == 0
    assert res["failed"] == 2
    assert any("Budget exceeded" in e["error"] for e in res["errors"])


@pytest.mark.anyio
async def test_analyze_lead_db_update_failure_raises_analysis_error(mock_ai_client):
    """If database update on leads fails, service raises AnalysisExecutionError."""
    db = MockSupabaseClient()
    user_id = "user-111"
    lead_id = "lead-err-update"
    campaign_id = "camp-001"

    db.leads_data = [
        {
            "id": lead_id,
            "campaign_id": campaign_id,
            "business_name": "Apex Plumbing",
            "category": "Plumber",
            "address": "10 Broadmead, Bristol",
            "phone": "+44 117 900 1234",
            "rating": 4.8,
            "pipeline_stage": "researched",
            "campaigns": {
                "id": campaign_id,
                "user_id": user_id,
                "industry": "Plumbing",
                "location": "Bristol",
                "keywords": ["plumber"],
                "max_budget": 500.0,
                "spent_amount": 0.0,
            },
        }
    ]

    # Force leads update to raise exception
    original_table = db.table
    def broken_table(name):
        builder = original_table(name)
        if name == "leads":
            def fail_exec():
                if builder.updated_payload:
                    raise RuntimeError("DB connection dropped")
                return builder
            builder.execute = fail_exec
        return builder

    db.table = broken_table

    service = AIAnalysisService(db_client=db, ai_client=mock_ai_client)
    with pytest.raises(AnalysisExecutionError, match="Failed to update lead status"):
        await service.analyze_lead(lead_id=lead_id, user_id=user_id)

