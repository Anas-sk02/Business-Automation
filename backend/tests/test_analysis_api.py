"""Integration tests for Stage 4 Task 6: Single & Batch Analysis API Endpoints.

Validates:
- POST /api/leads/{id}/analyze (202 Accepted, background job)
- GET /api/leads/{id}/analysis (200 OK with complete analysis model or null when unanalyzed)
- POST /api/campaigns/{id}/analyze (202 Accepted, batch analysis background job)
- Strict JWT authentication on all endpoints (401 Unauthorized)
- Strict user ownership validation on leads and campaigns (404 Not Found)
- Response envelope structure conformance: {"data": ..., "message": "..."}
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user


@pytest.fixture
def auth_user():
    return {"id": "user-uuid-123", "email": "test@signalforge.ai"}


@pytest.fixture
def client(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client


VALID_LEAD_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
VALID_CAMPAIGN_ID = "4fa85f64-5717-4562-b3fc-2c963f66afa7"


# ==============================================================================
# 1. Single Lead Analysis: POST /api/leads/{id}/analyze
# ==============================================================================


def test_start_lead_analysis_unauthorized(unauth_client):
    """Verify POST /api/leads/{id}/analyze rejects unauthenticated requests with 401."""
    response = unauth_client.post(f"/api/leads/{VALID_LEAD_ID}/analyze")
    assert response.status_code == 401


def test_start_lead_analysis_not_found(client):
    """Verify POST /api/leads/{id}/analyze returns 404 when lead is unowned or nonexistent."""
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        response = client.post(f"/api/leads/{VALID_LEAD_ID}/analyze")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_start_lead_analysis_success_202(client, auth_user):
    """Verify POST /api/leads/{id}/analyze enqueues background analysis and returns 202 Accepted."""
    lead_data = {
        "id": VALID_LEAD_ID,
        "campaign_id": VALID_CAMPAIGN_ID,
        "business_name": "Apex Dental",
        "website_url": "https://apexdental.in",
        "pipeline_stage": "researched",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.return_value = mock_leads_table
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.return_value = mock_leads_table
            with patch("backend.services.ai_analysis.AIAnalysisService.analyze_lead", new_callable=AsyncMock) as mock_analyze:
                response = client.post(f"/api/leads/{VALID_LEAD_ID}/analyze")

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["lead_id"] == VALID_LEAD_ID
    assert res_json["data"]["status"] == "accepted"
    assert "started in background" in res_json["data"]["message"]


# ==============================================================================
# 2. Get Lead Analysis: GET /api/leads/{id}/analysis
# ==============================================================================


def test_get_lead_analysis_unauthorized(unauth_client):
    """Verify GET /api/leads/{id}/analysis rejects unauthenticated requests with 401."""
    response = unauth_client.get(f"/api/leads/{VALID_LEAD_ID}/analysis")
    assert response.status_code == 401


def test_get_lead_analysis_not_found(client):
    """Verify GET /api/leads/{id}/analysis returns 404 when lead is unowned or nonexistent."""
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        response = client.get(f"/api/leads/{VALID_LEAD_ID}/analysis")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_get_lead_analysis_empty(client, auth_user):
    """Verify GET /api/leads/{id}/analysis returns 200 with data=None when unanalyzed."""
    lead_data = {
        "id": VALID_LEAD_ID,
        "campaign_id": VALID_CAMPAIGN_ID,
        "business_name": "Apex Dental",
        "pipeline_stage": "discovered",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_analyses_table = MagicMock()
    mock_analyses_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "ai_analyses":
            return mock_analyses_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.get(f"/api/leads/{VALID_LEAD_ID}/analysis")

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"] is None
    assert "No AI analysis" in res_json["message"]


def test_get_lead_analysis_success_200(client, auth_user):
    """Verify GET /api/leads/{id}/analysis returns full AI analysis model when present."""
    lead_data = {
        "id": VALID_LEAD_ID,
        "campaign_id": VALID_CAMPAIGN_ID,
        "business_name": "Apex Dental",
        "pipeline_stage": "qualified",
        "campaigns": {"user_id": auth_user["id"]},
    }

    analysis_data = {
        "id": "analysis-uuid-999",
        "lead_id": VALID_LEAD_ID,
        "model_used": "gemini-2.0-flash",
        "prompt_version": "v1",
        "analysis_result": {
            "business_summary": "Apex Dental is an established family dental clinic in Bristol.",
            "strengths": ["High Google rating", "Fast desktop load"],
            "opportunities": [
                {
                    "issue": "Slow mobile performance",
                    "evidence": "Lighthouse mobile score is 45",
                    "impact": "May increase visitor bounce rate",
                    "recommendation": "Compress images and bundle scripts",
                }
            ],
            "recommended_service": "Mobile Optimization",
            "pitch_angle": "Help turn mobile visitors into booked appointments.",
            "confidence": "high",
        },
        "recommended_service": "Mobile Optimization",
        "pitch_angle": "Help turn mobile visitors into booked appointments.",
        "confidence": "high",
        "claim_verifications": [
            {
                "claim": "Lighthouse mobile score is 45",
                "status": "verified",
                "evidence_id": "ev-1",
                "matched_finding": "Slow mobile speed",
            }
        ],
        "total_claims": 1,
        "verified_claims": 1,
        "unverified_claims": 0,
        "contradicted_claims": 0,
        "input_tokens": 400,
        "output_tokens": 150,
        "api_cost_usd": 0.0003,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_analyses_table = MagicMock()
    mock_analyses_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[analysis_data]
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "ai_analyses":
            return mock_analyses_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.get(f"/api/leads/{VALID_LEAD_ID}/analysis")

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"] is not None
    assert res_json["data"]["lead_id"] == VALID_LEAD_ID
    assert res_json["data"]["model_used"] == "gemini-2.0-flash"
    assert res_json["data"]["recommended_service"] == "Mobile Optimization"
    assert res_json["data"]["verified_claims"] == 1


# ==============================================================================
# 3. Batch Campaign Analysis: POST /api/campaigns/{id}/analyze
# ==============================================================================


def test_start_batch_campaign_analysis_unauthorized(unauth_client):
    """Verify POST /api/campaigns/{id}/analyze rejects unauthenticated requests with 401."""
    response = unauth_client.post(f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze")
    assert response.status_code == 401


def test_start_batch_campaign_analysis_not_found(client):
    """Verify POST /api/campaigns/{id}/analyze returns 404 when campaign is unowned or nonexistent."""
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        response = client.post(f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_start_batch_campaign_analysis_no_leads(client, auth_user):
    """Verify POST /api/campaigns/{id}/analyze returns 202 with 0 enqueued when no leads qualify."""
    camp_data = {
        "id": VALID_CAMPAIGN_ID,
        "user_id": auth_user["id"],
        "status": "discovery_complete",
    }

    mock_campaigns_table = MagicMock()
    mock_campaigns_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[camp_data]
    )

    mock_leads_table = MagicMock()
    # 0 candidate leads found
    mock_leads_table.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    def table_router(name):
        if name == "campaigns":
            return mock_campaigns_table
        if name == "leads":
            return mock_leads_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.campaigns.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.post(f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze")

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["total_eligible_leads"] == 0
    assert res_json["data"]["analyses_enqueued"] == 0
    assert "No eligible leads" in res_json["data"]["message"]


def test_start_batch_campaign_analysis_success_202(client, auth_user):
    """Verify POST /api/campaigns/{id}/analyze enqueues batch background job and returns 202."""
    camp_data = {
        "id": VALID_CAMPAIGN_ID,
        "user_id": auth_user["id"],
        "status": "discovery_complete",
    }

    candidate_leads = [{"id": f"lead-cand-{i}", "pipeline_stage": "researched"} for i in range(4)]

    mock_campaigns_table = MagicMock()
    mock_campaigns_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[camp_data]
    )

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=candidate_leads
    )

    def table_router(name):
        if name == "campaigns":
            return mock_campaigns_table
        if name == "leads":
            return mock_leads_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.campaigns.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            with patch("backend.services.ai_analysis.AIAnalysisService.analyze_campaign_leads", new_callable=AsyncMock) as mock_batch:
                response = client.post(
                    f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze",
                    json={"limit": 10},
                )

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["total_eligible_leads"] == 4
    assert res_json["data"]["analyses_enqueued"] == 4
    assert res_json["data"]["status"] == "accepted"


def test_start_batch_campaign_analysis_invalid_lead_ids(client, auth_user):
    """Verify POST /api/campaigns/{id}/analyze returns 422 if lead_ids contains non-UUID strings."""
    camp_data = {
        "id": VALID_CAMPAIGN_ID,
        "user_id": auth_user["id"],
        "status": "discovery_complete",
    }
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[camp_data]
        )
        response = client.post(
            f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze",
            json={"lead_ids": ["invalid-uuid-format"]},
        )
    assert response.status_code == 422


def test_start_batch_campaign_analysis_paused_campaign_returns_400(client, auth_user):
    """Verify POST /api/campaigns/{id}/analyze rejects requests on paused/stopped campaigns with 400."""
    camp_data = {
        "id": VALID_CAMPAIGN_ID,
        "user_id": auth_user["id"],
        "status": "paused",
    }
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[camp_data]
        )
        response = client.post(f"/api/campaigns/{VALID_CAMPAIGN_ID}/analyze")
    assert response.status_code == 400
    assert "cannot run ai analysis" in response.json()["detail"].lower()


def test_get_lead_analysis_db_error_returns_500(client, auth_user):
    """Verify GET /api/leads/{id}/analysis handles DB errors and returns 500 error envelope."""
    lead_data = {
        "id": VALID_LEAD_ID,
        "campaign_id": VALID_CAMPAIGN_ID,
        "pipeline_stage": "researched",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_analyses_table = MagicMock()
    mock_analyses_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = RuntimeError("DB connection failure")

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "ai_analyses":
            return mock_analyses_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.get(f"/api/leads/{VALID_LEAD_ID}/analysis")

    assert response.status_code == 500
    assert "failed to retrieve ai analysis" in response.json()["detail"].lower()


