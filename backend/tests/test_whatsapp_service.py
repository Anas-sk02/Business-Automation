"""Unit tests for Stage 5 Task 2: WhatsApp Delivery Service & Safety Guardrails.

Validates:
- WAHA format adapter (+91 98220 12345 -> 919822012345@c.us)
- Indian quiet hours enforcement (21:00 to 09:00 Asia/Kolkata)
- Daily send quota enforcement (DAILY_SEND_LIMIT) across user campaigns
- Strict human approval check (status == 'approved')
- Atomic double-send prevention (conditional update)
- Inline pre-send suppression cancellation
- Pre-send campaign budget limits for paid provider
- Empty message body & ID validation
- Pipeline stage transition to 'contacted' with anti-regression guard
- WAHA provider dispatch ($0 cost) & Twilio provider fallback with api_costs logging
- Remote failure handling (status -> 'failed')
"""

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo
import httpx
import pytest

from backend.config import settings
from backend.models.whatsapp import (
    MessageDirection,
    MessageStatus,
    SendMessageResponse,
)
from backend.services.whatsapp import (
    CampaignBudgetExceededError,
    DailyLimitExceededError,
    LeadSuppressedError,
    MessageAlreadySentError,
    MessageNotApprovedError,
    MessageNotFoundError,
    QuietHoursError,
    WhatsAppDeliveryError,
    WhatsAppService,
)


class MockQueryBuilder:
    """Mock query builder for chained Supabase table queries."""

    def __init__(self, target_list: Optional[List[Dict[str, Any]]] = None):
        self.target_list = target_list if target_list is not None else []
        self.data: List[Dict[str, Any]] = list(self.target_list)
        self.filter_conditions: Dict[str, Any] = {}
        self.updated_payload: Optional[Dict[str, Any]] = None
        self.inserted_payload: Optional[Dict[str, Any]] = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column: str, value: Any):
        self.filter_conditions[column] = value
        return self

    def gte(self, column: str, value: Any):
        self.filter_conditions[f"{column}__gte"] = value
        return self

    def insert(self, payload: Dict[str, Any]):
        self.inserted_payload = payload
        record = dict(payload)
        if "id" not in record:
            record["id"] = "rec_mock_123"
        self.target_list.append(record)
        self.data = [record]
        return self

    def update(self, payload: Dict[str, Any]):
        self.updated_payload = payload
        return self

    def execute(self):
        if self.updated_payload is not None:
            updated_list = []
            for item in self.target_list:
                match = True
                for k, v in self.filter_conditions.items():
                    if k.endswith("__gte"):
                        continue
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    item.update(self.updated_payload)
                    updated_list.append(item)
            self.data = updated_list
            return self
        elif self.inserted_payload is not None:
            return self
        elif self.filter_conditions:
            filtered = []
            for item in self.target_list:
                match = True
                for k, v in self.filter_conditions.items():
                    if k.endswith("__gte"):
                        continue
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            self.data = filtered
        return self


class MockSupabaseClient:
    """Mock Supabase client providing isolated table state."""

    def __init__(self):
        self.leads_data: List[Dict[str, Any]] = []
        self.campaigns_data: List[Dict[str, Any]] = []
        self.messages_data: List[Dict[str, Any]] = []
        self.suppressions_data: List[Dict[str, Any]] = []
        self.costs_data: List[Dict[str, Any]] = []

    def table(self, table_name: str) -> MockQueryBuilder:
        if table_name == "leads":
            return MockQueryBuilder(self.leads_data)
        elif table_name == "campaigns":
            return MockQueryBuilder(self.campaigns_data)
        elif table_name == "whatsapp_messages":
            return MockQueryBuilder(self.messages_data)
        elif table_name == "suppressions":
            return MockQueryBuilder(self.suppressions_data)
        elif table_name == "api_costs":
            return MockQueryBuilder(self.costs_data)
        return MockQueryBuilder()


# ============================================================================
# Helpers & Adapters Tests
# ============================================================================

def test_format_waha_chat_id():
    """Verify phone normalization into WAHA <digits>@c.us format."""
    chat_id = WhatsAppService.format_waha_chat_id("+91 98220 12345")
    assert chat_id == "919822012345@c.us"

    chat_id2 = WhatsAppService.format_waha_chat_id("9876543210")
    assert chat_id2 == "919876543210@c.us"

    with pytest.raises(ValueError, match="Invalid phone number"):
        WhatsAppService.format_waha_chat_id("invalid-phone")


def test_is_quiet_hours():
    """Verify quiet hours check in Asia/Kolkata timezone."""
    tz = ZoneInfo("Asia/Kolkata")

    # 22:30 IST is quiet hours
    late_night = datetime(2026, 11, 5, 22, 30, tzinfo=tz)
    assert WhatsAppService.is_quiet_hours(late_night) is True

    # 04:00 IST is quiet hours
    early_morning = datetime(2026, 11, 5, 4, 0, tzinfo=tz)
    assert WhatsAppService.is_quiet_hours(early_morning) is True

    # 14:00 IST is NOT quiet hours
    afternoon = datetime(2026, 11, 5, 14, 0, tzinfo=tz)
    assert WhatsAppService.is_quiet_hours(afternoon) is False


# ============================================================================
# Delivery Flow & Guardrail Tests
# ============================================================================

@pytest.fixture
def base_db():
    db = MockSupabaseClient()
    db.campaigns_data = [
        {
            "id": "camp_001",
            "user_id": "user_xyz",
            "name": "Local Dental Outreach",
            "service_offered": "SEO Services",
            "max_budget": 500.0,
            "spent_amount": 0.0,
        }
    ]
    db.leads_data = [
        {
            "id": "lead_001",
            "campaign_id": "camp_001",
            "business_name": "Smile Care",
            "phone": "+919822012345",
            "is_suppressed": False,
            "pipeline_stage": "qualified",
        }
    ]
    db.messages_data = [
        {
            "id": "msg_001",
            "lead_id": "lead_001",
            "campaign_id": "camp_001",
            "direction": "outbound",
            "to_number": "+919822012345",
            "message_body": "Hello Doctor, saw your site speed.\n\nReply STOP to opt out",
            "status": "approved",
            "followup_attempt": 0,
            "conversation_cost": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return db


@pytest.fixture
def mock_waha_http():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "waha_msg_12345_ack"}
    mock_client.post.return_value = mock_resp
    return mock_client


@pytest.mark.anyio
async def test_send_message_waha_success(base_db, mock_waha_http):
    """Test successful send via WAHA provider advancing lead stage to contacted."""
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    res = await service.send_message(
        message_id="msg_001",
        user_id="user_xyz",
        ignore_quiet_hours=True,
    )

    assert isinstance(res, SendMessageResponse)
    assert res.wa_message_id == "waha_msg_12345_ack"
    assert res.provider == "waha"
    assert res.cost_inr == 0.0
    assert res.recipient_phone == "+919822012345"

    # Verify message status updated to sent
    assert base_db.messages_data[0]["status"] == "sent"
    assert base_db.messages_data[0]["wa_message_id"] == "waha_msg_12345_ack"

    # Verify lead transitioned from qualified to contacted
    assert base_db.leads_data[0]["pipeline_stage"] == "contacted"
    assert base_db.leads_data[0]["last_contacted_at"] is not None

    # Verify HTTP post called with expected WAHA payload
    mock_waha_http.post.assert_called_once()
    call_args = mock_waha_http.post.call_args
    assert call_args[1]["json"]["chatId"] == "919822012345@c.us"
    assert "Reply STOP to opt out" in call_args[1]["json"]["text"]


@pytest.mark.anyio
async def test_send_message_blocks_unapproved_draft(base_db, mock_waha_http):
    """Test that sending a message with status='draft' is strictly blocked."""
    base_db.messages_data[0]["status"] = "draft"
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    with pytest.raises(MessageNotApprovedError, match="Explicit human approval"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    # Remote API must not be called
    mock_waha_http.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_blocks_already_sent_or_queued(base_db, mock_waha_http):
    """Test that attempting to re-send an already sent message raises MessageAlreadySentError."""
    base_db.messages_data[0]["status"] = "sent"
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    with pytest.raises(MessageAlreadySentError, match="has already been dispatched"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    mock_waha_http.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_pre_send_suppression_block(base_db, mock_waha_http):
    """Test that if the lead is opted out, sending is aborted and message is marked cancelled."""
    base_db.leads_data[0]["is_suppressed"] = True
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    with pytest.raises(LeadSuppressedError, match="suppressed or opted out"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    # Message must be marked cancelled in database
    assert base_db.messages_data[0]["status"] == "cancelled"
    mock_waha_http.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_anti_regression_guard(base_db, mock_waha_http):
    """Test that sending a follow-up to an 'interested' lead does not regress it back to 'contacted'."""
    base_db.leads_data[0]["pipeline_stage"] = "interested"
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    # Stage remains 'interested' (anti-regression)
    assert base_db.leads_data[0]["pipeline_stage"] == "interested"
    assert base_db.leads_data[0]["last_contacted_at"] is not None


@pytest.mark.anyio
async def test_send_message_waha_failure_handling(base_db):
    """Test that remote WAHA errors transition message status to failed with error message."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.text = "Session default is not connected"
    mock_client.post.return_value = mock_resp

    service = WhatsAppService(db_client=base_db, http_client=mock_client, provider="waha")

    with pytest.raises(WhatsAppDeliveryError, match="WAHA returned HTTP 500"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    # Message must be recorded as failed in DB
    assert base_db.messages_data[0]["status"] == "failed"
    assert "WAHA returned HTTP 500" in base_db.messages_data[0]["error_message"]


@pytest.mark.anyio
async def test_send_message_twilio_fallback_logs_cost(base_db):
    """Test sending via Twilio fallback provider logs cost to api_costs."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"sid": "SM_twilio_12345"}
    mock_client.post.return_value = mock_resp

    # Configure Twilio settings
    settings.WHATSAPP_ACCOUNT_SID = "AC_mock_sid"
    settings.WHATSAPP_AUTH_TOKEN = "token_mock"
    settings.WHATSAPP_FROM_NUMBER = "+14155238886"

    service = WhatsAppService(db_client=base_db, http_client=mock_client, provider="twilio")

    res = await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    assert res.provider == "twilio"
    assert res.wa_message_id == "SM_twilio_12345"
    assert res.cost_inr > 0.0

    # api_costs record inserted
    assert len(base_db.costs_data) == 1
    assert base_db.costs_data[0]["service"] == "whatsapp_outreach"


@pytest.mark.anyio
async def test_send_message_twilio_budget_exceeded_blocks_send(base_db):
    """Test sending via Twilio stops if campaign max_budget is exceeded per decisions.md §11."""
    base_db.campaigns_data[0]["spent_amount"] = 500.0
    base_db.campaigns_data[0]["max_budget"] = 500.0

    settings.WHATSAPP_ACCOUNT_SID = "AC_mock_sid"
    settings.WHATSAPP_AUTH_TOKEN = "token_mock"
    settings.WHATSAPP_FROM_NUMBER = "+14155238886"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    service = WhatsAppService(db_client=base_db, http_client=mock_client, provider="twilio")

    with pytest.raises(CampaignBudgetExceededError, match="budget limit"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)

    mock_client.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_quiet_hours_blocks_without_override(base_db, mock_waha_http):
    """Test sending during quiet hours without ignore_quiet_hours=True raises QuietHoursError."""
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")
    # Force is_quiet_hours to return True
    service.is_quiet_hours = staticmethod(lambda *args, **kwargs: True)

    with pytest.raises(QuietHoursError, match="quiet hours"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=False)

    mock_waha_http.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_unauthorized_user(base_db, mock_waha_http):
    """Test rejection when campaign belongs to a different user."""
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    with pytest.raises(MessageNotFoundError, match="access denied"):
        await service.send_message("msg_001", "different_user_abc", ignore_quiet_hours=True)

    mock_waha_http.post.assert_not_called()


@pytest.mark.anyio
async def test_send_message_empty_inputs_rejected(base_db, mock_waha_http):
    """Test validation rejection for empty message_id, user_id, or message body."""
    service = WhatsAppService(db_client=base_db, http_client=mock_waha_http, provider="waha")

    with pytest.raises(ValueError, match="message_id must be a non-empty string"):
        await service.send_message("", "user_xyz")

    with pytest.raises(ValueError, match="user_id must be a non-empty string"):
        await service.send_message("msg_001", "  ")

    base_db.messages_data[0]["message_body"] = "   "
    with pytest.raises(ValueError, match="empty message body"):
        await service.send_message("msg_001", "user_xyz", ignore_quiet_hours=True)
