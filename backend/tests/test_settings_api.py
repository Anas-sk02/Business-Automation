"""Integration tests for Settings & Suppression List Router (Stage 7 Task 3).

Verifies GET /api/settings/suppression-list endpoint per docs/UI-UX.md Section 6.12.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user

USER_1_ID = "00000000-0000-0000-0000-000000000001"
USER_2_ID = "00000000-0000-0000-0000-000000000002"
CAMP_1_ID = "11111111-1111-1111-1111-111111111111"
CAMP_2_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def auth_user():
    return {"id": USER_1_ID, "email": "doctor@signalforge.ai"}


@pytest.fixture
def client(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    app.dependency_overrides.clear()
    return TestClient(app)


def test_get_suppression_list_unauthorized(unauth_client):
    """Verify GET /api/settings/suppression-list rejects unauthenticated requests with 401."""
    res = unauth_client.get("/api/settings/suppression-list")
    assert res.status_code == 401


def test_get_suppression_list_empty_when_no_campaigns(client):
    """Verify empty list returned when user has no campaigns."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        query = MagicMock()
        query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = query

        res = client.get("/api/settings/suppression-list")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 0
        assert data["suppressed_contacts"] == []


def test_get_suppression_list_success(client):
    """Verify suppressed leads are returned with phone, reason, and campaign context."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [{"id": CAMP_1_ID, "name": "Dental Clinics Pune"}]
        mock_leads = [
            {
                "id": "lead-1",
                "phone": "+919822010001",
                "business_name": "Joshi Dental Clinic",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "suppression_reason": "Requested STOP",
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-05T12:00:00Z",
                "created_at": "2026-11-01T10:00:00Z",
            },
            {
                "id": "lead-2",
                "phone": "+919822010002",
                "business_name": "Active Care",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": False,
                "suppression_reason": None,
                "pipeline_stage": "contacted",
                "updated_at": "2026-11-05T10:00:00Z",
                "created_at": "2026-11-01T10:00:00Z",
            },
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        res = client.get("/api/settings/suppression-list")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 1
        assert len(data["suppressed_contacts"]) == 1
        record = data["suppressed_contacts"][0]
        assert record["phone"] == "+919822010001"
        assert record["business_name"] == "Joshi Dental Clinic"
        assert record["campaign_name"] == "Dental Clinics Pune"
        assert record["suppression_reason"] == "Requested STOP"
        assert record["opted_out_at"] == "2026-11-05T12:00:00Z"


def test_get_suppression_list_search_filter(client):
    """Verify search parameter filters results by phone or business name."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [{"id": CAMP_1_ID, "name": "Dental Clinics Pune"}]
        mock_leads = [
            {
                "id": "lead-1",
                "phone": "+919822010001",
                "business_name": "Joshi Dental Clinic",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "suppression_reason": "Requested STOP",
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-05T12:00:00Z",
            },
            {
                "id": "lead-2",
                "phone": "+919822099999",
                "business_name": "Kulkarni Eye Clinic",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "suppression_reason": "Unsubscribed",
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-04T12:00:00Z",
            },
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        # Search by phone substring
        res_phone = client.get("/api/settings/suppression-list?search=99999")
        assert res_phone.status_code == 200
        assert res_phone.json()["data"]["total"] == 1
        assert res_phone.json()["data"]["suppressed_contacts"][0]["phone"] == "+919822099999"

        # Search by name substring
        res_name = client.get("/api/settings/suppression-list?search=Joshi")
        assert res_name.status_code == 200
        assert res_name.json()["data"]["total"] == 1
        assert res_name.json()["data"]["suppressed_contacts"][0]["business_name"] == "Joshi Dental Clinic"


def test_get_suppression_list_pagination(client):
    """Verify pagination slices results properly."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [{"id": CAMP_1_ID, "name": "Dental Clinics Pune"}]
        mock_leads = [
            {
                "id": f"lead-{i}",
                "phone": f"+91982201000{i}",
                "business_name": f"Clinic {i}",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "pipeline_stage": "opted_out",
                "updated_at": f"2026-11-0{i}T12:00:00Z",
            }
            for i in range(1, 6)
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        res = client.get("/api/settings/suppression-list?page=1&page_size=2")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 5
        assert len(data["suppressed_contacts"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2


def test_get_suppression_list_multi_tenant_isolation(client):
    """Verify user can only query campaigns and leads belonging to their user_id."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        campaigns_query = MagicMock()
        campaigns_query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = campaigns_query

        client.get("/api/settings/suppression-list")

        # Verify campaigns table query was strictly filtered by authenticated user's ID
        campaigns_query.select.return_value.eq.assert_called_with("user_id", USER_1_ID)


def test_get_suppression_list_db_error_returns_500(client):
    """Verify database exceptions return 500 with generic message."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        query = MagicMock()
        query.select.return_value.eq.return_value.execute.side_effect = Exception("Supabase connection timeout")
        mock_db.table.return_value = query

        res = client.get("/api/settings/suppression-list")
        assert res.status_code == 500
        assert res.json()["detail"] == "Failed to retrieve suppression list"


def test_get_suppression_list_empty_when_no_leads_suppressed(client):
    """Verify returns 0 results when leads exist but none are suppressed."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [{"id": CAMP_1_ID, "name": "Dental Clinics Pune"}]
        mock_leads = [
            {
                "id": "lead-1",
                "phone": "+919822010001",
                "business_name": "Active Care",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": False,
                "suppression_reason": None,
                "pipeline_stage": "contacted",
            }
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        res = client.get("/api/settings/suppression-list")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 0
        assert data["suppressed_contacts"] == []


def test_get_suppression_list_deduplication_by_phone(client):
    """Verify multiple leads with the same phone number are deduplicated, keeping the latest."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [
            {"id": CAMP_1_ID, "name": "Campaign 1"},
            {"id": CAMP_2_ID, "name": "Campaign 2"},
        ]
        # Same phone in both campaigns, lead-2 has newer timestamp
        mock_leads = [
            {
                "id": "lead-1",
                "phone": "+919822010001",
                "business_name": "Old Clinic",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "suppression_reason": "Requested STOP earlier",
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-01T10:00:00Z",
            },
            {
                "id": "lead-2",
                "phone": "+919822010001",
                "business_name": "New Clinic",
                "campaign_id": CAMP_2_ID,
                "is_suppressed": True,
                "suppression_reason": "Stop command latest",
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-05T12:00:00Z",
            },
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        res = client.get("/api/settings/suppression-list")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 1
        assert len(data["suppressed_contacts"]) == 1
        record = data["suppressed_contacts"][0]
        assert record["phone"] == "+919822010001"
        assert record["suppression_reason"] == "Stop command latest"
        assert record["business_name"] == "New Clinic"


def test_get_suppression_list_page_beyond_range(client):
    """Verify requesting page beyond available range returns empty contacts with correct total."""
    with patch("backend.routers.settings.get_supabase_client") as mock_get_sb:
        mock_db = MagicMock()
        mock_get_sb.return_value = mock_db

        mock_campaigns = [{"id": CAMP_1_ID, "name": "Dental Clinics Pune"}]
        mock_leads = [
            {
                "id": "lead-1",
                "phone": "+919822010001",
                "business_name": "Joshi Clinic",
                "campaign_id": CAMP_1_ID,
                "is_suppressed": True,
                "pipeline_stage": "opted_out",
                "updated_at": "2026-11-05T12:00:00Z",
            }
        ]

        def table_router(table_name):
            q = MagicMock()
            if table_name == "campaigns":
                q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            elif table_name == "leads":
                q.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
            return q

        mock_db.table.side_effect = table_router

        res = client.get("/api/settings/suppression-list?page=10&page_size=20")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] == 1
        assert data["suppressed_contacts"] == []
        assert data["page"] == 10


