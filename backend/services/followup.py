"""Follow-up Engine and Scheduling Service for automated outreach lifecycle management."""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.database import get_supabase_client
from backend.services.ai_client import AIClient
from backend.services.message_generator import MessageGeneratorService

logger = logging.getLogger("signalforge.followup")

# Timezone and quiet hours configuration per docs/decisions.md Section 10
TIMEZONE_IST = ZoneInfo("Asia/Kolkata")
QUIET_START_HOUR = 21  # 9:00 PM IST
QUIET_END_HOUR = 9     # 9:00 AM IST
QUIET_RESUME_MINUTE = 30  # 9:30 AM IST for safe scheduling buffer

TERMINAL_OR_ADVANCED_STAGES = {
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
    "closed_lost",
    "not_interested",
    "opted_out",
    "no_response",
}


class FollowupService:
    """Service responsible for scheduling, evaluating, and cancelling lead follow-ups."""

    def __init__(
        self,
        db_client: Any = None,
        message_generator: Optional[MessageGeneratorService] = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        """Initialize FollowupService with optional dependency injection."""
        self._db = db_client or get_supabase_client()
        self._ai_client = ai_client or AIClient(db_client=self._db)
        self._message_generator = message_generator or MessageGeneratorService(
            db_client=self._db, ai_client=self._ai_client
        )

    # -------------------------------------------------------------------------
    # Quiet Hours Logic (Asia/Kolkata)
    # -------------------------------------------------------------------------

    @classmethod
    def is_quiet_hours(cls, dt: Optional[datetime] = None) -> bool:
        """Check whether given datetime (default now UTC) falls in IST quiet hours (21:00-09:00)."""
        check_dt = dt or datetime.now(timezone.utc)
        ist_dt = check_dt.astimezone(TIMEZONE_IST)
        ist_time = ist_dt.time()
        # Quiet if hour >= 21 or hour < 9
        return ist_time >= time(QUIET_START_HOUR, 0) or ist_time < time(QUIET_END_HOUR, 0)

    @classmethod
    def adjust_for_quiet_hours(cls, target_dt: datetime) -> datetime:
        """If target_dt falls within IST quiet hours, defer to next 09:30 AM IST."""
        ist_dt = target_dt.astimezone(TIMEZONE_IST)
        if not cls.is_quiet_hours(target_dt):
            return target_dt

        # If after 21:00 IST, advance to tomorrow 09:30 AM IST
        if ist_dt.time() >= time(QUIET_START_HOUR, 0):
            next_day = ist_dt.date() + timedelta(days=1)
            deferred_ist = datetime.combine(
                next_day, time(QUIET_END_HOUR, QUIET_RESUME_MINUTE), tzinfo=TIMEZONE_IST
            )
        else:
            # If between midnight and 09:00 IST, defer to today 09:30 AM IST
            deferred_ist = datetime.combine(
                ist_dt.date(), time(QUIET_END_HOUR, QUIET_RESUME_MINUTE), tzinfo=TIMEZONE_IST
            )

        return deferred_ist.astimezone(timezone.utc)

    # -------------------------------------------------------------------------
    # Schedule Follow-ups (Triggered after initial outbound send)
    # -------------------------------------------------------------------------

    async def schedule_followups(
        self,
        lead_id: str,
        campaign_id: str,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Schedule Day 3, Day 7, Day 14 follow-up reminders in followup_schedules.

        Args:
            lead_id: UUID of prospect lead.
            campaign_id: UUID of campaign owning the lead.
            user_id: Optional UUID of user for tenant ownership validation.

        Returns:
            List of created or existing pending followup schedule dictionaries.
        """
        if not lead_id or not campaign_id:
            raise ValueError("lead_id and campaign_id must be non-empty strings")

        # 1. Fetch lead
        lead_res = self._db.table("leads").select("*").eq("id", lead_id).execute()
        if not lead_res.data:
            logger.warning(f"Lead {lead_id} not found, skipping followup scheduling")
            return []

        lead = lead_res.data[0]
        if lead.get("campaign_id") != campaign_id:
            logger.warning(f"Lead {lead_id} does not belong to campaign {campaign_id}")
            raise ValueError(f"Lead {lead_id} does not belong to campaign {campaign_id}")

        if lead.get("is_suppressed") or lead.get("pipeline_stage") in TERMINAL_OR_ADVANCED_STAGES:
            logger.info(f"Lead {lead_id} is suppressed or in advanced stage; skipping followup scheduling")
            return []

        # 2. Fetch campaign and verify tenant ownership if user_id is provided
        camp_res = self._db.table("campaigns").select("*").eq("id", campaign_id).execute()
        if not camp_res.data:
            logger.warning(f"Campaign {campaign_id} not found")
            return []

        campaign = camp_res.data[0]
        if user_id and campaign.get("user_id") != user_id:
            raise ValueError(f"Campaign {campaign_id} does not belong to user {user_id}")

        wa_settings = campaign.get("whatsapp_settings") or {}

        max_attempts = int(wa_settings.get("max_followup_attempts", 3))
        # Clamp max attempts between 1 and 3 per decisions.md Section 10
        max_attempts = max(1, min(max_attempts, 3))
        gap_days = int(wa_settings.get("followup_gap_days", 3))

        # Default standard schedule: Day 3, Day 7, Day 14 (or scaled by gap_days)
        # Attempt 1: +gap_days
        # Attempt 2: +(gap_days * 2 + 1)
        # Attempt 3: +(gap_days * 4 + 2)
        interval_offsets = [
            gap_days,
            gap_days * 2 + 1,
            gap_days * 4 + 2,
        ]

        now_utc = datetime.now(timezone.utc)
        created_schedules: List[Dict[str, Any]] = []

        for attempt in range(1, max_attempts + 1):
            offset_days = interval_offsets[attempt - 1]
            raw_target = now_utc + timedelta(days=offset_days)
            scheduled_for = self.adjust_for_quiet_hours(raw_target)

            # Check if pending schedule for this attempt already exists
            existing_res = (
                self._db.table("followup_schedules")
                .select("*")
                .eq("lead_id", lead_id)
                .eq("attempt_number", attempt)
                .execute()
            )
            live_existing = [
                s for s in (existing_res.data or [])
                if s.get("status") in ("pending", "sent")
            ]

            if live_existing:
                created_schedules.append(live_existing[0])
                continue

            insert_payload = {
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "attempt_number": attempt,
                "status": "pending",
                "scheduled_for": scheduled_for.isoformat(),
            }
            res = self._db.table("followup_schedules").insert(insert_payload).execute()
            saved = res.data[0] if res.data else insert_payload
            created_schedules.append(saved)

        # Update lead next_followup_at to first scheduled time
        if created_schedules:
            earliest_time = min(s["scheduled_for"] for s in created_schedules)
            self._db.table("leads").update({"next_followup_at": earliest_time}).eq("id", lead_id).execute()

        logger.info(f"Scheduled {len(created_schedules)} follow-ups for lead {lead_id}")
        return created_schedules

    # -------------------------------------------------------------------------
    # Cancel Follow-ups (On reply, opt-out, manual closed, etc.)
    # -------------------------------------------------------------------------

    async def cancel_followups(
        self,
        lead_id: str,
        reason: str = "lead_replied",
        campaign_id: Optional[str] = None,
    ) -> int:
        """Cancel all pending followup_schedules for a lead and clear next_followup_at.

        Args:
            lead_id: UUID of prospect lead.
            reason: Human-readable cancellation reason (e.g. 'lead_replied', 'opted_out').
            campaign_id: Optional campaign UUID for tighter multi-tenant scoping.

        Returns:
            Number of cancelled schedules.
        """
        if not lead_id:
            return 0

        # Update all pending schedules to cancelled
        query = (
            self._db.table("followup_schedules")
            .update({
                "status": "cancelled",
                "cancellation_reason": reason,
            })
            .eq("lead_id", lead_id)
            .eq("status", "pending")
        )
        if campaign_id:
            query = query.eq("campaign_id", campaign_id)

        res = query.execute()
        cancelled_count = len(res.data or [])

        # Clear next_followup_at on lead
        lead_query = self._db.table("leads").update({"next_followup_at": None}).eq("id", lead_id)
        if campaign_id:
            lead_query = lead_query.eq("campaign_id", campaign_id)
        lead_query.execute()

        logger.info(f"Cancelled {cancelled_count} pending follow-ups for lead {lead_id} (reason: {reason})")
        return cancelled_count

    # -------------------------------------------------------------------------
    # Check Pending Follow-ups (Called hourly by scheduler or manually)
    # -------------------------------------------------------------------------

    async def check_pending_followups(self) -> Dict[str, Any]:
        """Query pending follow-ups due now, draft messages, and create approval tasks.

        Returns:
            Summary dict with counts of checked, drafted, cancelled, deferred, and exhausted.
        """
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        # 1. Fetch pending schedules whose scheduled_for is in the past or now
        pending_res = (
            self._db.table("followup_schedules")
            .select("*")
            .eq("status", "pending")
            .lte("scheduled_for", now_iso)
            .order("scheduled_for", desc=False)
            .execute()
        )
        schedules: List[Dict[str, Any]] = pending_res.data or []

        stats = {
            "checked": len(schedules),
            "drafted": 0,
            "cancelled": 0,
            "deferred": 0,
            "exhausted": 0,
            "errors": 0,
        }

        if not schedules:
            return stats

        # Evaluate current time for quiet hours
        in_quiet_now = self.is_quiet_hours(now_utc)

        for sched in schedules:
            sched_id = sched["id"]
            lead_id = sched["lead_id"]
            campaign_id = sched["campaign_id"]
            attempt_number = sched["attempt_number"]

            try:
                # 2. Quiet hours check: defer to 9:30 AM IST if currently in quiet hours
                if in_quiet_now:
                    deferred_time = self.adjust_for_quiet_hours(now_utc)
                    self._db.table("followup_schedules").update({
                        "scheduled_for": deferred_time.isoformat(),
                    }).eq("id", sched_id).execute()
                    self._db.table("leads").update({
                        "next_followup_at": deferred_time.isoformat(),
                    }).eq("id", lead_id).execute()
                    stats["deferred"] += 1
                    continue

                # 3. Fetch lead details
                lead_res = self._db.table("leads").select("*").eq("id", lead_id).execute()
                if not lead_res.data:
                    self._db.table("followup_schedules").update({
                        "status": "cancelled",
                        "cancellation_reason": "lead_deleted",
                    }).eq("id", sched_id).execute()
                    stats["cancelled"] += 1
                    continue

                lead = lead_res.data[0]
                stage = lead.get("pipeline_stage")

                # If lead is suppressed or already in terminal/advanced stage, cancel
                if lead.get("is_suppressed") or stage in TERMINAL_OR_ADVANCED_STAGES:
                    await self.cancel_followups(lead_id, reason=f"lead_stage_{stage or 'suppressed'}")
                    stats["cancelled"] += 1
                    continue

                # 4. Fetch campaign and verify user_id
                camp_res = self._db.table("campaigns").select("*").eq("id", campaign_id).execute()
                if not camp_res.data:
                    stats["errors"] += 1
                    continue

                campaign = camp_res.data[0]
                user_id = campaign.get("user_id")
                if not user_id:
                    stats["errors"] += 1
                    continue

                wa_settings = campaign.get("whatsapp_settings") or {}
                max_attempts = int(wa_settings.get("max_followup_attempts", 3))

                # Check if attempt exceeded campaign max
                if attempt_number > max_attempts:
                    self._db.table("followup_schedules").update({
                        "status": "skipped",
                        "cancellation_reason": "exceeds_campaign_max_attempts",
                    }).eq("id", sched_id).execute()
                    stats["cancelled"] += 1
                    continue

                # 5. Check if an outbound message for this attempt already exists
                existing_msg_res = (
                    self._db.table("whatsapp_messages")
                    .select("id, status")
                    .eq("lead_id", lead_id)
                    .eq("direction", "outbound")
                    .eq("followup_attempt", attempt_number)
                    .execute()
                )
                active_msgs = [
                    m for m in (existing_msg_res.data or [])
                    if m.get("status") not in ("failed", "cancelled")
                ]

                if active_msgs:
                    # Draft or sent message already created for this attempt; skip duplicate generation
                    continue

                # 6. Generate follow-up draft using MessageGeneratorService
                # Per decisions.md Section 10: Every message needs explicit human approval. No auto-send in V1.
                draft_resp = await self._message_generator.generate_draft(
                    lead_id=lead_id,
                    user_id=user_id,
                    followup_attempt=attempt_number,
                )

                # 7. Advance lead pipeline stage to 'followup_due'
                self._db.table("leads").update({
                    "pipeline_stage": "followup_due",
                }).eq("id", lead_id).execute()

                # 8. Create approval task in tasks table per database schema check constraint
                biz_name = lead.get("business_name") or "lead"
                task_payload = {
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": "approve_message",
                    "title": f"Review follow-up #{attempt_number} for {biz_name}",
                    "description": (
                        f"Follow-up #{attempt_number} draft is ready for review and approval. "
                        f"Recipient: {draft_resp.recipient_phone or biz_name}."
                    ),
                    "priority": "high",
                    "status": "pending",
                    "due_date": now_iso,
                }
                self._db.table("tasks").insert(task_payload).execute()

                # 9. Update next_followup_at to next pending schedule if available
                next_sched_res = (
                    self._db.table("followup_schedules")
                    .select("scheduled_for")
                    .eq("lead_id", lead_id)
                    .eq("status", "pending")
                    .gt("attempt_number", attempt_number)
                    .order("scheduled_for", desc=False)
                    .limit(1)
                    .execute()
                )
                if next_sched_res.data:
                    next_time = next_sched_res.data[0]["scheduled_for"]
                    self._db.table("leads").update({"next_followup_at": next_time}).eq("id", lead_id).execute()
                else:
                    self._db.table("leads").update({"next_followup_at": None}).eq("id", lead_id).execute()

                stats["drafted"] += 1
                logger.info(f"Generated follow-up draft #{attempt_number} for lead {lead_id}")

            except Exception as exc:
                logger.error(f"Error processing pending follow-up schedule {sched_id}: {exc}", exc_info=True)
                stats["errors"] += 1

        # 10. Check for exhausted leads with no response after final follow-up
        await self._check_exhausted_leads()

        return stats

    async def _check_exhausted_leads(self) -> int:
        """Mark leads as 'no_response' if all follow-ups were sent and grace period expired without reply."""
        exhausted_count = 0
        try:
            # Query leads currently in 'contacted' or 'followup_due'
            # and who have no pending follow-up scheduled
            leads_res = (
                self._db.table("leads")
                .select("id, campaign_id, pipeline_stage, last_contacted_at, next_followup_at")
                .in_("pipeline_stage", ["contacted", "followup_due"])
                .execute()
            )
            # Filter in Python for next_followup_at is None/empty for robust SQL NULL matching
            candidates = [
                l for l in (leads_res.data or [])
                if not l.get("next_followup_at")
            ]

            now_utc = datetime.now(timezone.utc)

            for cand in candidates:
                lead_id = cand["id"]
                last_contact = cand.get("last_contacted_at")
                if not last_contact:
                    continue

                try:
                    last_dt = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
                except Exception:
                    continue

                # Check if all scheduled follow-ups are completed or cancelled
                sched_res = (
                    self._db.table("followup_schedules")
                    .select("status")
                    .eq("lead_id", lead_id)
                    .execute()
                )
                schedules = sched_res.data or []
                if not schedules:
                    continue

                has_pending = any(s.get("status") == "pending" for s in schedules)
                if has_pending:
                    continue

                # If 5 days passed since the last message and no pending follow-up remains
                if (now_utc - last_dt) > timedelta(days=5):
                    self._db.table("leads").update({
                        "pipeline_stage": "no_response",
                    }).eq("id", lead_id).execute()
                    exhausted_count += 1
                    logger.info(f"Marked lead {lead_id} as 'no_response' (all follow-ups exhausted)")

        except Exception as exc:
            logger.debug(f"Exhausted leads evaluation note: {exc}")

        return exhausted_count

