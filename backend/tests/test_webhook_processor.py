"""Unit tests for Stage 5 Task 3: Inbound Webhook Processor & Reply Classifier.

Validates:
- Strict keyword opt-out detection (stop, unsubscribe, band karo, mat bhejo, nahi chahiye)
- Phone extraction and normalization from WAHA JID and Twilio formats
- Delivery receipt processing (WAHA message.ack & Twilio MessageStatus)
- Inbound reply deduplication and idempotency via wa_message_id
- AI reply classification for positive responses (interested, pricing_request, meeting_request)
- Low confidence (< 0.7) and ambiguous reply fallback to 'replied' stage + manual review task
- Cross-lead phone suppression and follow-up cancellation on opt-out
- Actionable task generation with appropriate task_types and priorities
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.models.whatsapp import (
    MessageDirection,
    MessageStatus,
    ReplyClassification,
    ReplyClassificationResult,
    WebhookProcessResult,
)
from backend.prompts.reply_classification import build_reply_classification_prompt
from backend.services.ai_client import AIResult
from backend.services.webhook_processor import WebhookProcessorService


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

    def order(self, column: str, desc: bool = False):
        return self

    def limit(self, count: int):
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
                match = all(item.get(k) == v for k, v in self.filter_conditions.items())
                if match:
                    item.update(self.updated_payload)
                    updated_list.append(item)
            self.data = updated_list
            return self
        elif self.inserted_payload is not None:
            return self
        elif self.filter_conditions:
            filtered = [
                item for item in self.target_list
                if all(item.get(k) == v for k, v in self.filter_conditions.items())
            ]
            self.data = filtered
        return self


class MockSupabaseClient:
    """Mock Supabase client providing isolated table state."""

    def __init__(self):
        self.leads_data: List[Dict[str, Any]] = []
        self.campaigns_data: List[Dict[str, Any]] = []
        self.messages_data: List[Dict[str, Any]] = []
        self.suppressions_data: List[Dict[str, Any]] = []
        self.followups_data: List[Dict[str, Any]] = []
        self.tasks_data: List[Dict[str, Any]] = []

    def table(self, table_name: str) -> MockQueryBuilder:
        if table_name == "leads":
            return MockQueryBuilder(self.leads_data)
        elif table_name == "campaigns":
            return MockQueryBuilder(self.campaigns_data)
        elif table_name == "whatsapp_messages":
            return MockQueryBuilder(self.messages_data)
        elif table_name == "suppressions":
            return MockQueryBuilder(self.suppressions_data)
        elif table_name == "followup_schedules":
            return MockQueryBuilder(self.followups_data)
        elif table_name == "tasks":
            return MockQueryBuilder(self.tasks_data)
        return MockQueryBuilder()


# ============================================================================
# Helpers & Prompts Tests
# ============================================================================

def test_is_keyword_opt_out():
    """Verify strict opt-out keyword matching rules per decisions.md §10."""
    # Strict exact matches
    assert WebhookProcessorService.is_keyword_opt_out("STOP") is True
    assert WebhookProcessorService.is_keyword_opt_out("stop") is True
    assert WebhookProcessorService.is_keyword_opt_out("unsubscribe") is True
    assert WebhookProcessorService.is_keyword_opt_out("band karo") is True
    assert WebhookProcessorService.is_keyword_opt_out("mat bhejo") is True
    assert WebhookProcessorService.is_keyword_opt_out("nahi chahiye") is True

    # Starting with keyword
    assert WebhookProcessorService.is_keyword_opt_out("stop messaging me") is True
    assert WebhookProcessorService.is_keyword_opt_out("band karo bhai") is True

    # Rejection of loose substrings or non-opt-outs
    assert WebhookProcessorService.is_keyword_opt_out("nonstop service") is False
    assert WebhookProcessorService.is_keyword_opt_out("can you stop by our clinic tomorrow?") is False
    assert WebhookProcessorService.is_keyword_opt_out("please do not stop the audit") is False


def test_extract_phone_digits():
    """Verify clean extraction of E.164 phone from WAHA and Twilio formats."""
    assert WebhookProcessorService.extract_phone_digits("919822012345@c.us") == "+919822012345"
    assert WebhookProcessorService.extract_phone_digits("whatsapp:+919822012345") == "+919822012345"
    assert WebhookProcessorService.extract_phone_digits("+91 98220 12345") == "+919822012345"
    assert WebhookProcessorService.extract_phone_digits(None) is None


def test_build_reply_classification_prompt():
    """Verify classification prompt formatting and bounds."""
    prompt = build_reply_classification_prompt(
        business_name="Dr. Mehta Dental Clinic",
        service_offered="Website Speed & SEO",
        reply_text="Kitna charge hoga?",
        last_outreach_summary="Lighthouse speed audit",
    )
    assert "Dr. Mehta Dental Clinic" in prompt
    assert "Kitna charge hoga?" in prompt
    assert "pricing_request" in prompt
    assert "Multi-language" in prompt


# ============================================================================
# Webhook Processing Tests
# ============================================================================

@pytest.fixture
def base_db():
    db = MockSupabaseClient()
    db.campaigns_data = [
        {
            "id": "camp_001",
            "user_id": "user_xyz",
            "name": "Local Dental Outreach",
            "service_offered": "Website Speed & SEO",
        }
    ]
    db.leads_data = [
        {
            "id": "lead_001",
            "campaign_id": "camp_001",
            "business_name": "Smile Care Clinic",
            "phone": "+919822012345",
            "is_suppressed": False,
            "pipeline_stage": "contacted",
            "last_contacted_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    db.messages_data = [
        {
            "id": "msg_out_001",
            "lead_id": "lead_001",
            "campaign_id": "camp_001",
            "direction": "outbound",
            "wa_message_id": "wamid_out_123",
            "to_number": "+919822012345",
            "message_body": "Hello Doctor, noticed your mobile site speed.\n\nReply STOP to opt out",
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    db.followups_data = [
        {
            "id": "fup_001",
            "lead_id": "lead_001",
            "campaign_id": "camp_001",
            "status": "pending",
        }
    ]
    return db


@pytest.fixture
def mock_ai_client():
    ai = MagicMock()
    ai.generate_structured_output = AsyncMock()
    ai.generate_structured_output.return_value = AIResult(
        parsed=ReplyClassificationResult(
            classification=ReplyClassification.INTERESTED,
            confidence=0.95,
            reasoning="Prospect expressed clear interest in optimizing website",
            suggested_action="Schedule discovery call",
        ),
        raw_text="{}",
        model_used="gemini-2.5-flash",
        input_tokens=120,
        output_tokens=40,
        cost_usd=0.00003,
        cost_inr=0.01,
    )
    return ai


@pytest.mark.anyio
async def test_waha_delivery_receipt_updates_status(base_db):
    """Test WAHA message.ack payload updates outbound message to delivered and read."""
    service = WebhookProcessorService(db_client=base_db)

    # 1. Delivered ack (ack=2)
    payload_deliv = {"event": "message.ack", "id": "wamid_out_123", "ack": 2}
    res_deliv = await service.process_waha_webhook(payload_deliv)
    assert res_deliv.status == "delivered"
    assert base_db.messages_data[0]["status"] == "delivered"
    assert base_db.messages_data[0]["delivered_at"] is not None

    # 2. Read ack (ack=3)
    payload_read = {"event": "message.ack", "id": "wamid_out_123", "ack": 3}
    res_read = await service.process_waha_webhook(payload_read)
    assert res_read.status == "read"
    assert base_db.messages_data[0]["status"] == "read"
    assert base_db.messages_data[0]["read_at"] is not None


@pytest.mark.anyio
async def test_twilio_delivery_receipt_updates_status(base_db):
    """Test Twilio delivery receipt payload updates outbound message to delivered."""
    service = WebhookProcessorService(db_client=base_db)

    payload = {"MessageSid": "wamid_out_123", "MessageStatus": "delivered"}
    res = await service.process_twilio_webhook(payload)
    assert res.status == "delivered"
    assert base_db.messages_data[0]["status"] == "delivered"


@pytest.mark.anyio
async def test_inbound_keyword_opt_out_immediate_bypass(base_db, mock_ai_client):
    """Test that incoming STOP suppresses the phone, marks lead opted_out, and cancels follow-ups."""
    # Sibling lead of the same user with the same phone
    base_db.leads_data.append(
        {
            "id": "lead_sibling_002",
            "campaign_id": "camp_001",
            "business_name": "Smile Care Branch 2",
            "phone": "+919822012345",
            "is_suppressed": False,
            "pipeline_stage": "qualified",
        }
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_stop_999",
        "from": "919822012345@c.us",
        "body": "STOP",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)

    # 1. Result summary
    assert result.classification == ReplyClassification.OPT_OUT
    assert result.confidence == 1.0
    assert result.suppressed is True
    assert result.stage_transition == "opted_out"
    assert result.followups_cancelled == 1

    # 2. AI client must NOT be called for keyword match
    mock_ai_client.generate_structured_output.assert_not_called()

    # 3. Both leads must be suppressed
    assert base_db.leads_data[0]["is_suppressed"] is True
    assert base_db.leads_data[0]["pipeline_stage"] == "opted_out"
    assert base_db.leads_data[1]["is_suppressed"] is True
    assert base_db.leads_data[1]["pipeline_stage"] == "opted_out"

    # 4. Added to suppressions registry
    assert len(base_db.suppressions_data) == 1
    assert base_db.suppressions_data[0]["phone"] == "+919822012345"

    # 5. Scheduled follow-up cancelled
    assert base_db.followups_data[0]["status"] == "cancelled"


@pytest.mark.anyio
async def test_inbound_ai_interested_reply(base_db, mock_ai_client):
    """Test AI classification of interested reply advances stage to interested and creates task."""
    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_yes_123",
        "from": "919822012345@c.us",
        "body": "Yes, please tell me what needs to be fixed on our site.",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)

    # AI invoked
    mock_ai_client.generate_structured_output.assert_called_once()

    # Result checks
    assert result.classification == ReplyClassification.INTERESTED
    assert result.stage_transition == "interested"
    assert result.tasks_created == 1
    assert result.followups_cancelled == 1

    # Lead updated to interested
    assert base_db.leads_data[0]["pipeline_stage"] == "interested"

    # Actionable sales task created
    assert len(base_db.tasks_data) == 1
    task = base_db.tasks_data[0]
    assert task["task_type"] == "callback"
    assert task["priority"] == "high"
    assert "Smile Care Clinic" in task["title"]


@pytest.mark.anyio
async def test_inbound_meeting_request_creates_urgent_task(base_db, mock_ai_client):
    """Test meeting request reply creates urgent meeting_prep task."""
    mock_ai_client.generate_structured_output.return_value = AIResult(
        parsed=ReplyClassificationResult(
            classification=ReplyClassification.MEETING_REQUEST,
            confidence=0.92,
            reasoning="Lead wants to talk on phone tomorrow",
            suggested_action="Schedule call",
        ),
        raw_text="{}",
        model_used="gemini-2.5-flash",
        input_tokens=100,
        output_tokens=30,
        cost_usd=0.00002,
        cost_inr=0.01,
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "From": "whatsapp:+919822012345",
        "Body": "Can we talk on call tomorrow afternoon?",
        "MessageSid": "SM_inbound_call_456",
    }
    result = await service.process_twilio_webhook(payload)

    assert result.classification == ReplyClassification.MEETING_REQUEST
    assert result.stage_transition == "interested"
    assert len(base_db.tasks_data) == 1
    assert base_db.tasks_data[0]["task_type"] == "schedule_meeting"
    assert base_db.tasks_data[0]["priority"] == "urgent"


@pytest.mark.anyio
async def test_inbound_low_confidence_creates_manual_review_task(base_db, mock_ai_client):
    """Test reply with confidence < 0.7 sets stage to 'replied' and creates manual_review task."""
    mock_ai_client.generate_structured_output.return_value = AIResult(
        parsed=ReplyClassificationResult(
            classification=ReplyClassification.UNCLEAR,
            confidence=0.45,
            reasoning="Single word response is ambiguous",
            suggested_action="Review manually",
        ),
        raw_text="{}",
        model_used="gemini-2.5-flash",
        input_tokens=80,
        output_tokens=30,
        cost_usd=0.00002,
        cost_inr=0.01,
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_ok_777",
        "from": "919822012345@c.us",
        "body": "Ok",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)

    assert result.stage_transition == "replied"
    assert base_db.leads_data[0]["pipeline_stage"] == "replied"
    assert len(base_db.tasks_data) == 1
    assert base_db.tasks_data[0]["task_type"] == "review_reply"
    assert base_db.tasks_data[0]["priority"] == "medium"


@pytest.mark.anyio
async def test_inbound_deduplication_idempotency(base_db, mock_ai_client):
    """Test duplicate webhook delivery is safely ignored without duplicate tasks."""
    # Pre-populate existing inbound message
    base_db.messages_data.append(
        {
            "id": "msg_existing_in_888",
            "wa_message_id": "wamid_in_dup_123",
            "direction": "inbound",
        }
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_dup_123",
        "from": "919822012345@c.us",
        "body": "Duplicate message",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)

    assert result.is_duplicate is True
    assert result.status == "duplicate_ignored"
    mock_ai_client.generate_structured_output.assert_not_called()
    assert len(base_db.tasks_data) == 0


@pytest.mark.anyio
async def test_inbound_unknown_sender_handled_gracefully(base_db, mock_ai_client):
    """Test that incoming message from unknown phone number doesn't crash."""
    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_unknown_000",
        "from": "919999999999@c.us",
        "body": "Hi there",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)
    assert result.status == "unknown_lead"
    mock_ai_client.generate_structured_output.assert_not_called()


@pytest.mark.anyio
async def test_inbound_empty_body_classified_as_unclear(base_db, mock_ai_client):
    """Test non-text media or empty body classified as unclear without invoking AI."""
    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_audio_001",
        "from": "919822012345@c.us",
        "body": "",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)
    assert result.classification == ReplyClassification.UNCLEAR
    assert result.stage_transition == "replied"
    assert result.confidence == 0.5
    # AI not called for empty/media message
    mock_ai_client.generate_structured_output.assert_not_called()
    assert len(base_db.tasks_data) == 1
    assert base_db.tasks_data[0]["task_type"] == "review_reply"


@pytest.mark.anyio
async def test_inbound_wrong_number_reported(base_db, mock_ai_client):
    """Test wrong number reply transitions lead to closed_lost and suppresses."""
    mock_ai_client.generate_structured_output.return_value = AIResult(
        parsed=ReplyClassificationResult(
            classification=ReplyClassification.WRONG_NUMBER,
            confidence=0.96,
            reasoning="Recipient stated they are not the clinic owner",
            suggested_action="Close lead and suppress number",
        ),
        raw_text="{}",
        model_used="gemini-2.5-flash",
        input_tokens=90,
        output_tokens=30,
        cost_usd=0.00002,
        cost_inr=0.01,
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_wrong_001",
        "from": "919822012345@c.us",
        "body": "Wrong number, I am not a doctor.",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)
    assert result.classification == ReplyClassification.WRONG_NUMBER
    assert result.stage_transition == "closed_lost"
    assert result.suppressed is True
    assert base_db.leads_data[0]["pipeline_stage"] == "closed_lost"
    assert base_db.leads_data[0]["is_suppressed"] is True


@pytest.mark.anyio
async def test_inbound_not_interested_reply(base_db, mock_ai_client):
    """Test not interested reply transitions lead to not_interested without creating tasks."""
    mock_ai_client.generate_structured_output.return_value = AIResult(
        parsed=ReplyClassificationResult(
            classification=ReplyClassification.NOT_INTERESTED,
            confidence=0.91,
            reasoning="Lead declined offer",
            suggested_action="No further action needed",
        ),
        raw_text="{}",
        model_used="gemini-2.5-flash",
        input_tokens=85,
        output_tokens=30,
        cost_usd=0.00002,
        cost_inr=0.01,
    )

    service = WebhookProcessorService(db_client=base_db, ai_client=mock_ai_client)

    payload = {
        "event": "message",
        "id": "wamid_in_no_001",
        "from": "919822012345@c.us",
        "body": "No thanks, we have an internal IT team.",
        "fromMe": False,
    }

    result = await service.process_waha_webhook(payload)
    assert result.classification == ReplyClassification.NOT_INTERESTED
    assert result.stage_transition == "not_interested"
    assert base_db.leads_data[0]["pipeline_stage"] == "not_interested"
    assert len(base_db.tasks_data) == 0


