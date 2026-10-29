"""Integration tests for Stage 3 Task 5: Single & Batch Audit API Endpoints & State Machine."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app, recover_stale_audit_jobs
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


def test_start_lead_audit_unauthorized(unauth_client):
    """Verify POST /api/leads/{id}/start-audit rejects unauthenticated requests with 401."""
    response = unauth_client.post("/api/leads/3fa85f64-5717-4562-b3fc-2c963f66afa6/start-audit")
    assert response.status_code == 401


def test_start_lead_audit_not_found(client):
    """Verify POST /api/leads/{id}/start-audit returns 404 when lead is unowned or nonexistent."""
    with patch("backend.dependencies.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        response = client.post("/api/leads/3fa85f64-5717-4562-b3fc-2c963f66afa6/start-audit")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_start_lead_audit_success_202(client, auth_user):
    """Verify POST /api/leads/{id}/start-audit transitions lead stage and returns 202 Accepted."""
    lead_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    lead_data = {
        "id": lead_id,
        "campaign_id": "camp-123",
        "business_name": "Apex Dental",
        "website_url": "https://apexdental.in",
        "pipeline_stage": "discovered",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )
    mock_leads_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    mock_audits_table = MagicMock()
    # No existing running audit
    mock_audits_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "website_audits":
            return mock_audits_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            with patch("backend.services.audit.AuditService.audit_lead_website", new_callable=AsyncMock) as mock_audit:
                response = client.post(f"/api/leads/{lead_id}/start-audit")

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["lead_id"] == lead_id
    assert res_json["data"]["status"] == "accepted"

    # Verify stage transition to research_pending was executed
    update_calls = mock_leads_table.update.call_args_list
    assert any(c[0][0].get("pipeline_stage") == "research_pending" for c in update_calls)


def test_start_lead_audit_idempotent_when_already_running(client, auth_user):
    """Verify POST /api/leads/{id}/start-audit returns existing running status if already in progress."""
    lead_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    lead_data = {
        "id": lead_id,
        "campaign_id": "camp-123",
        "business_name": "Apex Dental",
        "pipeline_stage": "research_pending",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_audits_table = MagicMock()
    mock_audits_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "audit-running-1", "status": "running"}]
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "website_audits":
            return mock_audits_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.post(f"/api/leads/{lead_id}/start-audit")

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["status"] == "running"
    assert res_json["data"]["audit_id"] == "audit-running-1"


def test_get_lead_audit_report_success(client, auth_user):
    """Verify GET /api/leads/{id}/audit returns full audit report with signed screenshot URLs."""
    lead_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    lead_data = {
        "id": lead_id,
        "campaign_id": "camp-123",
        "business_name": "Apex Dental",
        "campaigns": {"user_id": auth_user["id"]},
    }

    audit_row = {
        "id": "audit-succ-123",
        "lead_id": lead_id,
        "tested_url": "https://apexdental.in",
        "dns_resolves": True,
        "http_status_code": 200,
        "ssl_valid": True,
        "page_loads": True,
        "load_time_seconds": 1.2,
        "final_url": "https://apexdental.in/",
        "mobile_overflow": False,
        "mobile_overflow_pixels": 0,
        "has_contact_form": True,
        "has_phone_on_site": True,
        "has_email_on_site": True,
        "has_whatsapp_link": True,
        "has_social_links": True,
        "social_links": [{"platform": "facebook", "url": "https://facebook.com/apex"}],
        "page_title": "Apex Dental Clinic",
        "meta_description": "Premier dentistry in Nagpur",
        "h1_headings": ["Welcome to Apex Dental"],
        "has_alt_texts": True,
        "missing_alt_count": 0,
        "total_internal_links": 5,
        "broken_links": [],
        "broken_link_count": 0,
        "lighthouse_performance": 90,
        "lighthouse_seo": 95,
        "lighthouse_accessibility": 92,
        "lighthouse_best_practices": 88,
        "screenshot_desktop_url": "u/l/desk.png",
        "screenshot_mobile_url": "u/l/mob.png",
        "industry_checks": {},
        "status": "completed",
        "error_message": None,
        "created_at": "2026-10-29T10:00:00Z",
        "started_at": "2026-10-29T10:00:01Z",
        "completed_at": "2026-10-29T10:00:15Z",
    }

    evidence_rows = [
        {
            "id": "ev-1",
            "lead_id": lead_id,
            "audit_id": "audit-succ-123",
            "finding_title": "WhatsApp click-to-chat enabled",
            "description": "Direct WhatsApp link available.",
            "evidence_type": "content_scan",
            "evidence_data": {"has_whatsapp": True},
            "severity": "info",
            "verification_status": "verified",
            "detected_at": "2026-10-29T10:00:05Z",
        }
    ]

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_audits_table = MagicMock()
    mock_audits_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[audit_row]
    )

    mock_evidence_table = MagicMock()
    mock_evidence_table.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=evidence_rows
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "website_audits":
            return mock_audits_table
        if name == "evidence_items":
            return mock_evidence_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            with patch("backend.services.audit.AuditService.get_signed_screenshot_url") as mock_sign:
                mock_sign.side_effect = lambda path, **kw: f"https://signed.storage/{path}?token=xyz"
                response = client.get(f"/api/leads/{lead_id}/audit")

    assert response.status_code == 200
    res_json = response.json()
    data = res_json["data"]
    assert data["audit"]["id"] == "audit-succ-123"
    assert data["audit"]["page_title"] == "Apex Dental Clinic"
    assert data["audit"]["lighthouse_performance"] == 90
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["finding_title"] == "WhatsApp click-to-chat enabled"
    assert data["signed_screenshot_desktop_url"] == "https://signed.storage/u/l/desk.png?token=xyz"
    assert data["signed_screenshot_mobile_url"] == "https://signed.storage/u/l/mob.png?token=xyz"


def test_get_lead_audit_report_empty_when_not_audited(client, auth_user):
    """Verify GET /api/leads/{id}/audit returns empty/null audit report when lead has no audits."""
    lead_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    lead_data = {
        "id": lead_id,
        "campaign_id": "camp-123",
        "business_name": "Apex Dental",
        "campaigns": {"user_id": auth_user["id"]},
    }

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[lead_data]
    )

    mock_audits_table = MagicMock()
    mock_audits_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    def table_router(name):
        if name == "leads":
            return mock_leads_table
        if name == "website_audits":
            return mock_audits_table
        return MagicMock()

    with patch("backend.dependencies.supabase") as mock_dep_db:
        mock_dep_db.table.side_effect = table_router
        with patch("backend.routers.leads.supabase") as mock_router_db:
            mock_router_db.table.side_effect = table_router
            response = client.get(f"/api/leads/{lead_id}/audit")

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"]["audit"] is None
    assert res_json["data"]["evidence"] == []


def test_start_batch_campaign_audit_success(client, auth_user):
    """Verify POST /api/campaigns/{id}/start-audit returns 202 Accepted and queues eligible leads."""
    campaign_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    campaign_data = {
        "id": campaign_id,
        "name": "Dentists Nagpur",
        "user_id": auth_user["id"],
    }
    eligible_leads = [
        {"id": "lead-1", "pipeline_stage": "discovered"},
        {"id": "lead-2", "pipeline_stage": "discovered"},
    ]

    mock_campaigns_table = MagicMock()
    mock_campaigns_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[campaign_data]
    )

    mock_leads_table = MagicMock()
    mock_leads_table.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=eligible_leads
    )
    mock_leads_table.update.return_value.in_.return_value.execute.return_value = MagicMock(data=[{}])

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
            with patch("backend.services.audit.AuditService.audit_lead_website", new_callable=AsyncMock):
                response = client.post(f"/api/campaigns/{campaign_id}/start-audit")

    assert response.status_code == 202
    res_json = response.json()
    assert res_json["data"]["campaign_id"] == campaign_id
    assert res_json["data"]["leads_queued"] == 2


@pytest.mark.anyio
async def test_recover_stale_audit_jobs():
    """Verify recover_stale_audit_jobs marks audits stuck in running > 15m as failed."""
    mock_db = MagicMock()
    mock_audits_table = MagicMock()
    mock_audits_table.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[{"id": "audit-stale-1", "lead_id": "lead-stale-1"}]
    )
    mock_audits_table.update.return_value.in_.return_value.execute.return_value = MagicMock(data=[{}])

    mock_leads_table = MagicMock()
    mock_leads_table.update.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    def table_router(name):
        if name == "website_audits":
            return mock_audits_table
        if name == "leads":
            return mock_leads_table
        return MagicMock()

    mock_db.table.side_effect = table_router

    with patch("backend.main.get_supabase_client", return_value=mock_db):
        recovered_count = await recover_stale_audit_jobs()

    assert recovered_count == 1
    update_audit_args = mock_audits_table.update.call_args[0][0]
    assert update_audit_args["status"] == "failed"
    assert "stale job" in update_audit_args["error_message"]


def test_start_batch_campaign_audit_zero_eligible(client, auth_user):
    """Verify POST /api/campaigns/{id}/start-audit returns 202 with 0 leads when none eligible."""
    campaign_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    campaign_data = {
        "id": campaign_id,
        "name": "Dentists Nagpur",
        "user_id": auth_user["id"],
    }

    mock_campaigns_table = MagicMock()
    mock_campaigns_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[campaign_data]
    )

    mock_leads_table = MagicMock()
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
            response = client.post(f"/api/campaigns/{campaign_id}/start-audit")

    assert response.status_code == 202
    assert response.json()["data"]["leads_queued"] == 0
    assert "no leads to audit" in response.json()["message"].lower()


def test_audit_endpoints_invalid_uuid_returns_404(client):
    """Verify non-UUID path parameters safely return 404 per decisions.md Section 3."""
    res1 = client.post("/api/leads/not-a-valid-uuid/start-audit")
    assert res1.status_code == 404
    assert "not found" in res1.json()["detail"].lower()

    res2 = client.get("/api/leads/not-a-valid-uuid/audit")
    assert res2.status_code == 404
    assert "not found" in res2.json()["detail"].lower()

    res3 = client.post("/api/campaigns/not-a-valid-uuid/start-audit")
    assert res3.status_code == 404
    assert "not found" in res3.json()["detail"].lower()


def test_get_lead_audit_report_unauthorized(unauth_client):
    """Verify GET /api/leads/{id}/audit rejects unauthenticated calls with 401."""
    response = unauth_client.get("/api/leads/3fa85f64-5717-4562-b3fc-2c963f66afa6/audit")
    assert response.status_code == 401


