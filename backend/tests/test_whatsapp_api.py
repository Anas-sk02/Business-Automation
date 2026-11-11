"""Integration tests for Stage 5 Task 4: WhatsApp Router Endpoints.

Validates:
- POST /api/leads/{id}/whatsapp/draft (Generate outreach draft)
- GET /api/leads/{id}/whatsapp/draft (Get current active draft)
- PUT /api/leads/{id}/whatsapp/draft (Update draft text and approval status)
- POST /api/leads/{id}/whatsapp/send (Send approved message with guardrails)
- GET /api/leads/{id}/whatsapp/messages (Get conversation timeline)
- POST /api/webhooks/whatsapp (Public webhook receiver for delivery receipts and inbound replies)
- GET /api/webhooks/whatsapp (Meta webhook handshake challenge)
- Authentication enforcement (401 Unauthorized on protected routes)
- Tenant isolation (404 Not Found on unowned leads)
- Standard response envelope format ({"data": ..., "message": "..."})
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_lead
from backend.models.whatsapp import (
    MessageDirection,
    MessageStatus,
    MessageType,
    SendMessageResponse,
    WhatsAppDraftResponse,
    WhatsAppMessageResponse,
)


VALID_LEAD_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
VALID_CAMPAIGN_ID = "4fa85f64-5717-4562-b3fc-2c963f66afa7"


@pytest.fixture
def auth_user():
    return {"id": "user-uuid-123", "email": "doctor@signalforge.ai"}


@pytest.fixture
def mock_lead():
    return {
        "id": VALID_LEAD_ID,
        "campaign_id": VALID_CAMPAIGN_ID,
        "business_name": "Apex Physio Clinic",
        "phone": "+919876543210",
        "is_suppressed": False,
        "pipeline_stage": "qualified",
    }


@pytest.fixture
def client(auth_user, mock_lead):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_owned_lead] = lambda: mock_lead
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_draft_response():
    msg = WhatsAppMessageResponse(
        id="msg-uuid-001",
        lead_id=VALID_LEAD_ID,
        campaign_id=VALID_CAMPAIGN_ID,
        direction=MessageDirection.OUTBOUND,
        to_number="+919876543210",
        message_body="Hi Dr. Apex Team, noticed your site is slow.\n\nReply STOP to opt out",
        message_type=MessageType.TEXT,
        status=MessageStatus.DRAFT,
        created_at=datetime.now(timezone.utc),
    )
    return WhatsAppDraftResponse(
        message=msg,
        lead_id=VALID_LEAD_ID,
        lead_name="Apex Physio Clinic",
        recipient_phone="+919876543210",
        evidence_cited=["Slow mobile LCP"],
        estimated_cost_inr=0.01,
        status=MessageStatus.DRAFT,
    )


# ============================================================================
# 1. Draft Management Endpoints
# ============================================================================

def test_generate_draft_endpoint_success(client, sample_draft_response):
    """Test POST /api/leads/{id}/whatsapp/draft generates draft successfully."""
    with patch(
        "backend.routers.whatsapp.MessageGeneratorService.generate_draft",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = sample_draft_response

        response = client.post(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft",
            json={"instructions": "Keep it friendly"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Outreach draft generated successfully"
        assert data["data"]["lead_name"] == "Apex Physio Clinic"
        assert "Reply STOP to opt out" in data["data"]["message"]["message_body"]


def test_get_draft_endpoint_success(client, sample_draft_response):
    """Test GET /api/leads/{id}/whatsapp/draft retrieves existing active draft."""
    with patch(
        "backend.routers.whatsapp.MessageGeneratorService.get_draft",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = sample_draft_response

        response = client.get(f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Draft retrieved successfully"
        assert data["data"]["message"]["id"] == "msg-uuid-001"


def test_get_draft_endpoint_not_found(client):
    """Test GET /api/leads/{id}/whatsapp/draft returns 404 when no draft exists."""
    with patch(
        "backend.routers.whatsapp.MessageGeneratorService.get_draft",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = None

        response = client.get(f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft")
        assert response.status_code == 404


def test_update_draft_endpoint_success(client, sample_draft_response):
    """Test PUT /api/leads/{id}/whatsapp/draft updates draft text and status."""
    with patch(
        "backend.routers.whatsapp.MessageGeneratorService.update_draft",
        new_callable=AsyncMock,
    ) as mock_update:
        # Simulate updated approved draft
        updated_draft = sample_draft_response.model_copy(deep=True)
        updated_draft.status = MessageStatus.APPROVED
        updated_draft.message.status = MessageStatus.APPROVED
        updated_draft.message.message_body = "Custom edited message text.\n\nReply STOP to opt out"
        mock_update.return_value = updated_draft

        response = client.put(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft",
            json={
                "message_body": "Custom edited message text.\n\nReply STOP to opt out",
                "status": "approved",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "approved"
        assert "Custom edited message text." in data["data"]["message"]["message_body"]


# ============================================================================
# 2. Send Message Endpoint
# ============================================================================

def test_send_whatsapp_message_endpoint_success(client):
    """Test POST /api/leads/{id}/whatsapp/send successfully dispatches approved message."""
    sent_msg = WhatsAppMessageResponse(
        id="msg-uuid-001",
        lead_id=VALID_LEAD_ID,
        campaign_id=VALID_CAMPAIGN_ID,
        direction=MessageDirection.OUTBOUND,
        to_number="+919876543210",
        message_body="Approved body.\n\nReply STOP to opt out",
        status=MessageStatus.SENT,
        wa_message_id="waha_ack_12345",
        created_at=datetime.now(timezone.utc),
        sent_at=datetime.now(timezone.utc),
    )
    send_res = SendMessageResponse(
        message=sent_msg,
        lead_id=VALID_LEAD_ID,
        recipient_phone="+919876543210",
        provider="waha",
        wa_message_id="waha_ack_12345",
        sent_at=datetime.now(timezone.utc),
        cost_inr=0.0,
    )

    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.order.return_value = builder
    builder.execute.return_value = MagicMock(data=[{"id": "msg-uuid-001", "status": "approved"}])
    mock_db = MagicMock()
    mock_db.table.return_value = builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db), \
         patch("backend.routers.whatsapp.WhatsAppService.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = send_res

        response = client.post(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/send",
            json={"ignore_quiet_hours": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Message sent successfully"
        assert data["data"]["wa_message_id"] == "waha_ack_12345"
        assert data["data"]["provider"] == "waha"


def test_send_whatsapp_message_unapproved_returns_400(client):
    """Test POST /api/leads/{id}/whatsapp/send blocks sending when draft is unapproved."""
    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.order.return_value = builder
    builder.execute.return_value = MagicMock(data=[{"id": "msg-uuid-001", "status": "draft"}])
    mock_db = MagicMock()
    mock_db.table.return_value = builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db):
        response = client.post(f"/api/leads/{VALID_LEAD_ID}/whatsapp/send")
        assert response.status_code == 400
        assert "has not been approved yet" in response.json()["detail"]


# ============================================================================
# 3. Conversation Timeline Endpoint
# ============================================================================

def test_get_lead_whatsapp_messages_timeline(client):
    """Test GET /api/leads/{id}/whatsapp/messages retrieves conversation timeline."""
    now = datetime.now(timezone.utc).isoformat()
    mock_records = [
        {
            "id": "msg-01",
            "lead_id": VALID_LEAD_ID,
            "campaign_id": VALID_CAMPAIGN_ID,
            "direction": "outbound",
            "message_body": "Hello Doctor.\n\nReply STOP to opt out",
            "status": "sent",
            "created_at": now,
        },
        {
            "id": "msg-02",
            "lead_id": VALID_LEAD_ID,
            "campaign_id": VALID_CAMPAIGN_ID,
            "direction": "inbound",
            "message_body": "Yes tell me more",
            "status": "read",
            "reply_classification": "interested",
            "created_at": now,
        },
    ]
    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.order.return_value = builder
    builder.execute.return_value = MagicMock(data=mock_records)
    mock_db = MagicMock()
    mock_db.table.return_value = builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db):
        response = client.get(f"/api/leads/{VALID_LEAD_ID}/whatsapp/messages")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2
        assert data[0]["direction"] == "outbound"
        assert data[1]["direction"] == "inbound"
        assert data[1]["reply_classification"] == "interested"


# ============================================================================
# 4. Authentication & Tenant Isolation
# ============================================================================

def test_protected_routes_require_jwt(unauth_client):
    """Verify protected routes reject unauthenticated requests with 401."""
    res1 = unauth_client.post(f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft")
    assert res1.status_code == 401

    res2 = unauth_client.get(f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft")
    assert res2.status_code == 401

    res3 = unauth_client.post(f"/api/leads/{VALID_LEAD_ID}/whatsapp/send")
    assert res3.status_code == 401

    res4 = unauth_client.get(f"/api/leads/{VALID_LEAD_ID}/whatsapp/messages")
    assert res4.status_code == 401

    res5 = unauth_client.get("/api/whatsapp/session/status")
    assert res5.status_code == 401

    res6 = unauth_client.post("/api/whatsapp/session/start")
    assert res6.status_code == 401

    res7 = unauth_client.get("/api/whatsapp/session/qr")
    assert res7.status_code == 401

    res8 = unauth_client.post("/api/whatsapp/session/logout")
    assert res8.status_code == 401


# ============================================================================
# 5. Public Webhooks
# ============================================================================

def test_public_webhook_post_receiver_no_jwt_needed(unauth_client):
    """Verify POST /api/webhooks/whatsapp is public and processes WAHA delivery receipts."""
    with patch(
        "backend.routers.whatsapp.WebhookProcessorService.process_waha_webhook",
        new_callable=AsyncMock,
    ) as mock_waha:
        from backend.models.whatsapp import WebhookProcessResult

        mock_waha.return_value = WebhookProcessResult(
            event_type="delivery_receipt",
            wa_message_id="waha_ack_999",
            status="delivered",
        )

        payload = {"event": "message.ack", "id": "waha_ack_999", "ack": 2}
        response = unauth_client.post("/api/webhooks/whatsapp", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["data"]["status"] == "delivered"


def test_meta_webhook_challenge_get_endpoint(unauth_client):
    """Verify GET /api/webhooks/whatsapp responds with challenge string for Meta verification."""
    response = unauth_client.get(
        "/api/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "challenge_string_12345",
            "hub.verify_token": "token_xyz",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge_string_12345"


# ============================================================================
# 6. Security, Error Handling & Safeguard Tests
# ============================================================================

def test_send_whatsapp_message_cross_lead_mismatch_returns_404(client):
    """Verify specifying a message_id belonging to another lead or campaign returns 404."""
    mock_db = MagicMock()
    # Mock query returning empty because message does not match lead_id / campaign_id
    mock_builder = MagicMock()
    mock_builder.select.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.execute.return_value = MagicMock(data=[])
    mock_db.table.return_value = mock_builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db):
        response = client.post(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/send",
            json={"message_id": "other-lead-msg-uuid"},
        )
        assert response.status_code == 404
        assert "not found for lead" in response.json()["detail"]


def test_send_whatsapp_message_quiet_hours_returns_422(client):
    """Verify sending during quiet hours without override returns 422 Unprocessable Entity."""
    from backend.services.whatsapp import QuietHoursError

    mock_db = MagicMock()
    mock_builder = MagicMock()
    mock_builder.select.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.execute.return_value = MagicMock(data=[{"id": "msg-001", "status": "approved"}])
    mock_db.table.return_value = mock_builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db), \
         patch("backend.routers.whatsapp.WhatsAppService.send_message", side_effect=QuietHoursError("Quiet hours in effect")):
        response = client.post(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/send",
            json={"message_id": "msg-001", "ignore_quiet_hours": False},
        )
        assert response.status_code == 422
        assert "Quiet hours" in response.json()["detail"]


def test_send_whatsapp_message_daily_limit_returns_429(client):
    """Verify daily send limit enforcement returns 429 Too Many Requests."""
    from backend.services.whatsapp import DailyLimitExceededError

    mock_db = MagicMock()
    mock_builder = MagicMock()
    mock_builder.select.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.execute.return_value = MagicMock(data=[{"id": "msg-001", "status": "approved"}])
    mock_db.table.return_value = mock_builder

    with patch("backend.routers.whatsapp.get_supabase_client", return_value=mock_db), \
         patch("backend.routers.whatsapp.WhatsAppService.send_message", side_effect=DailyLimitExceededError("Daily limit reached")):
        response = client.post(
            f"/api/leads/{VALID_LEAD_ID}/whatsapp/send",
            json={"message_id": "msg-001"},
        )
        assert response.status_code == 429
        assert "Daily limit" in response.json()["detail"]


def test_generate_draft_budget_exceeded_returns_402(client):
    """Verify generating draft when campaign budget is exhausted returns 402 Payment Required."""
    from backend.services.message_generator import CampaignBudgetExceededError

    with patch(
        "backend.routers.whatsapp.MessageGeneratorService.generate_draft",
        side_effect=CampaignBudgetExceededError("Budget exhausted"),
    ):
        response = client.post(f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft")
        assert response.status_code == 402
        assert "Budget exhausted" in response.json()["detail"]


def test_update_draft_whitespace_body_fails_validation(client):
    """Verify draft updates with only whitespace fail validation with 422."""
    response = client.put(
        f"/api/leads/{VALID_LEAD_ID}/whatsapp/draft",
        json={"message_body": "   \n\t  "},
    )
    assert response.status_code == 422


def test_public_webhook_error_handled_gracefully(unauth_client):
    """Verify webhook errors do not crash with 500 and return status error with 200."""
    with patch(
        "backend.routers.whatsapp.WebhookProcessorService.process_waha_webhook",
        side_effect=RuntimeError("Corrupt payload"),
    ):
        payload = {"event": "message.ack", "corrupted": True}
        response = unauth_client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Corrupt payload" in data["message"]


def test_get_whatsapp_session_status_endpoint(client):
    """Verify getting user's isolated WhatsApp session status."""
    mock_status = {
        "session_name": "user_useruuid123",
        "status": "WORKING",
        "connected": True,
        "phone_number": "918087215103",
        "push_name": "Test User",
    }
    with patch("backend.routers.whatsapp.WhatsAppService.get_session_status", new_callable=AsyncMock) as mock_stat:
        mock_stat.return_value = mock_status
        response = client.get("/api/whatsapp/session/status")
        assert response.status_code == 200
        res = response.json()
        assert res["data"]["connected"] is True
        assert res["data"]["phone_number"] == "918087215103"
        assert res["data"]["session_name"] == "user_useruuid123"


def test_start_whatsapp_session_endpoint(client):
    """Verify starting user's isolated WhatsApp session."""
    mock_res = {
        "session_name": "user_useruuid123",
        "status": "SCAN_QR_CODE",
        "connected": False,
        "phone_number": None,
        "push_name": None,
    }
    with patch("backend.routers.whatsapp.WhatsAppService.start_session", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = mock_res
        response = client.post("/api/whatsapp/session/start")
        assert response.status_code == 200
        res = response.json()
        assert res["data"]["status"] == "SCAN_QR_CODE"
        assert res["data"]["connected"] is False


def test_get_whatsapp_qr_code_endpoint(client):
    """Verify fetching QR code for pairing."""
    with patch("backend.routers.whatsapp.WhatsAppService.get_session_qr", new_callable=AsyncMock) as mock_qr, \
         patch("backend.routers.whatsapp.WhatsAppService.get_session_status", new_callable=AsyncMock) as mock_stat:
        mock_qr.return_value = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
        mock_stat.return_value = {"status": "SCAN_QR_CODE"}
        response = client.get("/api/whatsapp/session/qr")
        assert response.status_code == 200
        res = response.json()
        assert res["data"]["qr_code"] == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
        assert res["data"]["status"] == "SCAN_QR_CODE"


def test_logout_whatsapp_session_endpoint(client):
    """Verify disconnecting user's WhatsApp session."""
    with patch("backend.routers.whatsapp.WhatsAppService.logout_session", new_callable=AsyncMock) as mock_logout:
        mock_logout.return_value = True
        response = client.post("/api/whatsapp/session/logout")
        assert response.status_code == 200
        res = response.json()
        assert res["data"]["success"] is True



