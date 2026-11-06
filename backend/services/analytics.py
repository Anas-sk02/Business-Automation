"""Analytics and Performance Aggregation Engine.

Computes conversion funnels, messaging performance, and spend metrics
strictly scoped to authenticated tenants per docs/decisions.md and docs/UI-UX.md.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from backend.database import get_supabase_client
from backend.models.analytics import (
    AnalyticsKPIs,
    AnalyticsOverviewResponse,
    CampaignAnalyticsResponse,
    CostBreakdown,
    CostsOverviewResponse,
    FunnelStep,
    MessagingMetrics,
    ServiceCostItem,
)

logger = logging.getLogger("signalforge.analytics")

# Canonical 6 services for API cost tracking per database-schema.md
CANONICAL_SERVICES = [
    "google_places",
    "ai_analysis",
    "ai_classification",
    "ai_message_gen",
    "whatsapp",
    "lighthouse",
]

# Pipeline stages mapped to downstream conversion thresholds per decisions.md §5
QUALIFIED_AND_ABOVE: Set[str] = {
    "qualified",
    "contacted",
    "followup_due",
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
}

CONTACTED_AND_ABOVE: Set[str] = {
    "contacted",
    "followup_due",
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
}

REPLIED_AND_ABOVE: Set[str] = {
    "replied",
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
}

INTERESTED_AND_ABOVE: Set[str] = {
    "interested",
    "meeting_scheduled",
    "proposal_sent",
    "negotiation",
    "won",
}


class AnalyticsService:
    """Service for computing user-scoped analytics, funnels, messaging, and cost metrics."""

    def __init__(self, db_client: Any = None) -> None:
        """Initialize with an optional injected database client."""
        self._db = db_client or get_supabase_client()

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    async def get_overview_analytics(
        self,
        user_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> AnalyticsOverviewResponse:
        """Compute aggregated analytics across all campaigns owned by a user."""
        self._validate_user_id(user_id)
        self._validate_dates(from_date, to_date)

        campaigns = self._get_user_campaigns(user_id)
        if not campaigns:
            return self._build_empty_overview()

        campaign_ids = [c["id"] for c in campaigns]
        return self._aggregate_metrics(
            campaign_ids=campaign_ids,
            total_campaigns=len(campaigns),
            from_date=from_date,
            to_date=to_date,
        )

    async def get_campaign_analytics(
        self,
        user_id: str,
        campaign_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> CampaignAnalyticsResponse:
        """Compute metrics scoped to a specific campaign owned by the user."""
        self._validate_user_id(user_id)
        if not campaign_id or not isinstance(campaign_id, str) or not campaign_id.strip():
            raise ValueError("A valid campaign_id is required")
        self._validate_dates(from_date, to_date)

        campaign = self._get_owned_campaign(user_id, campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found or unowned")

        overview = self._aggregate_metrics(
            campaign_ids=[campaign_id],
            total_campaigns=1,
            from_date=from_date,
            to_date=to_date,
        )

        return CampaignAnalyticsResponse(
            campaign_id=campaign["id"],
            campaign_name=campaign.get("name", "Unnamed Campaign"),
            has_sent_messages=overview.has_sent_messages,
            kpis=overview.kpis,
            funnel=overview.funnel,
            messaging=overview.messaging,
            costs=overview.costs,
        )

    async def get_cost_breakdown(
        self,
        user_id: str,
        campaign_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> CostsOverviewResponse:
        """Compute cost and usage breakdown for a user or a specific owned campaign."""
        self._validate_user_id(user_id)
        self._validate_dates(from_date, to_date)

        if campaign_id:
            campaign = self._get_owned_campaign(user_id, campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found or unowned")
            campaign_ids = [campaign_id]
        else:
            campaigns = self._get_user_campaigns(user_id)
            if not campaigns:
                return CostsOverviewResponse(
                    services=[ServiceCostItem(service=s, api_calls=0, cost_usd=0.0, cost_inr=0.0) for s in CANONICAL_SERVICES],
                    total_spend_usd=0.0,
                    total_spend_inr=0.0,
                    total_businesses_processed=0,
                    cost_per_qualified_lead_inr=None,
                    cost_per_won_deal_inr=None,
                    cost_per_acquired_lead_inr=None,
                )
            campaign_ids = [c["id"] for c in campaigns]

        # Fetch leads count for businesses processed & qualified leads
        leads = self._fetch_leads_for_campaigns(campaign_ids, from_date, to_date)
        total_leads = len(leads)
        total_qualified = sum(1 for l in leads if l.get("pipeline_stage") in QUALIFIED_AND_ABOVE or (l.get("fit_score") or 0) >= 60)
        total_won = sum(1 for l in leads if l.get("pipeline_stage") == "won")

        cost_breakdown = self._compute_costs(campaign_ids, total_qualified, total_won, from_date, to_date)

        return CostsOverviewResponse(
            services=cost_breakdown.services,
            total_spend_usd=cost_breakdown.total_spend_usd,
            total_spend_inr=cost_breakdown.total_spend_inr,
            total_businesses_processed=total_leads,
            cost_per_qualified_lead_inr=cost_breakdown.cost_per_qualified_lead_inr,
            cost_per_won_deal_inr=cost_breakdown.cost_per_won_deal_inr,
            cost_per_acquired_lead_inr=cost_breakdown.cost_per_won_deal_inr,
        )

    def _validate_user_id(self, user_id: str) -> None:
        """Ensure non-empty user_id is provided."""
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("A valid user_id is required")

    def _validate_dates(
        self, from_date: Optional[datetime], to_date: Optional[datetime]
    ) -> None:
        """Validate logical ordering of date range filters."""
        if from_date and to_date and from_date > to_date:
            raise ValueError("from_date cannot be later than to_date")

    # -------------------------------------------------------------------------
    # Internal Aggregation Helpers
    # -------------------------------------------------------------------------

    def _aggregate_metrics(
        self,
        campaign_ids: List[str],
        total_campaigns: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> AnalyticsOverviewResponse:
        """Aggregate funnel, messaging, and cost metrics for given campaign IDs."""
        leads = self._fetch_leads_for_campaigns(campaign_ids, from_date, to_date)
        lead_ids = [l["id"] for l in leads]

        audited_lead_ids = self._fetch_audited_lead_ids(lead_ids, from_date, to_date)
        messages = self._fetch_messages_for_campaigns(campaign_ids, from_date, to_date)

        # 1. Funnel Computation
        funnel, qualified_count, won_count = self._compute_funnel(leads, audited_lead_ids, messages)

        # 2. Messaging Metrics
        messaging = self._compute_messaging_metrics(messages, leads)
        has_sent_messages = messaging.total_sent > 0

        # 3. Cost Metrics
        costs = self._compute_costs(campaign_ids, qualified_count, won_count, from_date, to_date)

        # 4. Top-level KPIs
        kpis = AnalyticsKPIs(
            total_campaigns=total_campaigns,
            total_leads_found=len(leads),
            total_audited=len(audited_lead_ids),
            total_qualified=qualified_count,
            total_messages_sent=messaging.total_sent,
            total_deals_won=won_count,
            total_spend_usd=costs.total_spend_usd,
            total_spend_inr=costs.total_spend_inr,
        )

        return AnalyticsOverviewResponse(
            has_sent_messages=has_sent_messages,
            kpis=kpis,
            funnel=funnel,
            messaging=messaging,
            costs=costs,
        )

    def _compute_funnel(
        self,
        leads: List[Dict[str, Any]],
        audited_lead_ids: Set[str],
        messages: List[Dict[str, Any]],
    ) -> tuple[List[FunnelStep], int, int]:
        """Compute the 7-step horizontal funnel per docs/UI-UX.md Section 6.11."""
        total_found = len(leads)

        # Identify contacted and replied leads from message logs and lead stages
        contacted_lead_ids = {
            m["lead_id"]
            for m in messages
            if m.get("direction") == "outbound" and m.get("status") in {"sent", "delivered", "read", "replied"}
        }
        replied_lead_ids = {
            m["lead_id"]
            for m in messages
            if m.get("direction") == "inbound" or m.get("status") == "replied"
        }

        # Step 1: Leads found
        count_found = total_found

        # Step 2: Audited
        count_audited = sum(
            1
            for l in leads
            if l["id"] in audited_lead_ids or l.get("pipeline_stage") in QUALIFIED_AND_ABOVE
        )

        # Step 3: Qualified (fit score >= 60 or advanced stage)
        count_qualified = sum(
            1
            for l in leads
            if l.get("pipeline_stage") in QUALIFIED_AND_ABOVE or (l.get("fit_score") or 0) >= 60
        )

        # Step 4: Contacted
        count_contacted = sum(
            1
            for l in leads
            if l["id"] in contacted_lead_ids or l.get("pipeline_stage") in CONTACTED_AND_ABOVE
        )

        # Step 5: Replied
        count_replied = sum(
            1
            for l in leads
            if l["id"] in replied_lead_ids or l.get("pipeline_stage") in REPLIED_AND_ABOVE
        )

        # Step 6: Interested
        count_interested = sum(
            1
            for l in leads
            if l.get("pipeline_stage") in INTERESTED_AND_ABOVE
        )

        # Step 7: Won
        count_won = sum(
            1
            for l in leads
            if l.get("pipeline_stage") == "won"
        )

        raw_counts = [
            ("Found", count_found),
            ("Audited", count_audited),
            ("Qualified", count_qualified),
            ("Contacted", count_contacted),
            ("Replied", count_replied),
            ("Interested", count_interested),
            ("Won", count_won),
        ]

        funnel_steps: List[FunnelStep] = []
        for i, (name, count) in enumerate(raw_counts):
            if i == 0:
                conv_rate = 100.0 if count > 0 else 0.0
            else:
                prev_count = raw_counts[i - 1][1]
                conv_rate = round((count / prev_count) * 100.0, 1) if prev_count > 0 else 0.0

            overall_rate = round((count / count_found) * 100.0, 1) if count_found > 0 else 0.0
            funnel_steps.append(
                FunnelStep(
                    name=name,
                    count=count,
                    conversion_rate=min(conv_rate, 100.0),
                    overall_rate=min(overall_rate, 100.0),
                )
            )

        return funnel_steps, count_qualified, count_won

    def _compute_messaging_metrics(
        self,
        messages: List[Dict[str, Any]],
        leads: List[Dict[str, Any]],
    ) -> MessagingMetrics:
        """Compute delivery and response performance metrics."""
        outbound = [m for m in messages if m.get("direction") == "outbound"]
        sent_messages = [
            m for m in outbound if m.get("status") in {"sent", "delivered", "read", "replied"}
        ]
        total_sent = len(sent_messages)

        delivered_messages = [
            m for m in outbound if m.get("status") in {"delivered", "read", "replied"}
        ]
        total_delivered = len(delivered_messages)

        read_messages = [m for m in outbound if m.get("status") in {"read", "replied"}]
        total_read = len(read_messages)

        # Replied leads: inbound replies + outbound messages marked replied
        inbound_leads = {m["lead_id"] for m in messages if m.get("direction") == "inbound"}
        outbound_replied = {m["lead_id"] for m in outbound if m.get("status") == "replied"}
        total_replied = len(inbound_leads.union(outbound_replied))

        total_failed = sum(1 for m in outbound if m.get("status") == "failed")
        total_opted_out = sum(
            1 for l in leads if l.get("pipeline_stage") == "opted_out" or l.get("is_suppressed")
        )

        delivery_rate = round((total_delivered / total_sent) * 100.0, 1) if total_sent > 0 else 0.0
        read_rate = round((total_read / total_delivered) * 100.0, 1) if total_delivered > 0 else 0.0
        reply_rate = round((total_replied / total_sent) * 100.0, 1) if total_sent > 0 else 0.0

        return MessagingMetrics(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_read=total_read,
            total_replied=total_replied,
            total_failed=total_failed,
            total_opted_out=total_opted_out,
            delivery_rate=min(delivery_rate, 100.0),
            read_rate=min(read_rate, 100.0),
            reply_rate=min(reply_rate, 100.0),
        )

    def _compute_costs(
        self,
        campaign_ids: List[str],
        total_qualified: int,
        total_won: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> CostBreakdown:
        """Aggregate per-service API costs and unit economics."""
        if not campaign_ids:
            return CostBreakdown(
                services=[ServiceCostItem(service=s, api_calls=0, cost_usd=0.0, cost_inr=0.0) for s in CANONICAL_SERVICES],
                total_spend_usd=0.0,
                total_spend_inr=0.0,
                cost_per_qualified_lead_inr=None,
                cost_per_won_deal_inr=None,
            )

        query = self._db.table("api_costs").select("*").in_("campaign_id", campaign_ids)
        if from_date:
            query = query.gte("created_at", from_date.isoformat())
        if to_date:
            query = query.lte("created_at", to_date.isoformat())

        try:
            res = query.execute()
            cost_records = res.data or []
        except Exception as exc:
            logger.error("Failed to query api_costs: %s", exc)
            raise RuntimeError(f"Database error fetching api_costs: {exc}") from exc

        service_map: Dict[str, Dict[str, Any]] = {
            s: {"api_calls": 0, "cost_usd": 0.0, "cost_inr": 0.0} for s in CANONICAL_SERVICES
        }

        total_usd = 0.0
        total_inr = 0.0

        for r in cost_records:
            service = r.get("service", "other")
            calls = r.get("api_calls") or 1
            usd = float(r.get("cost_usd") or 0.0)
            inr = float(r.get("cost_inr") or 0.0)

            if service not in service_map:
                service_map[service] = {"api_calls": 0, "cost_usd": 0.0, "cost_inr": 0.0}

            service_map[service]["api_calls"] += calls
            service_map[service]["cost_usd"] += usd
            service_map[service]["cost_inr"] += inr

            total_usd += usd
            total_inr += inr

        services_list = [
            ServiceCostItem(
                service=s,
                api_calls=data["api_calls"],
                cost_usd=round(data["cost_usd"], 4),
                cost_inr=round(data["cost_inr"], 2),
            )
            for s, data in service_map.items()
        ]

        cost_per_qualified = (
            round(total_inr / total_qualified, 2) if total_qualified > 0 else None
        )
        cost_per_won = round(total_inr / total_won, 2) if total_won > 0 else None

        return CostBreakdown(
            services=services_list,
            total_spend_usd=round(total_usd, 4),
            total_spend_inr=round(total_inr, 2),
            cost_per_qualified_lead_inr=cost_per_qualified,
            cost_per_won_deal_inr=cost_per_won,
        )

    # -------------------------------------------------------------------------
    # Database Fetch Helpers
    # -------------------------------------------------------------------------

    def _get_user_campaigns(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch all campaigns owned by a specific user."""
        try:
            res = self._db.table("campaigns").select("id, name").eq("user_id", user_id).execute()
            return res.data or []
        except Exception as exc:
            logger.error("Failed to query user campaigns for %s: %s", user_id, exc)
            raise RuntimeError(f"Database error fetching campaigns: {exc}") from exc

    def _get_owned_campaign(self, user_id: str, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific campaign ensuring ownership."""
        try:
            res = (
                self._db.table("campaigns")
                .select("id, name")
                .eq("user_id", user_id)
                .eq("id", campaign_id)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as exc:
            logger.error("Failed to query campaign %s for %s: %s", campaign_id, user_id, exc)
            raise RuntimeError(f"Database error fetching campaign: {exc}") from exc

    def _fetch_leads_for_campaigns(
        self,
        campaign_ids: List[str],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch leads for specified campaigns with optional date filtering."""
        if not campaign_ids:
            return []
        try:
            query = self._db.table("leads").select("id, campaign_id, pipeline_stage, fit_score, is_suppressed, created_at").in_("campaign_id", campaign_ids)
            if from_date:
                query = query.gte("created_at", from_date.isoformat())
            if to_date:
                query = query.lte("created_at", to_date.isoformat())
            res = query.execute()
            return res.data or []
        except Exception as exc:
            logger.error("Failed to fetch leads for campaigns: %s", exc)
            raise RuntimeError(f"Database error fetching leads: {exc}") from exc

    def _fetch_audited_lead_ids(
        self,
        lead_ids: List[str],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Set[str]:
        """Fetch distinct lead IDs that have an audit recorded."""
        if not lead_ids:
            return set()
        try:
            query = self._db.table("website_audits").select("lead_id, status, created_at").in_("lead_id", lead_ids)
            if from_date:
                query = query.gte("created_at", from_date.isoformat())
            if to_date:
                query = query.lte("created_at", to_date.isoformat())
            res = query.execute()
            return {r["lead_id"] for r in (res.data or []) if r.get("status") in {"completed", "running"}}
        except Exception as exc:
            logger.error("Failed to fetch audited lead IDs: %s", exc)
            raise RuntimeError(f"Database error fetching audits: {exc}") from exc

    def _fetch_messages_for_campaigns(
        self,
        campaign_ids: List[str],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch WhatsApp messages for given campaign IDs."""
        if not campaign_ids:
            return []
        try:
            query = self._db.table("whatsapp_messages").select("id, lead_id, campaign_id, direction, status, created_at").in_("campaign_id", campaign_ids)
            if from_date:
                query = query.gte("created_at", from_date.isoformat())
            if to_date:
                query = query.lte("created_at", to_date.isoformat())
            res = query.execute()
            return res.data or []
        except Exception as exc:
            logger.error("Failed to fetch messages for campaigns: %s", exc)
            raise RuntimeError(f"Database error fetching messages: {exc}") from exc

    def _build_empty_overview(self) -> AnalyticsOverviewResponse:
        """Construct an honest zero-state envelope for users with no campaigns."""
        empty_funnel = [
            FunnelStep(name=name, count=0, conversion_rate=0.0, overall_rate=0.0)
            for name in ["Found", "Audited", "Qualified", "Contacted", "Replied", "Interested", "Won"]
        ]
        empty_messaging = MessagingMetrics(
            total_sent=0,
            total_delivered=0,
            total_read=0,
            total_replied=0,
            total_failed=0,
            total_opted_out=0,
            delivery_rate=0.0,
            read_rate=0.0,
            reply_rate=0.0,
        )
        empty_costs = CostBreakdown(
            services=[
                ServiceCostItem(service=s, api_calls=0, cost_usd=0.0, cost_inr=0.0)
                for s in CANONICAL_SERVICES
            ],
            total_spend_usd=0.0,
            total_spend_inr=0.0,
            cost_per_qualified_lead_inr=None,
            cost_per_won_deal_inr=None,
        )
        empty_kpis = AnalyticsKPIs(
            total_campaigns=0,
            total_leads_found=0,
            total_audited=0,
            total_qualified=0,
            total_messages_sent=0,
            total_deals_won=0,
            total_spend_usd=0.0,
            total_spend_inr=0.0,
        )

        return AnalyticsOverviewResponse(
            has_sent_messages=False,
            kpis=empty_kpis,
            funnel=empty_funnel,
            messaging=empty_messaging,
            costs=empty_costs,
        )

