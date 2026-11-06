"""Integration tests for Stage 6 Task 3: Pipeline API & Stage Transition Router."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_lead

VALID_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"
CAMP_ID_1 = "11111111-1111-1111-1111-111111111111"
CAMP_ID_2 = "22222222-2222-2222-2222-222222222222"
LEAD_QUALIFIED_ID = "33333333-3333-3333-3333-333333333331"
LEAD_CONTACTED_ID = "33333333-3333-3333-3333-333333333332"
LEAD_OPTED_OUT_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def auth_user():
    return {"id": VALID_USER_ID, "email": "doctor@signalforge.ai"}


class FakeQuery:
    def __init__(self, data=None):
        self._data = data if data is not None else []
        self._filters = []
        self._in_filters = []
        self._update_payload = None

    def select(self, *args, **kwargs):
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def in_(self, col, vals):
        self._in_filters.append((col, vals))
        return self

    def order(self, col, desc=False):
        return self

    def execute(self):
        filtered = list(self._data)
        for col, val in self._filters:
            filtered = [item for item in filtered if item.get(col) == val]
        for col, vals in self._in_filters:
            filtered = [item for item in filtered if item.get(col) in vals]

        if self._update_payload is not None:
            for item in filtered:
                item.update(self._update_payload)
            return MagicMock(data=filtered)

        return MagicMock(data=filtered)


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def set_table(self, name, rows):
        self.tables[name] = rows

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


@pytest.fixture
def mock_db():
    db = FakeSupabase()
    # User's campaigns
    db.set_table("campaigns", [
        {"id": CAMP_ID_1, "user_id": VALID_USER_ID, "name": "Dental Clinics Pune"},
        {"id": CAMP_ID_2, "user_id": VALID_USER_ID, "name": "Coaching Classes Mumbai"},
    ])
    # Leads across campaigns
    db.set_table("leads", [
        {
            "id": LEAD_QUALIFIED_ID,
            "campaign_id": CAMP_ID_1,
            "business_name": "Smile Dental Care",
            "category": "Dentist",
            "address": "MG Road, Pune",
            "phone": "+919822011111",
            "website_url": "https://smiledental.in",
            "fit_score": 85,
            "pipeline_stage": "qualified",
            "rating": 4.8,
            "review_count": 52,
            "notes": "Verified high priority prospect",
            "is_suppressed": False,
            "last_contacted_at": None,
            "next_followup_at": None,
            "created_at": "2026-11-01T10:00:00Z",
        },
        {
            "id": LEAD_CONTACTED_ID,
            "campaign_id": CAMP_ID_1,
            "business_name": "Apex Physio Clinic",
            "category": "Physiotherapy",
            "address": "Kothrud, Pune",
            "phone": "+919822022222",
            "website_url": "https://apexphysio.in",
            "fit_score": 75,
            "pipeline_stage": "contacted",
            "rating": 4.5,
            "review_count": 28,
            "notes": "",
            "is_suppressed": False,
            "last_contacted_at": "2026-11-05T12:00:00Z",
            "next_followup_at": "2026-11-08T09:30:00Z",
            "created_at": "2026-11-01T10:00:00Z",
        },
        {
            "id": LEAD_OPTED_OUT_ID,
            "campaign_id": CAMP_ID_1,
            "business_name": "Opted Out Dental",
            "category": "Dentist",
            "phone": "+919822033333",
            "fit_score": 60,
            "pipeline_stage": "opted_out",
            "is_suppressed": True,
            "notes": "STOP received",
            "created_at": "2026-11-01T10:00:00Z",
        },
    ])
    db.set_table("followup_schedules", [
        {"id": "fs_1", "lead_id": LEAD_CONTACTED_ID, "campaign_id": CAMP_ID_1, "status": "pending"},
    ])
    return db


# -----------------------------------------------------------------------------
# 1. Authentication & Tenant Isolation
# -----------------------------------------------------------------------------

def test_pipeline_requires_auth():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.get("/api/pipeline")
    assert res.status_code == 401


def test_put_stage_requires_auth():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.put(f"/api/leads/{LEAD_QUALIFIED_ID}/stage", json={"stage": "meeting_scheduled"})
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 2. GET /api/pipeline Kanban Board
# -----------------------------------------------------------------------------

def test_get_pipeline_board_success(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.get("/api/pipeline")

    assert res.status_code == 200
    data = res.json()["data"]

    # Verify standard 9 working columns exist
    assert "qualified" in data["columns"]
    assert "contacted" in data["columns"]
    assert "followup_due" in data["columns"]
    assert "replied" in data["columns"]
    assert "interested" in data["columns"]
    assert "meeting_scheduled" in data["columns"]
    assert "proposal_sent" in data["columns"]
    assert "negotiation" in data["columns"]
    assert "won" in data["columns"]

    # Verify closed rail exists
    assert "not_interested" in data["closed"]
    assert "no_response" in data["closed"]
    assert "closed_lost" in data["closed"]
    assert "opted_out" in data["closed"]

    # Check lead placement
    qualified_cards = data["columns"]["qualified"]
    assert len(qualified_cards) == 1
    assert qualified_cards[0]["id"] == LEAD_QUALIFIED_ID
    assert qualified_cards[0]["campaign_name"] == "Dental Clinics Pune"

    contacted_cards = data["columns"]["contacted"]
    assert len(contacted_cards) == 1
    assert contacted_cards[0]["id"] == LEAD_CONTACTED_ID

    opted_out_cards = data["closed"]["opted_out"]
    assert len(opted_out_cards) == 1
    assert opted_out_cards[0]["id"] == LEAD_OPTED_OUT_ID

    assert data["total_active_leads"] == 2
    assert data["total_leads"] == 3


def test_get_pipeline_board_filter_by_campaign(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.get(f"/api/pipeline?campaign_id={CAMP_ID_1}")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_leads"] == 3

    # Campaign 2 has 0 leads
    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res_empty = client.get(f"/api/pipeline?campaign_id={CAMP_ID_2}")
    assert res_empty.status_code == 200
    assert res_empty.json()["data"]["total_leads"] == 0


def test_get_pipeline_board_unowned_campaign_returns_404(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    unowned_camp = "99999999-9999-9999-9999-999999999999"

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.get(f"/api/pipeline?campaign_id={unowned_camp}")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_pipeline_board_invalid_campaign_uuid(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.get("/api/pipeline?campaign_id=not-a-valid-uuid")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_pipeline_board_db_error_returns_500(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    failing_db = MagicMock()
    failing_db.table.side_effect = RuntimeError("Database offline")

    with patch("backend.routers.pipeline.get_supabase_client", return_value=failing_db):
        res = client.get("/api/pipeline")

    assert res.status_code == 500
    assert "failed to retrieve" in res.json()["detail"].lower()


def test_get_pipeline_board_no_campaigns_returns_empty(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    empty_db = FakeSupabase()
    empty_db.set_table("campaigns", [])
    empty_db.set_table("leads", [])

    with patch("backend.routers.pipeline.get_supabase_client", return_value=empty_db):
        res = client.get("/api/pipeline")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_leads"] == 0
    assert data["total_active_leads"] == 0


# -----------------------------------------------------------------------------
# 3. PUT /api/leads/{id}/stage Manual Transitions
# -----------------------------------------------------------------------------

def test_put_stage_valid_manual_transition(auth_user, mock_db):
    lead = mock_db.tables["leads"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: lead
    client = TestClient(app)

    payload = {
        "stage": "meeting_scheduled",
        "notes": "Discovery call scheduled for Friday 4 PM",
        "deal_value_inr": 25000,
    }

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/leads/{LEAD_QUALIFIED_ID}/stage", json=payload)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["pipeline_stage"] == "meeting_scheduled"
    assert data["notes"] == "Discovery call scheduled for Friday 4 PM"


def test_put_stage_rejects_automated_stages(auth_user, mock_db):
    lead = mock_db.tables["leads"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: lead
    client = TestClient(app)

    # Attempting to move manually to 'contacted' (an automated stage)
    payload = {"stage": "contacted"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/leads/{LEAD_QUALIFIED_ID}/stage", json=payload)

    assert res.status_code == 400
    assert "moves automatically" in res.json()["detail"].lower()


def test_put_stage_rejects_invalid_stage_name(auth_user, mock_db):
    lead = mock_db.tables["leads"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: lead
    client = TestClient(app)

    payload = {"stage": "completely_invented_stage"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/leads/{LEAD_QUALIFIED_ID}/stage", json=payload)

    assert res.status_code == 400
    assert "invalid manual stage" in res.json()["detail"].lower()


def test_put_stage_blocks_moving_opted_out_lead(auth_user, mock_db):
    opted_out_lead = mock_db.tables["leads"][2]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: opted_out_lead
    client = TestClient(app)

    payload = {"stage": "won"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/leads/{LEAD_OPTED_OUT_ID}/stage", json=payload)

    assert res.status_code == 400
    assert "opted-out leads cannot be moved" in res.json()["detail"].lower()


def test_put_stage_cancels_followups_on_closed_lost(auth_user, mock_db):
    contacted_lead = mock_db.tables["leads"][1]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: contacted_lead
    client = TestClient(app)

    payload = {"stage": "closed_lost", "notes": "No budget this quarter"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db), \
         patch("backend.services.followup.FollowupService.cancel_followups", new_callable=AsyncMock) as mock_cancel:
        res = client.put(f"/api/leads/{LEAD_CONTACTED_ID}/stage", json=payload)

    assert res.status_code == 200
    mock_cancel.assert_awaited_once_with(
        lead_id=LEAD_CONTACTED_ID,
        reason="manual_closed_lost",
        campaign_id=CAMP_ID_1,
    )


def test_put_stage_cancels_followups_on_won(auth_user, mock_db):
    contacted_lead = mock_db.tables["leads"][1]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: contacted_lead
    client = TestClient(app)

    payload = {"stage": "won", "notes": "Contract signed!"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=mock_db), \
         patch("backend.services.followup.FollowupService.cancel_followups", new_callable=AsyncMock) as mock_cancel:
        res = client.put(f"/api/leads/{LEAD_CONTACTED_ID}/stage", json=payload)

    assert res.status_code == 200
    mock_cancel.assert_awaited_once_with(
        lead_id=LEAD_CONTACTED_ID,
        reason="manual_won",
        campaign_id=CAMP_ID_1,
    )


def test_put_stage_unowned_lead_returns_404(auth_user):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    unowned_id = "99999999-9999-9999-9999-999999999999"

    # Real get_owned_lead will query database with user_id and return 404
    empty_db = FakeSupabase()
    empty_db.set_table("leads", [])
    empty_db.set_table("campaigns", [])

    with patch("backend.dependencies.supabase", empty_db):
        res = client.put(f"/api/leads/{unowned_id}/stage", json={"stage": "meeting_scheduled"})

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_put_stage_invalid_uuid_returns_404(auth_user):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    res = client.put("/api/leads/not-a-valid-uuid/stage", json={"stage": "meeting_scheduled"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_put_stage_db_error_returns_500(auth_user, mock_db):
    contacted_lead = mock_db.tables["leads"][1]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: contacted_lead
    client = TestClient(app)

    failing_db = MagicMock()
    failing_db.table.side_effect = RuntimeError("Database write error")

    payload = {"stage": "meeting_scheduled"}

    with patch("backend.routers.pipeline.get_supabase_client", return_value=failing_db), \
         patch("backend.services.followup.FollowupService.cancel_followups", new_callable=AsyncMock):
        res = client.put(f"/api/leads/{LEAD_CONTACTED_ID}/stage", json=payload)

    assert res.status_code == 500
    assert "failed to update" in res.json()["detail"].lower()


