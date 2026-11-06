"""Tests for AnalyticsService and Analytics Pydantic models.

Verifies calculation accuracy, division-by-zero safety, multi-tenant isolation,
and funnel metrics per docs/decisions.md and docs/UI-UX.md Section 6.11.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from backend.services.analytics import AnalyticsService
from backend.models.analytics import (
    AnalyticsOverviewResponse,
    CampaignAnalyticsResponse,
    CostsOverviewResponse,
)


@pytest.fixture
def mock_db():
    """Mock Supabase database client."""
    db = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    """Instantiate AnalyticsService with mocked DB."""
    return AnalyticsService(db_client=mock_db)


@pytest.mark.anyio
async def test_empty_overview_when_user_has_no_campaigns(service, mock_db):
    """Verify honest empty state with 0s and has_sent_messages=False when user has no campaigns."""
    mock_campaigns_query = MagicMock()
    mock_campaigns_query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_db.table.return_value = mock_campaigns_query

    res = await service.get_overview_analytics(user_id="user-empty-123")

    assert isinstance(res, AnalyticsOverviewResponse)
    assert res.has_sent_messages is False
    assert res.kpis.total_campaigns == 0
    assert res.kpis.total_leads_found == 0
    assert res.kpis.total_messages_sent == 0
    assert len(res.funnel) == 7
    for step in res.funnel:
        assert step.count == 0
        assert step.conversion_rate == 0.0
        assert step.overall_rate == 0.0
    assert res.messaging.total_sent == 0
    assert res.messaging.delivery_rate == 0.0
    assert res.costs.total_spend_usd == 0.0
    assert res.costs.total_spend_inr == 0.0
    assert res.costs.cost_per_qualified_lead_inr is None


@pytest.mark.anyio
async def test_overview_analytics_with_full_funnel_and_messaging(service, mock_db):
    """Verify conversion funnel step math, message rates, and cost calculations."""
    campaign_id = "camp-123"

    # Setup mock data
    mock_campaigns = [{"id": campaign_id, "name": "Dental Outreach Pune"}]

    mock_leads = [
        {"id": "l-1", "campaign_id": campaign_id, "pipeline_stage": "won", "fit_score": 85, "is_suppressed": False},
        {"id": "l-2", "campaign_id": campaign_id, "pipeline_stage": "interested", "fit_score": 75, "is_suppressed": False},
        {"id": "l-3", "campaign_id": campaign_id, "pipeline_stage": "replied", "fit_score": 70, "is_suppressed": False},
        {"id": "l-4", "campaign_id": campaign_id, "pipeline_stage": "contacted", "fit_score": 65, "is_suppressed": False},
        {"id": "l-5", "campaign_id": campaign_id, "pipeline_stage": "qualified", "fit_score": 60, "is_suppressed": False},
        {"id": "l-6", "campaign_id": campaign_id, "pipeline_stage": "evaluating", "fit_score": 40, "is_suppressed": False},
        {"id": "l-7", "campaign_id": campaign_id, "pipeline_stage": "discovered", "fit_score": 30, "is_suppressed": False},
        {"id": "l-8", "campaign_id": campaign_id, "pipeline_stage": "opted_out", "fit_score": 50, "is_suppressed": True},
    ]

    mock_audits = [
        {"lead_id": "l-1", "status": "completed"},
        {"lead_id": "l-2", "status": "completed"},
        {"lead_id": "l-3", "status": "completed"},
        {"lead_id": "l-4", "status": "completed"},
        {"lead_id": "l-5", "status": "completed"},
        {"lead_id": "l-6", "status": "completed"},
    ]

    mock_messages = [
        {"id": "m-1", "lead_id": "l-1", "campaign_id": campaign_id, "direction": "outbound", "status": "replied"},
        {"id": "m-2", "lead_id": "l-2", "campaign_id": campaign_id, "direction": "outbound", "status": "read"},
        {"id": "m-3", "lead_id": "l-3", "campaign_id": campaign_id, "direction": "outbound", "status": "delivered"},
        {"id": "m-4", "lead_id": "l-4", "campaign_id": campaign_id, "direction": "outbound", "status": "sent"},
        {"id": "m-5", "lead_id": "l-5", "campaign_id": campaign_id, "direction": "outbound", "status": "failed"},
        {"id": "m-in-1", "lead_id": "l-1", "campaign_id": campaign_id, "direction": "inbound", "status": "delivered"},
    ]

    mock_costs = [
        {"service": "google_places", "api_calls": 5, "cost_usd": 0.15, "cost_inr": 12.50},
        {"service": "ai_analysis", "api_calls": 6, "cost_usd": 0.05, "cost_inr": 4.20},
        {"service": "whatsapp", "api_calls": 4, "cost_usd": 0.00, "cost_inr": 0.00},
    ]

    def table_router(table_name):
        query = MagicMock()
        if table_name == "campaigns":
            query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
        elif table_name == "leads":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
        elif table_name == "website_audits":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_audits)
        elif table_name == "whatsapp_messages":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_messages)
        elif table_name == "api_costs":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_costs)
        return query

    mock_db.table.side_effect = table_router

    res = await service.get_overview_analytics(user_id="user-1")

    assert res.has_sent_messages is True
    assert res.kpis.total_campaigns == 1
    assert res.kpis.total_leads_found == 8
    assert res.kpis.total_deals_won == 1

    # Check Funnel
    funnel_map = {step.name: step for step in res.funnel}
    assert funnel_map["Found"].count == 8
    assert funnel_map["Audited"].count == 6  # 6 leads audited
    assert funnel_map["Qualified"].count == 5  # l-1..l-5 have fit_score>=60 and qualified stage
    assert funnel_map["Contacted"].count == 4  # l-1..l-4 contacted+
    assert funnel_map["Replied"].count == 3    # l-1..l-3 replied+
    assert funnel_map["Interested"].count == 2 # l-1, l-2 interested+
    assert funnel_map["Won"].count == 1        # l-1 won

    # Overall conversion rate from top of funnel: 1 won out of 8 leads = 12.5%
    assert funnel_map["Won"].overall_rate == 12.5

    # Check Messaging Metrics
    # Sent: m-1..m-4 (sent, delivered, read, replied) = 4
    assert res.messaging.total_sent == 4
    # Delivered: m-1, m-2, m-3 = 3
    assert res.messaging.total_delivered == 3
    # Read: m-1, m-2 = 2
    assert res.messaging.total_read == 2
    # Replied: m-1, m-in-1 (lead l-1) = 1 distinct lead
    assert res.messaging.total_replied == 1
    assert res.messaging.total_failed == 1
    assert res.messaging.total_opted_out == 1

    # Rates
    assert res.messaging.delivery_rate == 75.0  # 3 / 4 = 75.0%
    assert res.messaging.read_rate == 66.7      # 2 / 3 = 66.7%
    assert res.messaging.reply_rate == 25.0     # 1 / 4 = 25.0%

    # Check Costs
    assert res.costs.total_spend_inr == 16.70
    assert res.costs.total_spend_usd == 0.20
    # Cost per qualified lead: 16.70 / 5 = 3.34
    assert res.costs.cost_per_qualified_lead_inr == 3.34
    # Cost per won deal: 16.70 / 1 = 16.70
    assert res.costs.cost_per_won_deal_inr == 16.70


@pytest.mark.anyio
async def test_campaign_analytics_unowned_raises_value_error(service, mock_db):
    """Verify multi-tenant boundary: requesting unowned campaign raises ValueError."""
    query = MagicMock()
    # eq(user_id).eq(id).execute() returns empty
    query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_db.table.return_value = query

    with pytest.raises(ValueError, match="not found or unowned"):
        await service.get_campaign_analytics(user_id="user-hacker", campaign_id="camp-secret-999")


@pytest.mark.anyio
async def test_campaign_analytics_owned_success(service, mock_db):
    """Verify campaign-specific analytics returns properly formatted CampaignAnalyticsResponse."""
    camp_id = "camp-valid-100"

    def table_router(table_name):
        query = MagicMock()
        if table_name == "campaigns":
            query.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": camp_id, "name": "Dental Outreach Pune"}]
            )
        elif table_name == "leads":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"id": "l-1", "campaign_id": camp_id, "pipeline_stage": "won", "fit_score": 90, "is_suppressed": False}]
            )
        elif table_name == "website_audits":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"lead_id": "l-1", "status": "completed"}]
            )
        elif table_name == "whatsapp_messages":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"id": "m-1", "lead_id": "l-1", "campaign_id": camp_id, "direction": "outbound", "status": "sent"}]
            )
        elif table_name == "api_costs":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"service": "whatsapp", "api_calls": 1, "cost_usd": 0.0, "cost_inr": 0.0}]
            )
        return query

    mock_db.table.side_effect = table_router

    res = await service.get_campaign_analytics(user_id="user-owner", campaign_id=camp_id)

    assert isinstance(res, CampaignAnalyticsResponse)
    assert res.campaign_id == camp_id
    assert res.campaign_name == "Dental Outreach Pune"
    assert res.kpis.total_deals_won == 1
    assert res.has_sent_messages is True


@pytest.mark.anyio
async def test_cost_breakdown_aggregations(service, mock_db):
    """Verify GET /api/analytics/costs calculation shape."""
    mock_campaigns = [{"id": "camp-1", "name": "Pune Tech"}]
    mock_leads = [
        {"id": "l-1", "campaign_id": "camp-1", "pipeline_stage": "qualified", "fit_score": 80, "is_suppressed": False},
        {"id": "l-2", "campaign_id": "camp-1", "pipeline_stage": "discovered", "fit_score": 40, "is_suppressed": False},
    ]
    mock_costs = [
        {"service": "google_places", "api_calls": 10, "cost_usd": 0.50, "cost_inr": 41.50},
        {"service": "ai_analysis", "api_calls": 2, "cost_usd": 0.20, "cost_inr": 16.60},
    ]

    def table_router(table_name):
        query = MagicMock()
        if table_name == "campaigns":
            query.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
        elif table_name == "leads":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_leads)
        elif table_name == "api_costs":
            query.select.return_value.in_.return_value.execute.return_value = MagicMock(data=mock_costs)
        return query

    mock_db.table.side_effect = table_router

    res = await service.get_cost_breakdown(user_id="user-1")

    assert isinstance(res, CostsOverviewResponse)
    assert res.total_businesses_processed == 2
    assert res.total_spend_usd == 0.70
    assert res.total_spend_inr == 58.10
    # 1 qualified lead: 58.10 / 1 = 58.10
    assert res.cost_per_qualified_lead_inr == 58.10
    # 0 won deals: None
    assert res.cost_per_won_deal_inr is None


@pytest.mark.anyio
async def test_date_range_filtering_passes_to_db(service, mock_db):
    """Verify from_date and to_date filters apply correctly to queries."""
    from_date = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    to_date = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)

    mock_campaigns = [{"id": "camp-1", "name": "Pune Tech"}]
    leads_query = MagicMock()
    leads_query.select.return_value.in_.return_value.gte.return_value.lte.return_value.execute.return_value = MagicMock(data=[])

    def table_router(table_name):
        if table_name == "campaigns":
            q = MagicMock()
            q.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_campaigns)
            return q
        elif table_name == "leads":
            return leads_query
        else:
            q = MagicMock()
            q.select.return_value.in_.return_value.gte.return_value.lte.return_value.execute.return_value = MagicMock(data=[])
            return q

    mock_db.table.side_effect = table_router

    await service.get_overview_analytics(user_id="user-1", from_date=from_date, to_date=to_date)

    # Verify gte and lte were invoked with ISO strings
    leads_query.select.return_value.in_.return_value.gte.assert_called_with("created_at", from_date.isoformat())
    leads_query.select.return_value.in_.return_value.gte.return_value.lte.assert_called_with("created_at", to_date.isoformat())


@pytest.mark.anyio
async def test_invalid_user_id_raises_value_error(service):
    """Verify empty or non-string user_id raises ValueError."""
    with pytest.raises(ValueError, match="valid user_id is required"):
        await service.get_overview_analytics(user_id="")

    with pytest.raises(ValueError, match="valid user_id is required"):
        await service.get_campaign_analytics(user_id="   ", campaign_id="camp-1")

    with pytest.raises(ValueError, match="valid user_id is required"):
        await service.get_cost_breakdown(user_id="")


@pytest.mark.anyio
async def test_invalid_date_range_raises_value_error(service):
    """Verify from_date > to_date raises ValueError."""
    from_date = datetime(2026, 11, 10, tzinfo=timezone.utc)
    to_date = datetime(2026, 11, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="from_date cannot be later than to_date"):
        await service.get_overview_analytics(user_id="user-1", from_date=from_date, to_date=to_date)


@pytest.mark.anyio
async def test_invalid_campaign_id_raises_value_error(service):
    """Verify empty campaign_id raises ValueError."""
    with pytest.raises(ValueError, match="valid campaign_id is required"):
        await service.get_campaign_analytics(user_id="user-1", campaign_id="  ")


@pytest.mark.anyio
async def test_database_error_raises_runtime_error(service, mock_db):
    """Verify unexpected database exceptions raise RuntimeError with logging."""
    query = MagicMock()
    query.select.return_value.eq.return_value.execute.side_effect = Exception("Supabase connection timeout")
    mock_db.table.return_value = query

    with pytest.raises(RuntimeError, match="Database error fetching campaigns"):
        await service.get_overview_analytics(user_id="user-1")


@pytest.mark.anyio
async def test_costs_overview_with_single_campaign_and_alias(service, mock_db):
    """Verify cost breakdown for single campaign and cost_per_acquired_lead_inr alias."""
    camp_id = "camp-single-1"

    def table_router(table_name):
        q = MagicMock()
        if table_name == "campaigns":
            q.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": camp_id, "name": "Dental Camp"}]
            )
        elif table_name == "leads":
            q.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"id": "l-1", "campaign_id": camp_id, "pipeline_stage": "won", "fit_score": 95, "is_suppressed": False}]
            )
        elif table_name == "api_costs":
            q.select.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{"service": "ai_message_gen", "api_calls": 2, "cost_usd": 0.04, "cost_inr": 3.50}]
            )
        return q

    mock_db.table.side_effect = table_router

    res = await service.get_cost_breakdown(user_id="user-1", campaign_id=camp_id)

    assert isinstance(res, CostsOverviewResponse)
    assert res.total_businesses_processed == 1
    assert res.total_spend_inr == 3.50
    assert res.cost_per_won_deal_inr == 3.50
    # Check alias matching docs/api-reference.md
    assert res.cost_per_acquired_lead_inr == 3.50

