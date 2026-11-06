"""Tests for APScheduler Background Scheduler and Lifespan Integration (Stage 6 Task 2)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.scheduler import (
    get_scheduler,
    run_followup_check_job,
    run_stale_jobs_recovery_job,
    run_unsnooze_tasks_job,
    start_scheduler,
    stop_scheduler,
)


class FakeQuery:
    def __init__(self, data=None):
        self._data = data if data is not None else []
        self._filters = []
        self._update_data = None

    def select(self, *args, **kwargs):
        return self

    def update(self, payload):
        self._update_data = payload
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def lte(self, col, val):
        return self

    def in_(self, col, vals):
        return self

    def execute(self):
        if self._update_data is not None:
            for item in self._data:
                item.update(self._update_data)
            return MagicMock(data=self._data)
        return MagicMock(data=self._data)


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def set_table(self, name, data):
        self.tables[name] = data

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


@pytest.fixture(autouse=True)
def cleanup_scheduler():
    """Ensure scheduler is cleanly stopped after each test."""
    yield
    stop_scheduler()


# -----------------------------------------------------------------------------
# 1. Lifecycle and Job Registration Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_scheduler_registration_and_lifecycle():
    scheduler = start_scheduler(
        followup_interval_hours=2,
        recovery_interval_minutes=10,
        unsnooze_interval_minutes=15,
    )
    assert scheduler.running is True

    # Verify all 3 jobs are registered
    assert scheduler.get_job("job_check_followups") is not None
    assert scheduler.get_job("job_stale_recovery") is not None
    assert scheduler.get_job("job_unsnooze_tasks") is not None

    # Idempotent start
    same_scheduler = start_scheduler()
    assert same_scheduler is scheduler

    # Shutdown
    stop_scheduler()
    assert get_scheduler().running is False


# -----------------------------------------------------------------------------
# 2. Follow-up Job Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_run_followup_check_job_success():
    with patch("backend.services.followup.FollowupService.check_pending_followups", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {
            "checked": 3,
            "drafted": 2,
            "cancelled": 1,
            "deferred": 0,
            "exhausted": 0,
            "errors": 0,
        }
        res = await run_followup_check_job()

        assert res["checked"] == 3
        assert res["drafted"] == 2
        mock_check.assert_awaited_once()


@pytest.mark.anyio
async def test_run_followup_check_job_error_resilience():
    with patch("backend.services.followup.FollowupService.check_pending_followups", new_callable=AsyncMock) as mock_check:
        mock_check.side_effect = RuntimeError("Database connection timed out")
        res = await run_followup_check_job()

        assert "error" in res
        assert "Database connection timed out" in res["error"]


# -----------------------------------------------------------------------------
# 3. Stale Jobs Recovery Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_run_stale_jobs_recovery_job():
    with patch("backend.main.recover_stale_discovery_jobs", new_callable=AsyncMock) as mock_disc, \
         patch("backend.main.recover_stale_audit_jobs", new_callable=AsyncMock) as mock_audit:
        mock_disc.return_value = 1
        mock_audit.return_value = 2

        res = await run_stale_jobs_recovery_job()
        assert res["discovery_recovered"] == 1
        assert res["audit_recovered"] == 2
        mock_disc.assert_awaited_once()
        mock_audit.assert_awaited_once()


@pytest.mark.anyio
async def test_run_stale_jobs_recovery_job_error_resilience():
    with patch("backend.main.recover_stale_discovery_jobs", new_callable=AsyncMock) as mock_disc:
        mock_disc.side_effect = Exception("Unexpected recovery failure")
        res = await run_stale_jobs_recovery_job()
        assert "error" in res


# -----------------------------------------------------------------------------
# 4. Unsnooze Tasks Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_run_unsnooze_tasks_job_resets_expired_tasks():
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db = FakeSupabase()
    db.set_table("tasks", [
        {
            "id": "task_snoozed_1",
            "user_id": "user_111",
            "status": "snoozed",
            "snoozed_until": past_iso,
        },
        {
            "id": "task_snoozed_2",
            "user_id": "user_222",
            "status": "snoozed",
            "snoozed_until": past_iso,
        },
    ])

    unsnoozed_count = await run_unsnooze_tasks_job(db_client=db)
    assert unsnoozed_count == 2
    tasks = db.tables["tasks"]
    assert tasks[0]["status"] == "pending"
    assert tasks[0]["snoozed_until"] is None
    assert tasks[1]["status"] == "pending"
    assert tasks[1]["snoozed_until"] is None


@pytest.mark.anyio
async def test_run_unsnooze_tasks_job_tenant_scoping():
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db = FakeSupabase()
    db.set_table("tasks", [
        {
            "id": "task_snoozed_user1",
            "user_id": "user_111",
            "status": "snoozed",
            "snoozed_until": past_iso,
        },
    ])

    # Calling with user_111 unsnoozes
    count = await run_unsnooze_tasks_job(db_client=db, user_id="user_111")
    assert count == 1


@pytest.mark.anyio
async def test_run_unsnooze_tasks_job_error_resilience():
    mock_db = MagicMock()
    mock_db.table.side_effect = RuntimeError("Database offline")
    count = await run_unsnooze_tasks_job(db_client=mock_db)
    assert count == 0


@pytest.mark.anyio
async def test_run_unsnooze_tasks_job_no_tasks():
    db = FakeSupabase()
    db.set_table("tasks", [])
    count = await run_unsnooze_tasks_job(db_client=db)
    assert count == 0


# -----------------------------------------------------------------------------
# 5. FastAPI Lifespan Integration Test
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fastapi_lifespan_starts_and_stops_scheduler():
    from backend.main import lifespan, app

    with patch("backend.main.recover_stale_discovery_jobs", new_callable=AsyncMock), \
         patch("backend.main.recover_stale_audit_jobs", new_callable=AsyncMock):
        async with lifespan(app):
            sched = get_scheduler()
            assert sched.running is True

        assert get_scheduler().running is False
