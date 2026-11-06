"""Integration tests for Stage 6 Task 4: Tasks API & Task Management Router."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_task

VALID_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"
CAMP_ID = "11111111-1111-1111-1111-111111111111"
LEAD_ID = "22222222-2222-2222-2222-222222222222"
TASK_1_ID = "33333333-3333-3333-3333-333333333331"
TASK_2_ID = "33333333-3333-3333-3333-333333333332"
TASK_3_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def auth_user():
    return {"id": VALID_USER_ID, "email": "doctor@signalforge.ai"}


class FakeQuery:
    def __init__(self, data=None):
        self._data = list(data) if data is not None else []
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
    now_utc = datetime.now(timezone.utc)
    yesterday_iso = (now_utc - timedelta(days=1)).isoformat()
    tomorrow_iso = (now_utc + timedelta(days=1)).isoformat()

    db.set_table("campaigns", [
        {"id": CAMP_ID, "user_id": VALID_USER_ID, "name": "Dental Outreach Pune"},
    ])
    db.set_table("leads", [
        {"id": LEAD_ID, "campaign_id": CAMP_ID, "business_name": "Smile Dentists"},
    ])
    db.set_table("tasks", [
        {
            "id": TASK_1_ID,
            "lead_id": LEAD_ID,
            "campaign_id": CAMP_ID,
            "user_id": VALID_USER_ID,
            "task_type": "review_reply",
            "title": "Review reply from Smile Dentists",
            "description": "Prospect asked for pricing",
            "status": "pending",
            "priority": "urgent",
            "due_date": yesterday_iso,  # overdue
            "snoozed_until": None,
            "completed_at": None,
            "created_at": (now_utc - timedelta(hours=2)).isoformat(),
            "updated_at": (now_utc - timedelta(hours=2)).isoformat(),
        },
        {
            "id": TASK_2_ID,
            "lead_id": LEAD_ID,
            "campaign_id": CAMP_ID,
            "user_id": VALID_USER_ID,
            "task_type": "approve_message",
            "title": "Approve follow-up message 1",
            "description": "Scheduled follow-up",
            "status": "pending",
            "priority": "medium",
            "due_date": tomorrow_iso,  # upcoming
            "snoozed_until": None,
            "completed_at": None,
            "created_at": (now_utc - timedelta(hours=1)).isoformat(),
            "updated_at": (now_utc - timedelta(hours=1)).isoformat(),
        },
        {
            "id": TASK_3_ID,
            "lead_id": LEAD_ID,
            "campaign_id": CAMP_ID,
            "user_id": VALID_USER_ID,
            "task_type": "callback",
            "title": "Call Dr. Sharma",
            "description": "Old completed callback",
            "status": "completed",
            "priority": "high",
            "due_date": yesterday_iso,
            "snoozed_until": None,
            "completed_at": now_utc.isoformat(),
            "created_at": (now_utc - timedelta(days=2)).isoformat(),
            "updated_at": now_utc.isoformat(),
        },
    ])
    return db


# -----------------------------------------------------------------------------
# 1. Authentication & Security
# -----------------------------------------------------------------------------

def test_tasks_requires_auth():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.get("/api/tasks")
    assert res.status_code == 401


def test_upcoming_tasks_requires_auth():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.get("/api/tasks/upcoming")
    assert res.status_code == 401


def test_put_task_requires_auth():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"status": "completed"})
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 2. GET /api/tasks Listing & Filtering
# -----------------------------------------------------------------------------

def test_get_tasks_success(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["tasks"]) == 3
    # Check enriched lead and campaign names
    first_task = next(t for t in data["tasks"] if t["id"] == TASK_1_ID)
    assert first_task["lead_name"] == "Smile Dentists"
    assert first_task["campaign_name"] == "Dental Outreach Pune"

    # Check timeframe counters
    counts = data["counts"]
    assert counts["overdue"] == 1
    assert counts["upcoming"] == 1
    assert counts["completed"] == 1
    assert counts["total"] == 3


def test_get_tasks_filter_by_status(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks?status=completed")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == TASK_3_ID


def test_get_tasks_filter_by_priority(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks?priority=urgent")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == TASK_1_ID


def test_get_tasks_filter_by_lead_and_campaign(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get(f"/api/tasks?lead_id={LEAD_ID}&campaign_id={CAMP_ID}")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["tasks"]) == 3


def test_get_tasks_invalid_uuid_returns_404(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks?lead_id=invalid-uuid-123")

    assert res.status_code == 404


def test_get_tasks_unowned_campaign_returns_404(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    unowned_camp_id = "99999999-9999-9999-9999-999999999999"

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get(f"/api/tasks?campaign_id={unowned_camp_id}")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_tasks_unowned_lead_returns_404(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    unowned_lead_id = "99999999-9999-9999-9999-999999999999"

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get(f"/api/tasks?lead_id={unowned_lead_id}")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_tasks_invalid_status_returns_400(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks?status=invalid_status")

    assert res.status_code == 400
    assert "invalid task status" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 3. GET /api/tasks/upcoming Work Queue
# -----------------------------------------------------------------------------

def test_get_upcoming_tasks_success(auth_user, mock_db):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.get("/api/tasks/upcoming")

    assert res.status_code == 200
    tasks = res.json()["data"]
    # Only open tasks (pending/in_progress) returned (TASK_1, TASK_2)
    assert len(tasks) == 2
    ids = [t["id"] for t in tasks]
    assert TASK_1_ID in ids
    assert TASK_2_ID in ids
    assert TASK_3_ID not in ids  # completed task excluded


# -----------------------------------------------------------------------------
# 4. PUT /api/tasks/{id} Updates & Snooze
# -----------------------------------------------------------------------------

def test_put_task_complete(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    payload = {"status": "completed"}

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/tasks/{TASK_1_ID}", json=payload)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_put_task_reopen(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][2]  # currently completed
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    payload = {"status": "pending"}

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/tasks/{TASK_3_ID}", json=payload)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "pending"
    assert data["completed_at"] is None


def test_put_task_snooze_preset(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    payload = {"snooze_preset": "tomorrow"}

    with patch("backend.routers.tasks.get_supabase_client", return_value=mock_db):
        res = client.put(f"/api/tasks/{TASK_1_ID}", json=payload)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "snoozed"
    assert data["snoozed_until"] is not None


def test_put_task_unowned_returns_404(auth_user):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)
    unowned_id = "99999999-9999-9999-9999-999999999999"

    empty_db = FakeSupabase()
    empty_db.set_table("tasks", [])

    with patch("backend.dependencies.supabase", empty_db):
        res = client.put(f"/api/tasks/{unowned_id}", json={"status": "completed"})

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_put_task_invalid_uuid_returns_404(auth_user):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    res = client.put("/api/tasks/not-a-valid-uuid", json={"status": "completed"})
    assert res.status_code == 404


def test_put_task_invalid_status_returns_400(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"status": "invalid_xyz"})
    assert res.status_code == 400


def test_put_task_snooze_past_returns_400(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"snoozed_until": past_iso})
    assert res.status_code == 400
    assert "must be in the future" in res.json()["detail"].lower()


def test_put_task_empty_title_returns_400(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"title": "   "})
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"].lower()


def test_put_task_invalid_priority_returns_400(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"priority": "invalid_priority"})
    assert res.status_code == 400
    assert "invalid task priority" in res.json()["detail"].lower()


def test_put_task_invalid_snooze_preset_returns_400(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    res = client.put(f"/api/tasks/{TASK_1_ID}", json={"snooze_preset": "invalid_preset"})
    assert res.status_code == 400
    assert "invalid snooze preset" in res.json()["detail"].lower()


def test_put_task_db_error_returns_500(auth_user, mock_db):
    task_row = mock_db.tables["tasks"][0]
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_task] = lambda: task_row
    client = TestClient(app)

    failing_db = MagicMock()
    failing_db.table.side_effect = RuntimeError("Database write error")

    with patch("backend.routers.tasks.get_supabase_client", return_value=failing_db):
        res = client.put(f"/api/tasks/{TASK_1_ID}", json={"title": "New Title"})

    assert res.status_code == 500
    assert "failed to update" in res.json()["detail"].lower()


def test_get_upcoming_tasks_db_error_returns_500(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    failing_db = MagicMock()
    failing_db.table.side_effect = RuntimeError("Database connection down")

    with patch("backend.routers.tasks.get_supabase_client", return_value=failing_db):
        res = client.get("/api/tasks/upcoming")

    assert res.status_code == 500
    assert "failed to retrieve" in res.json()["detail"].lower()


def test_tasks_db_error_returns_500(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    client = TestClient(app)

    failing_db = MagicMock()
    failing_db.table.side_effect = RuntimeError("Database offline")

    with patch("backend.routers.tasks.get_supabase_client", return_value=failing_db):
        res = client.get("/api/tasks")

    assert res.status_code == 500
    assert "failed to retrieve" in res.json()["detail"].lower()

