"""Integration tests for Analytics API Router (Stage 7 Task 2).

Verifies GET /api/analytics/overview, GET /api/analytics/campaign/{id},
and GET /api/analytics/costs endpoints per docs/decisions.md (Sections 4, 11).
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_analytics_service, get_current_user
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

VALID_USER_ID = "00000000-0000-0000-0000-000000000001"
VALID_CAMP_ID = "11111111-1111-1111-1111-111111111111"
UNOWNED_CAMP_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def auth_user():
    return {"id": VALID_USER_ID, "email": "doctor@signalforge.ai"}


@pytest.fixture
def mock_analytics_service():
    return AsyncMock()


@pytest.fixture
def client(auth_user, mock_analytics_service):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_analytics_service] = lambda: mock_analytics_service
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    app.dependency_overrides.clear()
    return TestClient(app)


def test_get_analytics_overview_unauthorized(unauth_client):
    """Verify GET /api/analytics/overview rejects unauthenticated requests with 401."""
    res = unauth_client.get("/api/analytics/overview")
    assert res.status_code == 401


def test_get_analytics_overview_success(client, mock_analytics_service):
    """Verify GET /api/analytics/overview returns 200 with standard envelope."""
    mock_analytics_service.get_overview_analytics.return_value = AnalyticsOverviewResponse(
        has_sent_messages=True,
        kpis=AnalyticsKPIs(
            total_campaigns=2,
            total_leads_found=20,
            total_audited=15,
            total_qualified=10,
            total_messages_sent=8,
            total_deals_won=2,
            total_spend_usd=1.50,
            total_spend_inr=125.00,
        ),
        funnel=[
            FunnelStep(name="Found", count=20, conversion_rate=100.0, overall_rate=100.0),
            FunnelStep(name="Won", count=2, conversion_rate=10.0, overall_rate=10.0),
        ],
        messaging=MessagingMetrics(
            total_sent=8,
            total_delivered=7,
            total_read=5,
            total_replied=3,
            total_failed=1,
            total_opted_out=0,
            delivery_rate=87.5,
            read_rate=71.4,
            reply_rate=37.5,
        ),
        costs=CostBreakdown(
            services=[
                ServiceCostItem(service="google_places", api_calls=10, cost_usd=0.50, cost_inr=41.50),
            ],
            total_spend_usd=1.50,
            total_spend_inr=125.00,
            cost_per_qualified_lead_inr=12.50,
            cost_per_won_deal_inr=62.50,
        ),
    )

    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "Analytics overview retrieved successfully"
    assert data["data"]["has_sent_messages"] is True
    assert data["data"]["kpis"]["total_deals_won"] == 2
    assert data["data"]["messaging"]["reply_rate"] == 37.5


def test_get_analytics_overview_with_date_filters(client, mock_analytics_service):
    """Verify date filters are parsed and forwarded to service."""
    mock_analytics_service.get_overview_analytics.return_value = AnalyticsOverviewResponse(
        has_sent_messages=False,
        kpis=AnalyticsKPIs(),
        funnel=[],
        messaging=MessagingMetrics(),
        costs=CostBreakdown(),
    )

    res = client.get("/api/analytics/overview?from_date=2026-10-01T00:00:00Z&to_date=2026-10-31T23:59:59Z")
    assert res.status_code == 200
    mock_analytics_service.get_overview_analytics.assert_called_once()
    args, kwargs = mock_analytics_service.get_overview_analytics.call_args
    assert kwargs["from_date"] is not None
    assert kwargs["to_date"] is not None


def test_get_analytics_overview_invalid_dates_returns_400(client, mock_analytics_service):
    """Verify service ValueError (e.g. from_date > to_date) translates to 400 Bad Request."""
    mock_analytics_service.get_overview_analytics.side_effect = ValueError("from_date cannot be later than to_date")

    res = client.get("/api/analytics/overview?from_date=2026-11-10T00:00:00Z&to_date=2026-11-01T00:00:00Z")
    assert res.status_code == 400
    assert "from_date cannot be later than to_date" in res.json()["detail"]


def test_get_campaign_analytics_unauthorized(unauth_client):
    """Verify GET /api/analytics/campaign/{id} rejects unauthenticated requests with 401."""
    res = unauth_client.get(f"/api/analytics/campaign/{VALID_CAMP_ID}")
    assert res.status_code == 401


def test_get_campaign_analytics_invalid_uuid_returns_404(client):
    """Verify invalid UUID returns 404 per decisions.md Section 3."""
    res = client.get("/api/analytics/campaign/not-a-valid-uuid")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_campaign_analytics_unowned_returns_404(client, mock_analytics_service):
    """Verify querying an unowned campaign returns 404 (not leaking existence)."""
    mock_analytics_service.get_campaign_analytics.side_effect = ValueError(
        f"Campaign {UNOWNED_CAMP_ID} not found or unowned"
    )

    res = client.get(f"/api/analytics/campaign/{UNOWNED_CAMP_ID}")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_campaign_analytics_success(client, mock_analytics_service):
    """Verify GET /api/analytics/campaign/{id} returns 200 with campaign data."""
    mock_analytics_service.get_campaign_analytics.return_value = CampaignAnalyticsResponse(
        campaign_id=VALID_CAMP_ID,
        campaign_name="Pune Dentist Campaign",
        has_sent_messages=True,
        kpis=AnalyticsKPIs(total_campaigns=1, total_leads_found=10, total_deals_won=1),
        funnel=[],
        messaging=MessagingMetrics(),
        costs=CostBreakdown(),
    )

    res = client.get(f"/api/analytics/campaign/{VALID_CAMP_ID}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["campaign_id"] == VALID_CAMP_ID
    assert data["campaign_name"] == "Pune Dentist Campaign"
    assert data["kpis"]["total_deals_won"] == 1


def test_get_cost_analytics_unauthorized(unauth_client):
    """Verify GET /api/analytics/costs rejects unauthenticated requests with 401."""
    res = unauth_client.get("/api/analytics/costs")
    assert res.status_code == 401


def test_get_cost_analytics_success(client, mock_analytics_service):
    """Verify GET /api/analytics/costs returns 200 with usage breakdown."""
    mock_analytics_service.get_cost_breakdown.return_value = CostsOverviewResponse(
        services=[
            ServiceCostItem(service="google_places", api_calls=12, cost_usd=0.60, cost_inr=50.00),
            ServiceCostItem(service="ai_analysis", api_calls=5, cost_usd=0.10, cost_inr=8.30),
        ],
        total_spend_usd=0.70,
        total_spend_inr=58.30,
        total_businesses_processed=12,
        cost_per_qualified_lead_inr=11.66,
        cost_per_won_deal_inr=58.30,
        cost_per_acquired_lead_inr=58.30,
    )

    res = client.get("/api/analytics/costs")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_businesses_processed"] == 12
    assert data["total_spend_inr"] == 58.30
    assert data["cost_per_acquired_lead_inr"] == 58.30
    assert len(data["services"]) == 2


def test_get_cost_analytics_invalid_campaign_id_returns_404(client):
    """Verify invalid campaign_id in query param returns 404."""
    res = client.get("/api/analytics/costs?campaign_id=not-a-uuid")
    assert res.status_code == 404


def test_get_cost_analytics_unowned_campaign_returns_404(client, mock_analytics_service):
    """Verify unowned campaign_id filter returns 404."""
    mock_analytics_service.get_cost_breakdown.side_effect = ValueError(
        f"Campaign {UNOWNED_CAMP_ID} not found or unowned"
    )

    res = client.get(f"/api/analytics/costs?campaign_id={UNOWNED_CAMP_ID}")
    assert res.status_code == 404


def test_analytics_internal_error_returns_500(client, mock_analytics_service):
    """Verify unexpected database or server exceptions return 500 with generic message."""
    mock_analytics_service.get_overview_analytics.side_effect = RuntimeError("Database timeout connection failed")

    res = client.get("/api/analytics/overview")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to retrieve analytics overview"


def test_get_campaign_analytics_invalid_dates_returns_400(client, mock_analytics_service):
    """Verify campaign analytics with invalid dates returns 400 Bad Request."""
    mock_analytics_service.get_campaign_analytics.side_effect = ValueError("from_date cannot be later than to_date")

    res = client.get(f"/api/analytics/campaign/{VALID_CAMP_ID}?from_date=2026-11-10T00:00:00Z&to_date=2026-11-01T00:00:00Z")
    assert res.status_code == 400
    assert "from_date cannot be later than to_date" in res.json()["detail"]


def test_get_campaign_analytics_internal_error_returns_500(client, mock_analytics_service):
    """Verify unexpected server exception on campaign analytics returns 500."""
    mock_analytics_service.get_campaign_analytics.side_effect = RuntimeError("Database timeout")

    res = client.get(f"/api/analytics/campaign/{VALID_CAMP_ID}")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to retrieve campaign analytics"


def test_get_cost_analytics_invalid_dates_returns_400(client, mock_analytics_service):
    """Verify cost analytics with invalid dates returns 400 Bad Request."""
    mock_analytics_service.get_cost_breakdown.side_effect = ValueError("from_date cannot be later than to_date")

    res = client.get("/api/analytics/costs?from_date=2026-11-10T00:00:00Z&to_date=2026-11-01T00:00:00Z")
    assert res.status_code == 400
    assert "from_date cannot be later than to_date" in res.json()["detail"]


def test_get_cost_analytics_internal_error_returns_500(client, mock_analytics_service):
    """Verify unexpected server exception on cost analytics returns 500."""
    mock_analytics_service.get_cost_breakdown.side_effect = RuntimeError("Database connection lost")

    res = client.get("/api/analytics/costs")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to retrieve cost analytics"


