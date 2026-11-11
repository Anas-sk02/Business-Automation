"""Pydantic models and schemas for WhatsApp messages, drafts, and webhooks."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MessageDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageType(str, Enum):
    TEXT = "text"
    TEMPLATE = "template"
    IMAGE = "image"
    DOCUMENT = "document"


class MessageStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReplyClassification(str, Enum):
    INTERESTED = "interested"
    WANTS_INFO = "wants_info"
    PRICING_REQUEST = "pricing_request"
    MEETING_REQUEST = "meeting_request"
    NOT_INTERESTED = "not_interested"
    NOT_NOW = "not_now"
    WRONG_NUMBER = "wrong_number"
    OPT_OUT = "opt_out"
    UNCLEAR = "unclear"


class WhatsAppMessageResponse(BaseModel):
    """Schema for a single stored WhatsApp message record."""

    id: str
    lead_id: str
    campaign_id: str
    wa_message_id: Optional[str] = None
    direction: MessageDirection
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    template_name: Optional[str] = None
    template_variables: Dict[str, Any] = Field(default_factory=dict)
    message_body: str
    message_type: MessageType = MessageType.TEXT
    status: MessageStatus
    error_message: Optional[str] = None
    reply_classification: Optional[ReplyClassification] = None
    classification_confidence: Optional[float] = None
    followup_attempt: int = 0
    is_followup: bool = False
    conversation_cost: float = 0.0
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class GeneratedOutreachMessage(BaseModel):
    """Raw structured output produced by AI client."""

    message_body: str
    template_name: Optional[str] = "business_website_intro"
    template_variables: Dict[str, Any] = Field(default_factory=dict)
    evidence_cited: List[str] = Field(default_factory=list)


class GenerateDraftRequest(BaseModel):
    """Request payload to generate an AI outreach message draft."""

    lead_id: Optional[str] = None
    template_name: Optional[str] = None
    instructions: Optional[str] = Field(
        default=None,
        description="Optional custom user instruction for tone or specific offer",
    )


class SendMessageRequest(BaseModel):
    """Optional request payload when dispatching an approved message."""

    message_id: Optional[str] = Field(
        default=None,
        description="Optional explicit message UUID. If omitted, active approved draft is sent.",
    )
    ignore_quiet_hours: bool = Field(
        default=False,
        description="Set to true to explicitly override quiet hours safeguard for manual testing/send.",
    )


class UpdateDraftRequest(BaseModel):
    """Request payload to manually edit a draft message body or status."""

    message_body: str = Field(..., min_length=1, max_length=2000)
    template_variables: Optional[Dict[str, Any]] = None
    status: Optional[MessageStatus] = None

    @field_validator("message_body")
    @classmethod
    def validate_message_body(cls, value: str) -> str:
        """Ensure message body is not blank whitespace."""
        clean = value.strip()
        if not clean:
            raise ValueError("message_body cannot be empty or purely whitespace")
        return clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[MessageStatus]) -> Optional[MessageStatus]:
        """Ensure status transitions during draft editing stay within allowable pre-send states."""
        if value is not None and value not in (
            MessageStatus.DRAFT,
            MessageStatus.PENDING_APPROVAL,
            MessageStatus.APPROVED,
        ):
            raise ValueError(
                f"Draft status can only be set to 'draft', 'pending_approval', or 'approved'; got '{value.value}'"
            )
        return value


class WhatsAppDraftResponse(BaseModel):
    """Response returned when an outreach message draft is created or updated."""

    message: WhatsAppMessageResponse
    lead_id: str
    lead_name: str
    recipient_phone: Optional[str] = None
    evidence_cited: List[str] = Field(default_factory=list)
    estimated_cost_inr: float = 0.0
    status: MessageStatus = MessageStatus.DRAFT


class SendMessageResponse(BaseModel):
    """Response returned when an approved message is dispatched."""

    message: WhatsAppMessageResponse
    lead_id: str
    recipient_phone: str
    provider: str
    wa_message_id: str
    sent_at: datetime
    cost_inr: float = 0.0


class ReplyClassificationResult(BaseModel):
    """Structured AI output for WhatsApp reply classification."""

    classification: ReplyClassification
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    suggested_action: Optional[str] = None


class WebhookProcessResult(BaseModel):
    """Summary of actions taken by the webhook processor."""

    event_type: str
    wa_message_id: Optional[str] = None
    status: Optional[str] = None
    lead_id: Optional[str] = None
    classification: Optional[ReplyClassification] = None
    confidence: Optional[float] = None
    stage_transition: Optional[str] = None
    tasks_created: int = 0
    suppressed: bool = False
    followups_cancelled: int = 0
    is_duplicate: bool = False


class WhatsAppSessionStatus(BaseModel):
    """Status model for user's isolated WAHA session."""

    session_name: str
    status: str
    connected: bool
    phone_number: Optional[str] = None
    push_name: Optional[str] = None


class WhatsAppSessionQRResponse(BaseModel):
    """QR Code response for pairing WhatsApp session."""

    session_name: str
    qr_code: Optional[str] = None
    status: str




