"""Tests for Leads Listing and Detail Endpoints (Stage 2, Task 4).

Verifies:
1. GET /api/campaigns/{id}/leads (pagination, sorting, filtering)
2. GET /api/leads/{id} (detailed lead view with audit, analysis, evidence)
3. Tenant isolation and ownership checks (unowned campaign/lead returns 404)
4. Authentication requirement (401 on missing token)
5. Validation of filter parameters
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_campaign, get_owned_lead

client = TestClient(app)

MOCK_USER_1 = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "user1@signalforge.ai",
}
MOCK_USER_2 = {
    "id": "22222222-2222-2222-2222-222222222222",
    "email": "user2@signalforge.ai",
}

SAMPLE_CAMPAIGN_ID = "33333333-3333-3333-3333-333333333333"
SAMPLE_LEAD_ID = "44444444-4444-4444-4444-444444444444"

SAMPLE_LEAD_ROW = {
    "id": SAMPLE_LEAD_ID,
    "campaign_id": SAMPLE_CAMPAIGN_ID,
    "place_id": "places/ChIJ111",
    "business_name": "Apex IIT Coaching",
    "category": "educational_institution",
    "subcategories": ["coaching_center", "school"],
    "address": "123 Ramdas Peth, Nagpur",
    "city": "Nagpur",
    "state": "Maharashtra",
    "postal_code": "440010",
    "latitude": 21.1458,
    "longitude": 79.0882,
    "phone": "+917122541234",
    "email": "info@apexiit.com",
    "website_url": "https://apexiit.com",
    "rating": 4.6,
    "review_count": 84,
    "business_status": "OPERATIONAL",
    "opening_hours": {},
    "fit_score": 85,
    "score_breakdown": {"industry": 20, "location": 15, "website": 25, "phone": 10, "rating": 5},
    "score_reasons": ["Industry match", "Location match"],
    "pipeline_stage": "discovered",
    "source": "google_places",
    "is_duplicate": False,
    "duplicate_of": None,
    "notes": "",
    "is_suppressed": False,
    "suppression_reason": None,
    "created_at": "2026-10-28T10:00:00Z",
    "updated_at": "2026-10-28T10:00:00Z",
    "last_contacted_at": None,
    "next_followup_at": None,
}

SAMPLE_CAMPAIGN_ROW = {
    "id": SAMPLE_CAMPAIGN_ID,
    "user_id": MOCK_USER_1["id"],
    "name": "Nagpur Coaching Campaign",
}


@pytest.fixture(autouse=True)
def clean_overrides():
    """Clear dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


# =========================================================================
# 1. Authentication and Authorization Tests
# =========================================================================

def test_leads_endpoints_require_auth():
    """Verify listing and detail endpoints reject unauthenticated requests with 401."""
    assert client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads").status_code == 401
    assert client.get(f"/api/leads/{SAMPLE_LEAD_ID}").status_code == 401


def test_list_leads_unowned_campaign_returns_404():
    """Per decisions.md Section 3: Accessing unowned campaign leads returns 404 (not 403)."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_2

    with patch("backend.dependencies.supabase") as mock_sb:
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_query

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads")
        assert resp.status_code == 404
        assert resp.json()["detail"] == f"Campaign with ID '{SAMPLE_CAMPAIGN_ID}' not found"


def test_get_lead_detail_unowned_lead_returns_404():
    """Per decisions.md Section 3: Accessing unowned lead returns 404 (not 403)."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_2

    with patch("backend.dependencies.supabase") as mock_sb:
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_query

        resp = client.get(f"/api/leads/{SAMPLE_LEAD_ID}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == f"Lead with ID '{SAMPLE_LEAD_ID}' not found"


# =========================================================================
# 2. List Leads Endpoint Tests (GET /api/campaigns/{id}/leads)
# =========================================================================

def test_list_campaign_leads_success():
    """Verify paginated leads list returned with envelope structure."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.return_value = query_chain
        query_chain.eq.return_value = query_chain
        query_chain.order.return_value = query_chain
        query_chain.range.return_value = query_chain
        query_chain.execute.return_value = MagicMock(data=[SAMPLE_LEAD_ROW], count=1)
        mock_sb.table.return_value = query_chain

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads?page=1&page_size=20")
        assert resp.status_code == 200
        body = resp.json()

        assert body["total"] == 1
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == SAMPLE_LEAD_ID
        assert body["data"][0]["business_name"] == "Apex IIT Coaching"
        assert body["data"][0]["fit_score"] == 85


def test_list_campaign_leads_filtering_options():
    """Verify score, stage, website, and phone filters are applied to query."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.return_value = query_chain
        query_chain.eq.return_value = query_chain
        query_chain.gte.return_value = query_chain
        query_chain.lte.return_value = query_chain
        query_chain.not_.is_.return_value = query_chain
        query_chain.neq.return_value = query_chain
        query_chain.or_.return_value = query_chain
        query_chain.order.return_value = query_chain
        query_chain.range.return_value = query_chain
        query_chain.execute.return_value = MagicMock(data=[SAMPLE_LEAD_ROW], count=1)
        mock_sb.table.return_value = query_chain

        url = (
            f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads"
            "?min_score=60&max_score=90&stage=discovered&has_website=true&has_phone=true"
            "&sort_by=fit_score&sort_order=desc"
        )
        resp = client.get(url)
        assert resp.status_code == 200

        # Assert query methods were called with filter arguments
        query_chain.gte.assert_called_with("fit_score", 60)
        query_chain.lte.assert_called_with("fit_score", 90)
        query_chain.eq.assert_any_call("pipeline_stage", "discovered")
        query_chain.order.assert_called_with("fit_score", desc=True)


def test_list_campaign_leads_rejects_invalid_score_range():
    """Verify min_score > max_score is rejected with 400 Bad Request."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads?min_score=90&max_score=60")
    assert resp.status_code == 400
    assert "min_score cannot be greater than max_score" in resp.json()["detail"]


def test_list_campaign_leads_has_website_false_filter():
    """Verify has_website=false filters for leads without website using IS NULL."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.return_value = query_chain
        query_chain.eq.return_value = query_chain
        query_chain.is_.return_value = query_chain
        query_chain.order.return_value = query_chain
        query_chain.range.return_value = query_chain
        query_chain.execute.return_value = MagicMock(data=[], count=0)
        mock_sb.table.return_value = query_chain

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads?has_website=false")
        assert resp.status_code == 200
        query_chain.is_.assert_called_with("website_url", "null")


def test_list_campaign_leads_has_website_and_phone_false_simultaneously():
    """Verify has_website=false and has_phone=false can be safely combined."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.return_value = query_chain
        query_chain.eq.return_value = query_chain
        query_chain.is_.return_value = query_chain
        query_chain.order.return_value = query_chain
        query_chain.range.return_value = query_chain
        query_chain.execute.return_value = MagicMock(data=[], count=0)
        mock_sb.table.return_value = query_chain

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads?has_website=false&has_phone=false")
        assert resp.status_code == 200
        query_chain.is_.assert_any_call("website_url", "null")
        query_chain.is_.assert_any_call("phone", "null")


def test_list_campaign_leads_suppressed_and_search_filters():
    """Verify is_suppressed and business_name search filters are applied."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.return_value = query_chain
        query_chain.eq.return_value = query_chain
        query_chain.ilike.return_value = query_chain
        query_chain.order.return_value = query_chain
        query_chain.range.return_value = query_chain
        query_chain.execute.return_value = MagicMock(data=[SAMPLE_LEAD_ROW], count=1)
        mock_sb.table.return_value = query_chain

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads?is_suppressed=true&search=Apex")
        assert resp.status_code == 200
        query_chain.eq.assert_any_call("is_suppressed", True)
        query_chain.ilike.assert_called_with("business_name", "%Apex%")


def test_leads_endpoints_invalid_uuid_returns_404():
    """Verify invalid UUID string returns 404 (not 500 or Postgres error)."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    resp1 = client.get("/api/campaigns/not-a-valid-uuid/leads")
    assert resp1.status_code == 404
    assert "not found" in resp1.json()["detail"]

    resp2 = client.get("/api/leads/not-a-valid-uuid")
    assert resp2.status_code == 404
    assert "not found" in resp2.json()["detail"]


def test_list_campaign_leads_db_error_returns_500():
    """Verify unexpected database error during listing returns sanitized 500."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: SAMPLE_CAMPAIGN_ROW

    with patch("backend.routers.leads.supabase") as mock_sb:
        query_chain = MagicMock()
        query_chain.select.side_effect = RuntimeError("Database down")
        mock_sb.table.return_value = query_chain

        resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/leads")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to retrieve leads for campaign"


def test_get_lead_detail_db_error_returns_500():
    """Verify unexpected database error during lead detail lookups returns sanitized 500."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_lead] = lambda: dict(SAMPLE_LEAD_ROW)

    with patch("backend.routers.leads.supabase") as mock_sb:
        mock_sb.table.side_effect = RuntimeError("Database lookup failed")

        resp = client.get(f"/api/leads/{SAMPLE_LEAD_ID}")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to retrieve lead details"


# =========================================================================
# 3. Lead Detail Endpoint Tests (GET /api/leads/{id})
# =========================================================================

def test_get_lead_detail_full():
    """Verify full lead detail includes audit, analysis, and evidence items."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_lead] = lambda: dict(
        SAMPLE_LEAD_ROW,
        campaigns={"user_id": MOCK_USER_1["id"]},
    )

    sample_audit = {
        "id": "aud-1",
        "lead_id": SAMPLE_LEAD_ID,
        "page_loads": True,
        "mobile_overflow": False,
        "lighthouse_performance": 85,
    }
    sample_analysis = {
        "id": "ana-1",
        "lead_id": SAMPLE_LEAD_ID,
        "recommended_service": "Website Redesign",
        "confidence": "high",
    }
    sample_evidence = [
        {"id": "ev-1", "lead_id": SAMPLE_LEAD_ID, "finding_title": "Fast load speed", "severity": "info"}
    ]

    with patch("backend.routers.leads.supabase") as mock_sb:
        # Mock audit, analysis, and evidence lookups
        audit_query = MagicMock()
        audit_query.select.return_value = audit_query
        audit_query.eq.return_value = audit_query
        audit_query.order.return_value = audit_query
        audit_query.limit.return_value = audit_query
        audit_query.execute.return_value = MagicMock(data=[sample_audit])

        analysis_query = MagicMock()
        analysis_query.select.return_value = analysis_query
        analysis_query.eq.return_value = analysis_query
        analysis_query.order.return_value = analysis_query
        analysis_query.limit.return_value = analysis_query
        analysis_query.execute.return_value = MagicMock(data=[sample_analysis])

        evidence_query = MagicMock()
        evidence_query.select.return_value = evidence_query
        evidence_query.eq.return_value = evidence_query
        evidence_query.order.return_value = evidence_query
        evidence_query.execute.return_value = MagicMock(data=sample_evidence)

        def table_router(table_name):
            if table_name == "website_audits":
                return audit_query
            if table_name == "ai_analyses":
                return analysis_query
            if table_name == "evidence_items":
                return evidence_query
            return MagicMock()

        mock_sb.table.side_effect = table_router

        resp = client.get(f"/api/leads/{SAMPLE_LEAD_ID}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["message"] == "Lead retrieved successfully"
        data = body["data"]
        assert data["id"] == SAMPLE_LEAD_ID
        assert data["business_name"] == "Apex IIT Coaching"
        assert data["audit"]["id"] == "aud-1"
        assert data["analysis"]["id"] == "ana-1"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["finding_title"] == "Fast load speed"
        # Ensure joined internal campaigns dict was stripped
        assert "campaigns" not in data


def test_get_lead_detail_without_audit_or_analysis():
    """Verify lead detail returns cleanly when audit, analysis, and evidence are not yet created."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_lead] = lambda: dict(SAMPLE_LEAD_ROW)

    with patch("backend.routers.leads.supabase") as mock_sb:
        empty_query = MagicMock()
        empty_query.select.return_value = empty_query
        empty_query.eq.return_value = empty_query
        empty_query.order.return_value = empty_query
        empty_query.limit.return_value = empty_query
        empty_query.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = empty_query

        resp = client.get(f"/api/leads/{SAMPLE_LEAD_ID}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == SAMPLE_LEAD_ID
        assert data["audit"] is None
        assert data["analysis"] is None
        assert data["evidence"] == []

