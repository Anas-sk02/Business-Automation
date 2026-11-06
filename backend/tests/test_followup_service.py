"""Tests for FollowupService and outreach lifecycle management (Stage 6 Task 1)."""

import pytest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.whatsapp import (
    MessageDirection,
    MessageStatus,
    MessageType,
    WhatsAppDraftResponse,
    WhatsAppMessageResponse,
)
from backend.services.followup import FollowupService, TIMEZONE_IST


class FakeQuery:
    def __init__(self, data=None):
        self._data = data if data is not None else []
        self._filters = []
        self._limit = None
        self._order_by = None
        self._update_data = None

    def select(self, *args, **kwargs):
        return self

    def insert(self, payload):
        if isinstance(payload, list):
            return FakeQuery([dict(item, id=item.get("id", f"gen_{i}")) for i, item in enumerate(payload)])
        return FakeQuery([dict(payload, id=payload.get("id", "gen_new_id"))])

    def update(self, payload):
        self._update_data = payload
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def lte(self, col, val):
        return self

    def gt(self, col, val):
        return self

    def is_(self, col, val):
        return self

    def in_(self, col, val):
        return self

    def order(self, col, desc=False):
        self._order_by = (col, desc)
        return self

    def limit(self, count):
        self._limit = count
        return self

    def execute(self):
        if self._update_data is not None:
            updated = []
            for item in self._data:
                item.update(self._update_data)
                updated.append(item)
            return MagicMock(data=updated)
        return MagicMock(data=self._data)


class FakeSupabaseClient:
    def __init__(self):
        self.tables = {}

    def set_table_data(self, table_name: str, rows):
        self.tables[table_name] = rows

    def table(self, table_name: str):
        data = self.tables.get(table_name, [])
        return FakeQuery(data)


@pytest.fixture
def fake_db():
    client = FakeSupabaseClient()
    client.set_table_data("leads", [{
        "id": "lead_123",
        "campaign_id": "camp_456",
        "business_name": "Apex Dental Clinic",
        "phone": "+919822012345",
        "pipeline_stage": "contacted",
        "is_suppressed": False,
        "next_followup_at": None,
    }])
    client.set_table_data("campaigns", [{
        "id": "camp_456",
        "user_id": "user_789",
        "name": "Local Dentists Outreach",
        "whatsapp_settings": {
            "followup_gap_days": 3,
            "max_followup_attempts": 3,
        },
    }])
    client.set_table_data("followup_schedules", [])
    client.set_table_data("whatsapp_messages", [])
    client.set_table_data("tasks", [])
    return client


# -----------------------------------------------------------------------------
# 1. Quiet Hours Tests
# -----------------------------------------------------------------------------

def test_is_quiet_hours():
    # 10:00 PM IST (22:00 IST = 16:30 UTC) -> Quiet
    quiet_dt = datetime(2026, 11, 6, 16, 30, tzinfo=timezone.utc)
    assert FollowupService.is_quiet_hours(quiet_dt) is True

    # 3:00 AM IST (21:30 UTC previous day) -> Quiet
    quiet_early_dt = datetime(2026, 11, 5, 21, 30, tzinfo=timezone.utc)
    assert FollowupService.is_quiet_hours(quiet_early_dt) is True

    # 2:00 PM IST (08:30 UTC) -> Active hours (Not quiet)
    active_dt = datetime(2026, 11, 6, 8, 30, tzinfo=timezone.utc)
    assert FollowupService.is_quiet_hours(active_dt) is False


def test_adjust_for_quiet_hours():
    # If in active hours (11:00 AM IST), no shift
    active_dt = datetime(2026, 11, 6, 5, 30, tzinfo=timezone.utc)  # 11:00 AM IST
    adjusted = FollowupService.adjust_for_quiet_hours(active_dt)
    assert adjusted == active_dt

    # If in late evening quiet hours (10:00 PM IST = 16:30 UTC), deferred to tomorrow 09:30 AM IST (04:00 UTC)
    night_dt = datetime(2026, 11, 6, 16, 30, tzinfo=timezone.utc)
    adj_night = FollowupService.adjust_for_quiet_hours(night_dt)
    ist_adj = adj_night.astimezone(TIMEZONE_IST)
    assert ist_adj.time() == time(9, 30)
    assert ist_adj.day == 7


# -----------------------------------------------------------------------------
# 2. Scheduling Follow-ups Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_schedule_followups_success(fake_db):
    svc = FollowupService(db_client=fake_db)
    schedules = await svc.schedule_followups("lead_123", "camp_456")

    assert len(schedules) == 3
    assert schedules[0]["attempt_number"] == 1
    assert schedules[1]["attempt_number"] == 2
    assert schedules[2]["attempt_number"] == 3
    assert schedules[0]["status"] == "pending"


@pytest.mark.anyio
async def test_schedule_followups_skips_suppressed_or_advanced_lead(fake_db):
    fake_db.set_table_data("leads", [{
        "id": "lead_supp",
        "campaign_id": "camp_456",
        "pipeline_stage": "opted_out",
        "is_suppressed": True,
    }])
    svc = FollowupService(db_client=fake_db)
    schedules = await svc.schedule_followups("lead_supp", "camp_456")
    assert schedules == []


# -----------------------------------------------------------------------------
# 3. Cancellation Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_cancel_followups_on_reply(fake_db):
    fake_db.set_table_data("followup_schedules", [
        {"id": "fs_1", "lead_id": "lead_123", "status": "pending", "attempt_number": 1},
        {"id": "fs_2", "lead_id": "lead_123", "status": "pending", "attempt_number": 2},
    ])
    svc = FollowupService(db_client=fake_db)
    count = await svc.cancel_followups("lead_123", reason="lead_replied")
    assert count == 2


# -----------------------------------------------------------------------------
# 4. Check Pending Follow-ups Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_check_pending_followups_creates_draft_and_task(fake_db):
    now_past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    fake_db.set_table_data("followup_schedules", [
        {
            "id": "sched_due",
            "lead_id": "lead_123",
            "campaign_id": "camp_456",
            "attempt_number": 1,
            "status": "pending",
            "scheduled_for": now_past,
        }
    ])

    mock_msg_gen = MagicMock()
    mock_msg = WhatsAppMessageResponse(
        id="msg_draft_1",
        lead_id="lead_123",
        campaign_id="camp_456",
        direction=MessageDirection.OUTBOUND,
        message_body="Just checking in! Reply STOP to opt out",
        message_type=MessageType.TEXT,
        status=MessageStatus.DRAFT,
        followup_attempt=1,
        is_followup=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_msg_gen.generate_draft = AsyncMock(return_value=WhatsAppDraftResponse(
        message=mock_msg,
        lead_id="lead_123",
        lead_name="Apex Dental Clinic",
        recipient_phone="+919822012345",
        evidence_cited=[],
        estimated_cost_inr=0.05,
        status=MessageStatus.DRAFT,
    ))

    svc = FollowupService(db_client=fake_db, message_generator=mock_msg_gen)

    # Patch is_quiet_hours to return False during test
    with patch.object(FollowupService, "is_quiet_hours", return_value=False):
        stats = await svc.check_pending_followups()

    assert stats["checked"] == 1
    assert stats["drafted"] == 1
    mock_msg_gen.generate_draft.assert_awaited_once_with(
        lead_id="lead_123",
        user_id="user_789",
        followup_attempt=1,
    )


@pytest.mark.anyio
async def test_check_pending_followups_defers_during_quiet_hours(fake_db):
    now_past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    fake_db.set_table_data("followup_schedules", [
        {
            "id": "sched_due",
            "lead_id": "lead_123",
            "campaign_id": "camp_456",
            "attempt_number": 1,
            "status": "pending",
            "scheduled_for": now_past,
        }
    ])

    svc = FollowupService(db_client=fake_db)

    # Patch is_quiet_hours to return True
    with patch.object(FollowupService, "is_quiet_hours", return_value=True):
        stats = await svc.check_pending_followups()

    assert stats["checked"] == 1
    assert stats["deferred"] == 1
    assert stats["drafted"] == 0


@pytest.mark.anyio
async def test_check_pending_followups_cancels_if_lead_already_replied(fake_db):
    now_past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    fake_db.set_table_data("leads", [{
        "id": "lead_123",
        "campaign_id": "camp_456",
        "pipeline_stage": "interested",  # Already replied positively!
        "is_suppressed": False,
    }])
    fake_db.set_table_data("followup_schedules", [
        {
            "id": "sched_due",
            "lead_id": "lead_123",
            "campaign_id": "camp_456",
            "attempt_number": 1,
            "status": "pending",
            "scheduled_for": now_past,
        }
    ])

    svc = FollowupService(db_client=fake_db)
    with patch.object(FollowupService, "is_quiet_hours", return_value=False):
        stats = await svc.check_pending_followups()

    assert stats["checked"] == 1
    assert stats["cancelled"] == 1
    assert stats["drafted"] == 0


@pytest.mark.anyio
async def test_check_pending_followups_idempotent_duplicate_prevention(fake_db):
    now_past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    fake_db.set_table_data("followup_schedules", [
        {
            "id": "sched_due",
            "lead_id": "lead_123",
            "campaign_id": "camp_456",
            "attempt_number": 1,
            "status": "pending",
            "scheduled_for": now_past,
        }
    ])
    # Outbound message already exists for attempt 1
    fake_db.set_table_data("whatsapp_messages", [
        {
            "id": "existing_msg_1",
            "lead_id": "lead_123",
            "direction": "outbound",
            "followup_attempt": 1,
            "status": "draft",
        }
    ])

    mock_msg_gen = MagicMock()
    mock_msg_gen.generate_draft = AsyncMock()
    svc = FollowupService(db_client=fake_db, message_generator=mock_msg_gen)

    with patch.object(FollowupService, "is_quiet_hours", return_value=False):
        stats = await svc.check_pending_followups()

    assert stats["checked"] == 1
    assert stats["drafted"] == 0
    mock_msg_gen.generate_draft.assert_not_called()


@pytest.mark.anyio
async def test_schedule_followups_mismatched_campaign_raises(fake_db):
    svc = FollowupService(db_client=fake_db)
    # lead_123 belongs to camp_456, passing wrong_camp should fail validation
    with pytest.raises(ValueError, match="does not belong to campaign"):
        await svc.schedule_followups("lead_123", "wrong_camp_999")


@pytest.mark.anyio
async def test_schedule_followups_unowned_campaign_raises(fake_db):
    svc = FollowupService(db_client=fake_db)
    # camp_456 belongs to user_789, passing unowned_user should fail validation
    with pytest.raises(ValueError, match="does not belong to user"):
        await svc.schedule_followups("lead_123", "camp_456", user_id="unauthorized_user_666")


@pytest.mark.anyio
async def test_check_exhausted_leads_transitions_to_no_response(fake_db):
    six_days_ago = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    fake_db.set_table_data("leads", [{
        "id": "lead_exhausted",
        "campaign_id": "camp_456",
        "pipeline_stage": "contacted",
        "last_contacted_at": six_days_ago,
        "next_followup_at": None,
    }])
    # All schedules completed/sent
    fake_db.set_table_data("followup_schedules", [
        {"id": "fs_1", "lead_id": "lead_exhausted", "status": "sent", "attempt_number": 1},
        {"id": "fs_2", "lead_id": "lead_exhausted", "status": "sent", "attempt_number": 2},
        {"id": "fs_3", "lead_id": "lead_exhausted", "status": "sent", "attempt_number": 3},
    ])

    svc = FollowupService(db_client=fake_db)
    count = await svc._check_exhausted_leads()
    assert count == 1
    assert fake_db.tables["leads"][0]["pipeline_stage"] == "no_response"


@pytest.mark.anyio
async def test_cancel_followups_scoped_to_campaign(fake_db):
    fake_db.set_table_data("followup_schedules", [
        {"id": "fs_1", "lead_id": "lead_123", "campaign_id": "camp_456", "status": "pending", "attempt_number": 1},
    ])
    svc = FollowupService(db_client=fake_db)
    cancelled = await svc.cancel_followups("lead_123", reason="opted_out", campaign_id="camp_456")
    assert cancelled == 1

