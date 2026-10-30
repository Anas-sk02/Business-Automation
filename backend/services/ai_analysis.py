"""AI Analysis and Orchestration Service for Stage 4: AI Analysis & Scoring.

Orchestrates the complete lead analysis pipeline conforming to:
- docs/decisions.md Sections 5, 6, 7, 9, 11
- docs/prompts.md Section 1
- docs/implementation.md Stage 4
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set

from backend.database import get_supabase_client
from backend.models.analysis import (
    AIAnalysisResult,
    ScoreResult,
    VerificationResult,
)
from backend.prompts.business_analysis import build_business_analysis_prompt
from backend.services.ai_client import AIClient
from backend.services.scoring import ScoringService
from backend.services.verification import VerificationService

logger = logging.getLogger("signalforge.analysis")

# Concurrency semaphore for batch analysis per decisions.md Section 9
BATCH_ANALYSIS_SEMAPHORE = asyncio.Semaphore(3)

# Stages that must never regress backwards when an analysis is completed
TERMINAL_OR_ADVANCED_STAGES: Set[str] = {
    "contacted",
    "replied",
    "interested",
    "not_interested",
    "opted_out",
    "followup_due",
    "no_response",
    "call_scheduled",
    "negotiation",
    "won",
    "closed_lost",
}


class LeadNotFoundError(Exception):
    """Raised when the specified lead is not found or does not belong to the user."""


class CampaignBudgetExceededError(Exception):
    """Raised when executing AI analysis would exceed campaign budget limit."""


class AnalysisExecutionError(Exception):
    """Raised when AI invocation or parsing fails."""


class AIAnalysisService:
    """Service managing business analysis, evidence cross-verification, scoring, and stage updates."""

    def __init__(
        self,
        db_client: Any = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        """Initialize AIAnalysisService with dependency injection support."""
        self._db = db_client or get_supabase_client()
        self._ai_client = ai_client or AIClient(db_client=self._db)

    @staticmethod
    def check_campaign_budget(
        campaign: Dict[str, Any],
        estimated_cost_inr: float = 1.0,
    ) -> bool:
        """Check whether campaign budget allows executing the next paid AI operation.

        Per docs/decisions.md Section 11:
        Stop when spent_amount would exceed max_budget. max_budget = 0 means no limit.
        """
        max_budget = float(campaign.get("max_budget") or 0.0)
        spent_amount = float(campaign.get("spent_amount") or 0.0)

        if max_budget <= 0.0:
            return True

        return (spent_amount + estimated_cost_inr) <= max_budget

    async def analyze_lead(
        self,
        lead_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Orchestrate the complete AI analysis, verification, scoring, and stage update for a lead.

        Args:
            lead_id: UUID of lead to analyze.
            user_id: UUID of authenticated user owning the lead and campaign.

        Returns:
            Dictionary containing created analysis, scoring result, and updated lead state.

        Raises:
            LeadNotFoundError: If lead does not exist or user does not own it.
            CampaignBudgetExceededError: If campaign has exceeded maximum budget.
            AnalysisExecutionError: If AI generation fails after retries.
        """
        if not lead_id or not str(lead_id).strip():
            raise ValueError("lead_id is required")
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required")

        # 1. Fetch lead + parent campaign with strict tenant scoping
        lead_query = (
            self._db.table("leads")
            .select("*, campaigns!inner(*)")
            .eq("id", lead_id)
            .eq("campaigns.user_id", user_id)
            .execute()
        )
        if not lead_query.data:
            raise LeadNotFoundError(f"Lead {lead_id} not found or access denied for user {user_id}")

        lead = lead_query.data[0]
        campaign = lead.get("campaigns") or {}
        campaign_id = campaign.get("id") or lead.get("campaign_id")

        # 2. Check campaign budget before paid AI invocation (decisions.md Section 11)
        # Gemini flash cost is approx $0.0003 (~0.03 INR), we conservatively check 0.05 INR
        if not self.check_campaign_budget(campaign, estimated_cost_inr=0.05):
            logger.warning(
                f"Campaign {campaign_id} budget exceeded (spent={campaign.get('spent_amount')}, max={campaign.get('max_budget')}). Halting AI analysis for lead {lead_id}."
            )
            raise CampaignBudgetExceededError(
                f"Campaign budget of {campaign.get('max_budget')} would be exceeded"
            )

        # 3. Fetch latest website audit data
        audit: Dict[str, Any] = {}
        try:
            audit_res = (
                self._db.table("website_audits")
                .select("*")
                .eq("lead_id", lead_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if audit_res.data:
                audit = audit_res.data[0]
        except Exception as e:
            logger.error(f"Failed to query website_audits for lead {lead_id}: {e}")

        # 4. Fetch evidence items
        evidence_items: List[Dict[str, Any]] = []
        try:
            ev_res = (
                self._db.table("evidence_items")
                .select("*")
                .eq("lead_id", lead_id)
                .execute()
            )
            if ev_res.data:
                evidence_items = ev_res.data
        except Exception as e:
            logger.error(f"Failed to query evidence_items for lead {lead_id}: {e}")

        # 5. Build grounded business analysis prompt
        prompt_text = build_business_analysis_prompt(
            lead=lead,
            campaign=campaign,
            audit=audit,
            evidence_items=evidence_items,
        )

        # 6. Call AI API with structured output and automatic retry
        try:
            ai_result = await self._ai_client.generate_structured_output(
                prompt=prompt_text,
                schema_class=AIAnalysisResult,
                campaign_id=campaign_id,
                user_id=user_id,
                service="ai_analysis",
                operation="analyze_lead",
                metadata={"lead_id": lead_id},
            )
        except Exception as e:
            logger.error(f"AI generation failed for lead {lead_id}: {e}")
            raise AnalysisExecutionError(f"AI generation failed: {e}") from e

        analysis_output: AIAnalysisResult = ai_result.parsed

        # 7. Run claim verification against audit evidence (decisions.md Section 7)
        verification: VerificationResult = VerificationService.verify_claims(
            analysis_result=analysis_output,
            evidence_items=evidence_items,
        )

        # 8. Calculate deterministic Lead Fit Score (decisions.md Section 6)
        score_res: ScoreResult = ScoringService.calculate_score(
            lead=lead,
            campaign=campaign,
            audit=audit,
            evidence_items=evidence_items,
            verification_result=verification,
        )

        # 9. Insert public.ai_analyses record
        now_iso = datetime.now(timezone.utc).isoformat()
        analysis_payload = {
            "lead_id": lead_id,
            "model_used": ai_result.model_used,
            "prompt_version": "v1",
            "analysis_result": analysis_output.model_dump(),
            "recommended_service": analysis_output.recommended_service,
            "pitch_angle": analysis_output.pitch_angle,
            "confidence": verification.confidence,
            "claim_verifications": [item.model_dump() for item in verification.items],
            "total_claims": verification.total_claims,
            "verified_claims": verification.verified_claims,
            "unverified_claims": verification.unverified_claims,
            "contradicted_claims": verification.contradicted_claims,
            "input_tokens": ai_result.input_tokens,
            "output_tokens": ai_result.output_tokens,
            "api_cost_usd": ai_result.cost_usd,
            "analyzed_at": now_iso,
        }

        try:
            insert_res = self._db.table("ai_analyses").insert(analysis_payload).execute()
            saved_analysis = insert_res.data[0] if insert_res.data else analysis_payload
        except Exception as e:
            logger.error(f"Failed to insert ai_analyses record for lead {lead_id}: {e}")
            raise AnalysisExecutionError(f"Database insertion failed: {e}") from e

        # 10. Update lead fit_score, score_breakdown, score_reasons, and pipeline_stage
        current_stage = str(lead.get("pipeline_stage") or "discovered").lower()
        new_stage = current_stage

        # Automatic transitions per decisions.md Section 5 & Section 6:
        # If score >= 60 AND has_valid_phone: lead advances to 'qualified'
        if score_res.qualifies:
            new_stage = "qualified"
        elif current_stage in ("discovered", "research_pending"):
            # If not qualifying, but analysis has completed, it is in 'researched' stage
            new_stage = "researched"
        elif current_stage in TERMINAL_OR_ADVANCED_STAGES:
            # Do NOT regress stages that have progressed to contacted, replied, won, etc.
            new_stage = current_stage
        else:
            new_stage = "researched"

        lead_update_payload = {
            "fit_score": score_res.fit_score,
            "score_breakdown": score_res.breakdown.model_dump(),
            "score_reasons": score_res.reasons,
            "pipeline_stage": new_stage,
            "updated_at": now_iso,
        }

        try:
            self._db.table("leads").update(lead_update_payload).eq("id", lead_id).execute()
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id} with scoring results: {e}")
            raise AnalysisExecutionError(f"Failed to update lead status: {e}") from e

        logger.info(
            f"Successfully completed AI analysis for lead {lead_id}: score={score_res.fit_score}, stage={new_stage}"
        )

        return {
            "analysis": saved_analysis,
            "scoring": score_res.model_dump(),
            "verification": verification.model_dump(),
            "pipeline_stage": new_stage,
            "lead_id": lead_id,
        }

    async def analyze_campaign_leads(
        self,
        campaign_id: str,
        user_id: str,
        lead_ids: Optional[List[str]] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Batch process AI analysis for eligible campaign leads.

        Args:
            campaign_id: UUID of campaign.
            user_id: UUID of campaign owner.
            lead_ids: Optional explicit list of lead UUIDs to analyze.
            limit: Maximum number of leads to process in one batch (default 50).

        Returns:
            Summary dictionary with processed, qualified, failed counts and error details.
        """
        if not campaign_id or not str(campaign_id).strip():
            raise ValueError("campaign_id is required")
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required")

        # 1. Verify campaign ownership
        camp_res = (
            self._db.table("campaigns")
            .select("id, user_id, spent_amount, max_budget, status")
            .eq("id", campaign_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not camp_res.data:
            raise LeadNotFoundError(f"Campaign {campaign_id} not found or access denied for user {user_id}")

        campaign = camp_res.data[0]

        # Check for campaign pause/stop (decisions.md Section 9)
        if campaign.get("status") in ("paused", "stopped", "archived"):
            logger.info(
                f"Campaign {campaign_id} status is '{campaign.get('status')}'; skipping batch analysis."
            )
            return {
                "campaign_id": campaign_id,
                "total_eligible": 0,
                "processed": 0,
                "qualified": 0,
                "failed": 0,
                "errors": [{"error": f"Campaign is {campaign.get('status')}"}],
            }

        # 2. Select eligible leads
        leads_query = (
            self._db.table("leads")
            .select("id, pipeline_stage")
            .eq("campaign_id", campaign_id)
        )
        if lead_ids:
            leads_query = leads_query.in_("id", lead_ids)
        else:
            # By default, analyze leads in researched or discovered stages that haven't been qualified
            leads_query = leads_query.in_("pipeline_stage", ["researched", "discovered"])

        leads_query = leads_query.limit(limit)
        leads_res = leads_query.execute()
        candidate_leads = leads_res.data or []

        total_eligible = len(candidate_leads)
        if total_eligible == 0:
            return {
                "campaign_id": campaign_id,
                "total_eligible": 0,
                "processed": 0,
                "qualified": 0,
                "failed": 0,
                "errors": [],
            }

        # 3. Process candidate leads with concurrency control
        processed = 0
        qualified = 0
        failed = 0
        budget_exhausted = False
        errors: List[Dict[str, str]] = []

        async def _process_single(target_id: str) -> None:
            nonlocal processed, qualified, failed, budget_exhausted
            if budget_exhausted:
                failed += 1
                errors.append({"lead_id": target_id, "error": "Skipped: campaign budget exhausted"})
                return

            async with BATCH_ANALYSIS_SEMAPHORE:
                if budget_exhausted:
                    failed += 1
                    errors.append({"lead_id": target_id, "error": "Skipped: campaign budget exhausted"})
                    return

                try:
                    res = await self.analyze_lead(lead_id=target_id, user_id=user_id)
                    processed += 1
                    if res.get("pipeline_stage") == "qualified":
                        qualified += 1
                except CampaignBudgetExceededError as e:
                    budget_exhausted = True
                    failed += 1
                    errors.append({"lead_id": target_id, "error": f"Budget exceeded: {e}"})
                except Exception as e:
                    failed += 1
                    errors.append({"lead_id": target_id, "error": str(e)})

        tasks = [_process_single(lead_item["id"]) for lead_item in candidate_leads]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "campaign_id": campaign_id,
            "total_eligible": total_eligible,
            "processed": processed,
            "qualified": qualified,
            "failed": failed,
            "errors": errors,
        }
