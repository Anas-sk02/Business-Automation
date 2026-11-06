"""AI Message Generator Service for Stage 5: WhatsApp Outreach Engine.

Orchestrates draft generation conforming to:
- docs/decisions.md Sections 7, 10, 11
- docs/whatsapp-integration.md
- docs/prompts.md Section 2
- docs/implementation.md Stage 5 (Task 1)
- docs/UI-UX.md Section 6.7

Key invariants:
- Strict zero auto-send: creates/updates messages with status='draft' only.
- Strict tenant isolation: verifies lead ownership via campaigns.user_id == current user.
- Evidence grounded: utilizes strictly verified evidence (verification_status='verified').
- Anti-hallucination: no fabricated revenue, lost customers, or false urgency.
- Mandatory opt-out: ensures 'Reply STOP to opt out' is present.
- Phone normalization: normalizes prospect phone numbers to canonical E.164.
- Cross-lead suppression: honors opt-out across all leads for that user with matching phone.
- Upsert attempt 0: respects unique constraint uq_messages_one_live_per_attempt by updating
  existing draft if present.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from backend.database import get_supabase_client
from backend.models.whatsapp import (
    GeneratedOutreachMessage,
    MessageDirection,
    MessageStatus,
    MessageType,
    UpdateDraftRequest,
    WhatsAppDraftResponse,
    WhatsAppMessageResponse,
)
from backend.prompts.message_generation import build_message_generation_prompt
from backend.services.ai_client import AIClient, AIClientError
from backend.services.discovery import DiscoveryService

logger = logging.getLogger("signalforge.message_generator")

MANDATORY_OPT_OUT_LINE = "Reply STOP to opt out"


class LeadNotFoundError(Exception):
    """Raised when the specified lead is not found or does not belong to the user."""


class LeadSuppressedError(Exception):
    """Raised when lead or lead phone number is present in suppression list."""


class CampaignBudgetExceededError(Exception):
    """Raised when campaign budget is exceeded before generating draft."""


class MessageGenerationError(Exception):
    """Raised when AI invocation or draft creation fails."""


class MessageGeneratorService:
    """Service managing personalized outreach message generation and draft storage."""

    def __init__(
        self,
        db_client: Any = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        """Initialize MessageGeneratorService with dependency injection support."""
        self._db = db_client or get_supabase_client()
        self._ai_client = ai_client or AIClient(db_client=self._db)

    def _validate_user_and_lead_inputs(self, lead_id: str, user_id: str) -> None:
        """Validate that lead_id and user_id are non-empty strings."""
        if not lead_id or not str(lead_id).strip():
            raise ValueError("lead_id must be a non-empty string")
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id must be a non-empty string")

    async def _verify_lead_and_campaign(
        self, lead_id: str, user_id: str
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Verify lead existence and tenant ownership via campaign user_id.

        Returns:
            Tuple of (lead_dict, campaign_dict)
        Raises:
            LeadNotFoundError: If lead not found or not owned by user.
        """
        self._validate_user_and_lead_inputs(lead_id, user_id)

        # 1. Fetch lead record
        lead_res = self._db.table("leads").select("*").eq("id", lead_id).execute()
        if not lead_res.data:
            raise LeadNotFoundError(f"Lead {lead_id} not found")
        lead = lead_res.data[0]

        # 2. Fetch campaign and verify tenant ownership
        campaign_id = lead.get("campaign_id")
        if not campaign_id:
            raise LeadNotFoundError(f"Lead {lead_id} is not associated with a campaign")

        camp_res = (
            self._db.table("campaigns")
            .select("*")
            .eq("id", campaign_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not camp_res.data:
            raise LeadNotFoundError(
                f"Campaign {campaign_id} not found or access denied for user {user_id}"
            )
        campaign = camp_res.data[0]

        return lead, campaign

    async def _check_suppression(self, lead: Dict[str, Any], campaign: Dict[str, Any]) -> None:
        """Verify lead and phone are not suppressed across the user's campaign leads or registry.

        Per docs/decisions.md Section 10:
        Normalize every phone to E.164 using phonenumbers library. Check suppression
        against lead is_suppressed flag, opted_out stage, matching phone across user leads,
        and suppressions table.
        """
        lead_id = lead.get("id")
        if lead.get("is_suppressed") or lead.get("pipeline_stage") == "opted_out":
            raise LeadSuppressedError(
                f"Lead {lead_id} is marked as suppressed or opted out"
            )

        lead_phone = lead.get("phone")
        if lead_phone:
            normalized_phone = DiscoveryService.normalize_phone(lead_phone) or str(lead_phone).strip()

            # 1. Check if any other lead with the same phone in the user's campaign is suppressed
            other_leads_res = (
                self._db.table("leads")
                .select("id, is_suppressed, pipeline_stage")
                .eq("phone", normalized_phone)
                .execute()
            )
            for other in (other_leads_res.data or []):
                if other.get("is_suppressed") or other.get("pipeline_stage") == "opted_out":
                    raise LeadSuppressedError(
                        f"Phone {lead_phone} ({normalized_phone}) was previously opted out on lead {other.get('id')}"
                    )

            # 2. Check standalone suppressions registry table (if present)
            supp_res = None
            try:
                supp_res = (
                    self._db.table("suppressions")
                    .select("id")
                    .eq("phone", normalized_phone)
                    .execute()
                )
            except Exception as e:
                logger.debug(f"Standalone suppressions check notice: {e}")

            if supp_res and supp_res.data:
                raise LeadSuppressedError(
                    f"Phone {lead_phone} ({normalized_phone}) is listed in suppression registry"
                )

    async def generate_draft(
        self,
        lead_id: str,
        user_id: str,
        instructions: Optional[str] = None,
        template_name: Optional[str] = None,
        followup_attempt: int = 0,
    ) -> WhatsAppDraftResponse:
        """Generate a personalized, evidence-backed WhatsApp outreach draft for a lead.

        Args:
            lead_id: UUID of prospect lead.
            user_id: UUID of authenticated user.
            instructions: Optional user-provided tone or offer instructions.
            template_name: Optional template name override.
            followup_attempt: 0 for initial outreach, 1+ for subsequent follow-ups.

        Returns:
            WhatsAppDraftResponse containing stored message record and metadata.

        Raises:
            ValueError: If lead_id or user_id are invalid.
            LeadNotFoundError: If lead not found or not owned by user.
            LeadSuppressedError: If lead or phone is opted out / suppressed.
            CampaignBudgetExceededError: If campaign has exceeded max_budget.
            MessageGenerationError: If AI generation fails.
        """
        lead, campaign = await self._verify_lead_and_campaign(lead_id, user_id)
        campaign_id = campaign["id"]

        # Check suppression rules
        await self._check_suppression(lead, campaign)

        # Budget check per decisions.md Section 11
        max_budget = float(campaign.get("max_budget") or 0.0)
        spent_amount = float(campaign.get("spent_amount") or 0.0)
        # Estimated cost for flash message generation ~0.05 INR
        if max_budget > 0.0 and (spent_amount + 0.05) > max_budget:
            raise CampaignBudgetExceededError(
                f"Campaign {campaign_id} budget limit (₹{max_budget:.2f}) reached (spent: ₹{spent_amount:.2f})"
            )

        # Fetch sender user profile
        profile_res = self._db.table("profiles").select("*").eq("id", user_id).execute()
        profile = profile_res.data[0] if (profile_res.data and len(profile_res.data) > 0) else {}

        # Fetch strictly verified audit evidence items
        ev_res = (
            self._db.table("evidence_items")
            .select("*")
            .eq("lead_id", lead_id)
            .eq("verification_status", "verified")
            .execute()
        )
        verified_evidence: List[Dict[str, Any]] = ev_res.data or []

        # Fetch existing AI analysis if available
        an_res = (
            self._db.table("ai_analyses")
            .select("*")
            .eq("lead_id", lead_id)
            .execute()
        )
        analysis: Optional[Dict[str, Any]] = an_res.data[0] if (an_res.data and len(an_res.data) > 0) else None

        # Build structured prompt with sanitized inputs
        prompt = build_message_generation_prompt(
            lead=lead,
            campaign=campaign,
            profile=profile,
            analysis=analysis,
            verified_evidence=verified_evidence,
            custom_instructions=instructions,
            followup_attempt=followup_attempt,
        )

        # Invoke AI client
        try:
            ai_result = await self._ai_client.generate_structured_output(
                prompt=prompt,
                schema_class=GeneratedOutreachMessage,
                campaign_id=campaign_id,
                user_id=user_id,
                service="ai_message_gen",
                operation="message_generation",
                metadata={"lead_id": lead_id, "followup_attempt": followup_attempt},
            )
        except AIClientError as exc:
            logger.error(f"AI message generation failed for lead {lead_id}: {exc}")
            raise MessageGenerationError(f"Failed to generate outreach message: {exc}") from exc

        generated: GeneratedOutreachMessage = ai_result.parsed

        # Enforce mandatory opt-out guardrail per decisions.md Section 10
        body_text = generated.message_body.strip()
        if MANDATORY_OPT_OUT_LINE.lower() not in body_text.lower():
            body_text = f"{body_text}\n\n{MANDATORY_OPT_OUT_LINE}"

        chosen_template = template_name or generated.template_name or "business_website_intro"

        # Canonicalize phone to E.164 format
        lead_phone = lead.get("phone")
        normalized_phone = DiscoveryService.normalize_phone(lead_phone) if lead_phone else None

        # Check for existing active attempt draft (upsert semantics for uq_messages_one_live_per_attempt)
        existing_res = (
            self._db.table("whatsapp_messages")
            .select("*")
            .eq("lead_id", lead_id)
            .eq("campaign_id", campaign_id)
            .eq("direction", MessageDirection.OUTBOUND.value)
            .eq("followup_attempt", followup_attempt)
            .execute()
        )
        active_existing = [
            m for m in (existing_res.data or [])
            if m.get("status") not in (MessageStatus.FAILED.value, MessageStatus.CANCELLED.value)
        ]

        if active_existing:
            # Update existing draft in-place
            existing_record = active_existing[0]
            msg_id = existing_record["id"]
            update_data = {
                "message_body": body_text,
                "template_name": chosen_template,
                "template_variables": generated.template_variables,
                "status": MessageStatus.DRAFT.value,
                "message_type": MessageType.TEXT.value,
                "to_number": normalized_phone or lead_phone,
            }
            save_res = (
                self._db.table("whatsapp_messages")
                .update(update_data)
                .eq("id", msg_id)
                .eq("campaign_id", campaign_id)
                .execute()
            )
            saved_msg = {**existing_record, **(save_res.data[0] if save_res.data else update_data)}
        else:
            # Insert new draft row
            now_iso = datetime.now(timezone.utc).isoformat()
            insert_data = {
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "direction": MessageDirection.OUTBOUND.value,
                "from_number": None,
                "to_number": normalized_phone or lead_phone,
                "template_name": chosen_template,
                "template_variables": generated.template_variables,
                "message_body": body_text,
                "message_type": MessageType.TEXT.value,
                "status": MessageStatus.DRAFT.value,
                "followup_attempt": followup_attempt,
                "is_followup": bool(followup_attempt > 0),
                "conversation_cost": 0.0,
                "created_at": now_iso,
            }
            save_res = self._db.table("whatsapp_messages").insert(insert_data).execute()
            saved_msg = save_res.data[0] if save_res.data else insert_data

        return WhatsAppDraftResponse(
            message=WhatsAppMessageResponse.model_validate(saved_msg),
            lead_id=lead_id,
            lead_name=lead.get("business_name") or "Business Owner",
            recipient_phone=normalized_phone or lead_phone,
            evidence_cited=generated.evidence_cited,
            estimated_cost_inr=ai_result.cost_inr,
            status=MessageStatus.DRAFT,
        )

    async def get_draft(
        self,
        lead_id: str,
        user_id: str,
        followup_attempt: int = 0,
    ) -> Optional[WhatsAppDraftResponse]:
        """Fetch the current active draft message for a lead if it exists."""
        lead, campaign = await self._verify_lead_and_campaign(lead_id, user_id)
        campaign_id = campaign["id"]

        msg_res = (
            self._db.table("whatsapp_messages")
            .select("*")
            .eq("lead_id", lead_id)
            .eq("campaign_id", campaign_id)
            .eq("direction", MessageDirection.OUTBOUND.value)
            .eq("followup_attempt", followup_attempt)
            .execute()
        )
        active = [
            m for m in (msg_res.data or [])
            if m.get("status") not in (MessageStatus.FAILED.value, MessageStatus.CANCELLED.value)
        ]
        if not active:
            return None

        msg_record = active[0]
        return WhatsAppDraftResponse(
            message=WhatsAppMessageResponse.model_validate(msg_record),
            lead_id=lead_id,
            lead_name=lead.get("business_name") or "Business Owner",
            recipient_phone=msg_record.get("to_number") or lead.get("phone"),
            evidence_cited=[],
            estimated_cost_inr=0.0,
            status=MessageStatus(msg_record.get("status", "draft")),
        )

    async def update_draft(
        self,
        lead_id: str,
        user_id: str,
        request: UpdateDraftRequest,
    ) -> WhatsAppDraftResponse:
        """Manually update an existing draft message body, variables, or approval status.

        Per docs/UI-UX.md §6.7 & docs/implementation.md Stage 5:
        Enforces mandatory opt-out line retention and scopes update to tenant campaign.

        Args:
            lead_id: UUID of prospect lead.
            user_id: UUID of authenticated user.
            request: Validated UpdateDraftRequest.

        Returns:
            Updated WhatsAppDraftResponse.

        Raises:
            ValueError: If no editable draft exists or inputs are invalid.
            LeadNotFoundError: If lead not found or not owned by user.
        """
        lead, campaign = await self._verify_lead_and_campaign(lead_id, user_id)
        campaign_id = campaign["id"]

        msg_res = (
            self._db.table("whatsapp_messages")
            .select("*")
            .eq("lead_id", lead_id)
            .eq("campaign_id", campaign_id)
            .eq("direction", MessageDirection.OUTBOUND.value)
            .eq("followup_attempt", 0)
            .execute()
        )
        active = [
            m for m in (msg_res.data or [])
            if m.get("status") in (
                MessageStatus.DRAFT.value,
                MessageStatus.PENDING_APPROVAL.value,
                MessageStatus.APPROVED.value,
            )
        ]
        if not active:
            raise ValueError(
                f"No editable draft or pre-approval message found for lead {lead_id}"
            )

        existing_record = active[0]
        msg_id = existing_record["id"]

        # Ensure mandatory opt-out remains on the edited message
        body_text = request.message_body.strip()
        if MANDATORY_OPT_OUT_LINE.lower() not in body_text.lower():
            body_text = f"{body_text}\n\n{MANDATORY_OPT_OUT_LINE}"

        update_payload: Dict[str, Any] = {
            "message_body": body_text,
        }
        if request.template_variables is not None:
            update_payload["template_variables"] = request.template_variables
        if request.status is not None:
            update_payload["status"] = request.status.value

        save_res = (
            self._db.table("whatsapp_messages")
            .update(update_payload)
            .eq("id", msg_id)
            .eq("campaign_id", campaign_id)
            .execute()
        )
        saved_msg = {**existing_record, **(save_res.data[0] if save_res.data else update_payload)}

        return WhatsAppDraftResponse(
            message=WhatsAppMessageResponse.model_validate(saved_msg),
            lead_id=lead_id,
            lead_name=lead.get("business_name") or "Business Owner",
            recipient_phone=saved_msg.get("to_number") or lead.get("phone"),
            evidence_cited=[],
            estimated_cost_inr=0.0,
            status=MessageStatus(saved_msg.get("status", "draft")),
        )
