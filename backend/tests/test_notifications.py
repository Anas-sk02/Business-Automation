"""Tests for notifications router, model, and automatic creation triggers."""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import HTTPException
from backend.routers.notifications import (
    create_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from backend.models.notification import NotificationType


@pytest.fixture
def fake_user():
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "test@signalforge.ai",
    }


def test_create_notification_helper_success():
    mock_db = MagicMock()
    insert_mock = MagicMock()
    mock_db.table.return_value.insert.return_value = insert_mock
    notif_id = str(uuid4())
    insert_mock.execute.return_value = MagicMock(data=[{"id": notif_id, "title": "Test"}])

    res = create_notification(
        db=mock_db,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        title="Test Notification",
        message="This is a test notification message",
        notification_type="action_required",
        link_url="/leads/123",
        lead_id=str(uuid4()),
        campaign_id=str(uuid4()),
    )

    assert res is not None
    assert mock_db.table.called
    assert mock_db.table.call_args[0][0] == "notifications"
    inserted_payload = insert_mock.call_args[0][0] if insert_mock.call_args else mock_db.table.return_value.insert.call_args[0][0]
    assert inserted_payload["type"] == "action_required"


def test_create_notification_invalid_type_fallback():
    mock_db = MagicMock()
    insert_mock = MagicMock()
    mock_db.table.return_value.insert.return_value = insert_mock
    insert_mock.execute.return_value = MagicMock(data=[{"id": str(uuid4()), "title": "Test"}])

    res = create_notification(
        db=mock_db,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        title="Test",
        message="Message",
        notification_type="invalid_custom_type",
    )

    assert res is not None
    inserted_payload = mock_db.table.return_value.insert.call_args[0][0]
    assert inserted_payload["type"] == "info"


def test_create_notification_exception_returns_none():
    mock_db = MagicMock()
    mock_db.table.side_effect = RuntimeError("Database down")

    res = create_notification(
        db=mock_db,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        title="Test",
        message="Message",
    )

    assert res is None


def test_create_notification_empty_or_none_user_id():
    mock_db = MagicMock()
    assert create_notification(db=mock_db, user_id=None, title="T", message="M") is None
    assert create_notification(db=mock_db, user_id="", title="T", message="M") is None
    assert create_notification(db=mock_db, user_id="None", title="T", message="M") is None
    assert not mock_db.table.called


@pytest.mark.anyio
async def test_list_notifications_enveloped_empty(monkeypatch, fake_user):
    mock_db = MagicMock()
    select_mock = MagicMock()
    mock_db.table.return_value.select.return_value = select_mock
    select_mock.eq.return_value = select_mock
    select_mock.order.return_value = select_mock
    select_mock.limit.return_value = select_mock
    select_mock.execute.return_value = MagicMock(data=[])

    monkeypatch.setattr("backend.routers.notifications.get_supabase_client", lambda: mock_db)

    res = await list_notifications(unread_only=False, limit=20, current_user=fake_user)
    assert "data" in res
    assert "message" in res
    assert res["data"].total == 0
    assert res["data"].unread_count == 0
    assert res["data"].notifications == []


@pytest.mark.anyio
async def test_list_notifications_with_items(monkeypatch, fake_user):
    mock_db = MagicMock()
    select_mock = MagicMock()
    mock_db.table.return_value.select.return_value = select_mock
    select_mock.eq.return_value = select_mock
    select_mock.order.return_value = select_mock
    select_mock.limit.return_value = select_mock

    now = datetime.now(timezone.utc).isoformat()
    n1_id = uuid4()
    mock_rows = [
        {
            "id": n1_id,
            "user_id": fake_user["id"],
            "title": "New interested reply",
            "message": "Dr. Sharma wants pricing details",
            "type": "action_required",
            "link_url": "/leads/123",
            "lead_id": None,
            "campaign_id": None,
            "is_read": False,
            "created_at": now,
            "read_at": None,
        }
    ]

    # First call: rows query, second call: unread count query
    select_mock.execute.side_effect = [
        MagicMock(data=mock_rows),
        MagicMock(data=[{"id": n1_id}]),
    ]

    monkeypatch.setattr("backend.routers.notifications.get_supabase_client", lambda: mock_db)

    res = await list_notifications(unread_only=False, limit=20, current_user=fake_user)
    assert res["data"].total == 1
    assert res["data"].unread_count == 1
    assert len(res["data"].notifications) == 1
    assert res["data"].notifications[0].title == "New interested reply"


@pytest.mark.anyio
async def test_mark_single_notification_read_success(monkeypatch, fake_user):
    mock_db = MagicMock()
    notif_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    existing_row = {
        "id": notif_id,
        "user_id": fake_user["id"],
        "title": "Meeting scheduled",
        "message": "Discovery call at 4pm",
        "type": "success",
        "link_url": "/leads/123",
        "lead_id": None,
        "campaign_id": None,
        "is_read": False,
        "created_at": now,
        "read_at": None,
    }
    updated_row = dict(existing_row, is_read=True, read_at=now)

    select_mock = MagicMock()
    mock_db.table.return_value.select.return_value = select_mock
    select_mock.eq.return_value = select_mock
    select_mock.execute.return_value = MagicMock(data=[existing_row])

    update_mock = MagicMock()
    mock_db.table.return_value.update.return_value = update_mock
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[updated_row])

    monkeypatch.setattr("backend.routers.notifications.get_supabase_client", lambda: mock_db)

    res = await mark_notification_read(notification_id=notif_id, current_user=fake_user)
    assert res["data"].is_read is True
    assert res["data"].read_at is not None
    assert res["message"] == "Notification marked as read"


@pytest.mark.anyio
async def test_mark_single_notification_read_not_found(monkeypatch, fake_user):
    mock_db = MagicMock()
    notif_id = uuid4()

    select_mock = MagicMock()
    mock_db.table.return_value.select.return_value = select_mock
    select_mock.eq.return_value = select_mock
    select_mock.execute.return_value = MagicMock(data=[])

    monkeypatch.setattr("backend.routers.notifications.get_supabase_client", lambda: mock_db)

    with pytest.raises(HTTPException) as exc_info:
        await mark_notification_read(notification_id=notif_id, current_user=fake_user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Notification not found"


@pytest.mark.anyio
async def test_mark_all_notifications_read(monkeypatch, fake_user):
    mock_db = MagicMock()
    select_mock = MagicMock()
    mock_db.table.return_value.select.return_value = select_mock
    select_mock.eq.return_value = select_mock
    select_mock.execute.return_value = MagicMock(data=[{"id": "n1"}, {"id": "n2"}])

    update_mock = MagicMock()
    mock_db.table.return_value.update.return_value = update_mock
    update_mock.in_.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])

    monkeypatch.setattr("backend.routers.notifications.get_supabase_client", lambda: mock_db)

    res = await mark_all_notifications_read(current_user=fake_user)
    assert res["data"].success is True
    assert res["data"].marked_count == 2
    assert "Marked 2 notifications as read" in res["message"]
