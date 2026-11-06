"""Inbound Webhook Processor for Stage 5: WhatsApp Outreach & Reply Tracking.

Processes webhooks from WAHA and Twilio, manages delivery receipts, enforces strict keyword
opt-out suppression, classifies replies via AI, transitions pipeline stages, cancels scheduled
follow-ups, and generates actionable sales tasks conforming to:
- docs/decisions.md Sections 5, 10, 11
- docs/whatsapp-integration.md
- docs/prompts.md Section 2
- docs/database-schema.md
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, Optional, Tuple

from backend.database import get_supabase_client
from backend.models.whatsapp import (
    MessageDirection,
    MessageStatus,
    MessageType,
    ReplyClassification,
    ReplyClassificationResult,
    WebhookProcessResult,
)
from backend.prompts.reply_classification import build_reply_classification_prompt
from backend.services.ai_client import AIClient, AIClientError
from backend.services.discovery import DiscoveryService

logger = logging.getLogger("signalforge.webhook_processor")

# Strict keyword opt-out triggers per docs/decisions.md Section 10
OPT_OUT_KEYWORDS: Tuple[str, ...] = (
    "stop",
    "unsubscribe",
    "opt out",
    "optout",
    "band karo",
    "mat bhejo",
    "nahi chahiye",
)


class WebhookProcessorService:
    """Service processing incoming WhatsApp webhook events and managing reply pipelines."""

    def __init__(
        self,
        db_client: Any = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        """Initialize WebhookProcessorService with dependency injection."""
        self._db = db_client or get_supabase_client()
        self._ai = ai_client or AIClient(db_client=self._db)

    @staticmethod
    def is_keyword_opt_out(text: str) -> bool:
        """Strict check whether incoming message is an opt-out demand.

        Per docs/decisions.md Section 10:
        If the trimmed, lowercased message equals or starts with one of:
        stop, unsubscribe, opt out, band karo, mat bhejo, nahi chahiye,
        treat it as an opt-out immediately without loose substring matching.
        """
        if not text or not isinstance(text, str):
            return False

        clean = re.sub(r"[^\w\s]", "", text.strip().lower())
        if not clean:
            return False

        for kw in OPT_OUT_KEYWORDS:
            if clean == kw or clean.startswith(kw + " "):
                return True
        return False

    @staticmethod
    def extract_phone_digits(from_str: str) -> Optional[str]:
        """Extract clean phone number from JID or Twilio format.

        e.g. '919822012345@c.us' -> '+919822012345'
             'whatsapp:+919822012345' -> '+919822012345'
        """
        if not from_str or not isinstance(from_str, str):
            return None
        cleaned = from_str.replace("whatsapp:", "").split("@")[0].split(":")[0].strip()
        return DiscoveryService.normalize_phone(cleaned)

    async def _handle_delivery_receipt(
        self,
        wa_message_id: str,
        new_status: MessageStatus,
        error_message: Optional[str] = None,
    ) -> WebhookProcessResult:
        """Update outbound message delivery status based on receipt webhook."""
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data: Dict[str, Any] = {"status": new_status.value}

        if new_status == MessageStatus.DELIVERED:
            update_data["delivered_at"] = now_iso
        elif new_status == MessageStatus.READ:
            update_data["read_at"] = now_iso
        elif new_status == MessageStatus.FAILED:
            update_data["failed_at"] = now_iso
            if error_message:
                update_data["error_message"] = error_message[:500]

        res = (
            self._db.table("whatsapp_messages")
            .update(update_data)
            .eq("wa_message_id", wa_message_id)
            .execute()
        )
        found = bool(res.data and len(res.data) > 0)

        return WebhookProcessResult(
            event_type="delivery_receipt",
            wa_message_id=wa_message_id,
            status=new_status.value,
            stage_transition=None,
            tasks_created=0,
            suppressed=False,
            followups_cancelled=0,
            is_duplicate=False if found else True,
        )

    async def process_waha_webhook(self, payload: Dict[str, Any]) -> WebhookProcessResult:
        """Parse and process a WAHA webhook payload."""
        if not payload or not isinstance(payload, dict):
            return WebhookProcessResult(event_type="invalid_payload", status="ignored")

        event = payload.get("event")

        # Resolve inner data object (WAHA can pass fields either at root or nested in 'payload')
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload

        # 1. Handle Delivery Receipts (message.ack)
        if event == "message.ack":
            ack = inner.get("ack") if inner.get("ack") is not None else payload.get("ack")
            wa_id = str(inner.get("id") or payload.get("id") or "")
            if not wa_id:
                return WebhookProcessResult(event_type="message.ack", status="missing_id")

            if ack == 2:
                return await self._handle_delivery_receipt(wa_id, MessageStatus.DELIVERED)
            elif ack in (3, 4):
                return await self._handle_delivery_receipt(wa_id, MessageStatus.READ)
            return WebhookProcessResult(event_type="message.ack", wa_message_id=wa_id, status=f"ack_{ack}")

        # 2. Handle Inbound Messages (message)
        if event == "message":
            # Ignore our own reflected messages
            if inner.get("fromMe") is True or payload.get("fromMe") is True:
                return WebhookProcessResult(event_type="message_echo_ignored", status="ignored")

            from_raw = inner.get("from") or payload.get("from") or ""
            phone = self.extract_phone_digits(from_raw)
            body = inner.get("body") or payload.get("body") or ""
            msg_id = str(inner.get("id") or payload.get("id") or "")

            if not phone or not msg_id:
                return WebhookProcessResult(event_type="invalid_message", status="missing_fields")

            return await self.process_inbound_message(phone=phone, body=body, wa_message_id=msg_id)

        return WebhookProcessResult(event_type=f"unhandled_{event}", status="ignored")

    async def process_twilio_webhook(self, payload: Dict[str, Any]) -> WebhookProcessResult:
        """Parse and process a Twilio webhook payload."""
        if not payload or not isinstance(payload, dict):
            return WebhookProcessResult(event_type="invalid_payload", status="ignored")

        status_val = payload.get("MessageStatus")
        sid = payload.get("MessageSid") or payload.get("SmsSid")

        # Delivery Receipt
        if status_val and sid:
            s_lower = status_val.lower()
            if s_lower == "delivered":
                return await self._handle_delivery_receipt(sid, MessageStatus.DELIVERED)
            elif s_lower == "read":
                return await self._handle_delivery_receipt(sid, MessageStatus.READ)
            elif s_lower in ("failed", "undelivered"):
                err = payload.get("ErrorMessage") or f"Twilio status {status_val}"
                return await self._handle_delivery_receipt(sid, MessageStatus.FAILED, error_message=err)

        # Inbound Message
        from_raw = payload.get("From") or ""
        body = payload.get("Body") or ""
        if from_raw and sid:
            phone = self.extract_phone_digits(from_raw)
            if phone:
                return await self.process_inbound_message(phone=phone, body=body, wa_message_id=sid)

        return WebhookProcessResult(event_type="twilio_unhandled", status="ignored")

    async def process_inbound_message(
        self,
        phone: str,
        body: str,
        wa_message_id: str,
    ) -> WebhookProcessResult:
        """Process inbound prospect reply: deduplication, classification, stage update, tasks."""
        # 1. Deduplication / Idempotency check per CLAUDE.md
        existing_msg = (
            self._db.table("whatsapp_messages")
            .select("id")
            .eq("wa_message_id", wa_message_id)
            .execute()
        )
        if existing_msg.data and len(existing_msg.data) > 0:
            logger.info(f"Duplicate incoming message {wa_message_id} ignored")
            return WebhookProcessResult(
                event_type="inbound_reply",
                wa_message_id=wa_message_id,
                status="duplicate_ignored",
                is_duplicate=True,
            )

        # 2. Resolve target lead and campaign
        normalized_phone = DiscoveryService.normalize_phone(phone) or phone

        # Prefer matching by most recent outbound message sent to this phone (preserves exact campaign context)
        recent_out = (
            self._db.table("whatsapp_messages")
            .select("lead_id, campaign_id")
            .eq("to_number", normalized_phone)
            .eq("direction", MessageDirection.OUTBOUND.value)
            .order("sent_at", desc=True)
            .limit(1)
            .execute()
        )

        lead_id = recent_out.data[0].get("lead_id") if (recent_out.data and len(recent_out.data) > 0) else None

        if lead_id:
            lead_res = self._db.table("leads").select("*").eq("id", lead_id).execute()
        else:
            lead_res = (
                self._db.table("leads")
                .select("*")
                .eq("phone", normalized_phone)
                .order("last_contacted_at", desc=True)
                .execute()
            )

        if not lead_res.data:
            logger.warning(f"Inbound reply received from unknown number {normalized_phone}")
            return WebhookProcessResult(
                event_type="inbound_unknown_sender",
                wa_message_id=wa_message_id,
                status="unknown_lead",
            )

        lead = lead_res.data[0]
        lead_id = lead["id"]
        campaign_id = lead["campaign_id"]

        # Fetch campaign and user_id for task assignment
        camp_res = self._db.table("campaigns").select("*").eq("id", campaign_id).execute()
        campaign = camp_res.data[0] if camp_res.data else {}
        user_id = campaign.get("user_id")

        # 3. Classify reply
        clean_body = (body or "").strip()
        is_opt_out = self.is_keyword_opt_out(clean_body)

        if not clean_body:
            # Handle empty body or non-text media (e.g. voice notes/stickers)
            classification = ReplyClassification.UNCLEAR
            confidence = 0.5
            reasoning = "Non-text media or empty message received"
            suggested_action = "Manual review required"
        elif is_opt_out:
            classification = ReplyClassification.OPT_OUT
            confidence = 1.0
            reasoning = "Matched strict opt-out keyword"
            suggested_action = "Suppress recipient and cancel outreach"
        else:
            # Call AI reply classifier
            biz_name = lead.get("business_name") or "Business Owner"
            service_pitched = campaign.get("service_offered") or "Digital Growth & Web Solutions"

            # Fetch last outreach summary
            last_msg_res = (
                self._db.table("whatsapp_messages")
                .select("message_body")
                .eq("lead_id", lead_id)
                .eq("direction", MessageDirection.OUTBOUND.value)
                .order("sent_at", desc=True)
                .limit(1)
                .execute()
            )
            last_summary = (
                last_msg_res.data[0].get("message_body", "")[:250]
                if last_msg_res.data
                else None
            )

            prompt = build_reply_classification_prompt(
                business_name=biz_name,
                service_offered=service_pitched,
                reply_text=clean_body,
                last_outreach_summary=last_summary,
            )

            try:
                ai_res = await self._ai.generate_structured_output(
                    prompt=prompt,
                    schema_class=ReplyClassificationResult,
                    campaign_id=campaign_id,
                    user_id=user_id,
                    service="whatsapp_outreach",
                    operation="reply_classification",
                    metadata={"lead_id": lead_id, "incoming_msg_id": wa_message_id},
                )
                classification = ai_res.parsed.classification
                confidence = float(ai_res.parsed.confidence)
                reasoning = ai_res.parsed.reasoning
                suggested_action = ai_res.parsed.suggested_action
            except AIClientError as exc:
                logger.error(f"AI reply classification failed for message {wa_message_id}: {exc}")
                # Safe fallback to unclear per decisions.md §5
                classification = ReplyClassification.UNCLEAR
                confidence = 0.5
                reasoning = f"Classification fallback due to AI error: {exc}"
                suggested_action = "Manual review required"

        # 4. Save inbound message in public.whatsapp_messages
        now_iso = datetime.now(timezone.utc).isoformat()
        inbound_record = {
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "direction": MessageDirection.INBOUND.value,
            "from_number": normalized_phone,
            "to_number": None,
            "message_body": clean_body or "[Non-text media / Audio]",
            "message_type": MessageType.TEXT.value,
            "status": MessageStatus.READ.value,
            "wa_message_id": wa_message_id,
            "reply_classification": classification.value,
            "classification_confidence": confidence,
            "created_at": now_iso,
        }
        self._db.table("whatsapp_messages").insert(inbound_record).execute()

        # 5. Apply Pipeline Transitions & Extra Actions per decisions.md §5
        new_stage: Optional[str] = None
        tasks_created = 0
        followups_cancelled = 0
        suppressed = False

        # Cancel pending follow-ups for this lead on any inbound reply
        from backend.services.followup import FollowupService
        followup_svc = FollowupService(db_client=self._db)
        followups_cancelled = await followup_svc.cancel_followups(lead_id, reason="inbound_reply")

        # Opt-out demand
        if classification == ReplyClassification.OPT_OUT:
            new_stage = "opted_out"
            suppressed = True
            # Update target lead
            self._db.table("leads").update({
                "pipeline_stage": "opted_out",
                "is_suppressed": True,
                "suppression_reason": f"Opt-out request: {clean_body[:100]}",
            }).eq("id", lead_id).eq("campaign_id", campaign_id).execute()

            # Cross-lead suppression across all campaigns of this user
            if user_id:
                user_camps = self._db.table("campaigns").select("id").eq("user_id", user_id).execute()
                for c in (user_camps.data or []):
                    self._db.table("leads").update({
                        "is_suppressed": True,
                        "suppression_reason": "Opt-out by phone",
                        "pipeline_stage": "opted_out",
                    }).eq("campaign_id", c["id"]).eq("phone", normalized_phone).execute()

            # Record in suppressions table idempotently
            try:
                existing_supp = self._db.table("suppressions").select("id").eq("phone", normalized_phone).execute()
                if not (existing_supp.data and len(existing_supp.data) > 0):
                    self._db.table("suppressions").insert({
                        "phone": normalized_phone,
                        "reason": "user_opt_out",
                        "source": "whatsapp_inbound",
                    }).execute()
            except Exception as e:
                logger.debug(f"Suppressions insert notice: {e}")

        # Wrong number
        elif classification == ReplyClassification.WRONG_NUMBER:
            new_stage = "closed_lost"
            suppressed = True
            self._db.table("leads").update({
                "pipeline_stage": "closed_lost",
                "is_suppressed": True,
                "suppression_reason": "Wrong number reported by recipient",
            }).eq("id", lead_id).eq("campaign_id", campaign_id).execute()

        # Low confidence (< 0.7) or Unclear -> 'replied' + manual-review task
        elif confidence < 0.7 or classification == ReplyClassification.UNCLEAR:
            new_stage = "replied"
            self._db.table("leads").update({"pipeline_stage": "replied"}).eq("id", lead_id).eq("campaign_id", campaign_id).execute()
            if user_id:
                self._db.table("tasks").insert({
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": "review_reply",
                    "title": f"Review ambiguous reply from {lead.get('business_name') or 'lead'}",
                    "description": f"Reply: '{clean_body}'\nClassification: {classification.value} (confidence: {confidence:.2f})\nReasoning: {reasoning}",
                    "priority": "medium",
                    "status": "pending",
                }).execute()
                tasks_created += 1

        # High confidence positive response
        elif classification in (
            ReplyClassification.INTERESTED,
            ReplyClassification.PRICING_REQUEST,
            ReplyClassification.MEETING_REQUEST,
        ):
            new_stage = "interested"
            self._db.table("leads").update({"pipeline_stage": "interested"}).eq("id", lead_id).eq("campaign_id", campaign_id).execute()

            if user_id:
                biz = lead.get("business_name") or "lead"
                if classification == ReplyClassification.MEETING_REQUEST:
                    t_type = "schedule_meeting"
                    priority = "urgent"
                    t_title = f"Schedule meeting with {biz}"
                elif classification == ReplyClassification.PRICING_REQUEST:
                    t_type = "send_pricing"
                    priority = "high"
                    t_title = f"Provide pricing info to {biz}"
                else:
                    t_type = "callback"
                    priority = "high"
                    t_title = f"Follow up with interested lead {biz}"

                self._db.table("tasks").insert({
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": t_type,
                    "title": t_title,
                    "description": f"Reply: '{clean_body}'\nAction: {suggested_action or reasoning}",
                    "priority": priority,
                    "status": "pending",
                }).execute()
                tasks_created += 1

        # Wants info or Not now
        elif classification in (ReplyClassification.WANTS_INFO, ReplyClassification.NOT_NOW):
            new_stage = "replied"
            self._db.table("leads").update({"pipeline_stage": "replied"}).eq("id", lead_id).eq("campaign_id", campaign_id).execute()

            if user_id:
                biz = lead.get("business_name") or "lead"
                if classification == ReplyClassification.WANTS_INFO:
                    t_type = "callback"
                    priority = "medium"
                    t_title = f"Send details to {biz}"
                else:
                    t_type = "followup"
                    priority = "low"
                    t_title = f"Follow up later with {biz}"

                self._db.table("tasks").insert({
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": t_type,
                    "title": t_title,
                    "description": f"Reply: '{clean_body}'\nAction: {suggested_action or reasoning}",
                    "priority": priority,
                    "status": "pending",
                }).execute()
                tasks_created += 1

        # Not interested
        elif classification == ReplyClassification.NOT_INTERESTED:
            new_stage = "not_interested"
            self._db.table("leads").update({"pipeline_stage": "not_interested"}).eq("id", lead_id).eq("campaign_id", campaign_id).execute()

        return WebhookProcessResult(
            event_type="inbound_reply",
            wa_message_id=wa_message_id,
            status="processed",
            lead_id=lead_id,
            classification=classification,
            confidence=confidence,
            stage_transition=new_stage,
            tasks_created=tasks_created,
            suppressed=suppressed,
            followups_cancelled=followups_cancelled,
            is_duplicate=False,
        )
