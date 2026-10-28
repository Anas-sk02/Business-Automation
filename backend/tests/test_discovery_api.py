"""Tests for Discovery Control and Status Endpoints (Stage 2, Task 3).

Verifies:
1. POST /api/campaigns/{id}/start-discovery (202 Accepted, background job)
2. GET /api/campaigns/{id}/status (200 OK, live metrics and budget status)
3. Authentication and tenant isolation (unowned campaign returns 404)
4. Concurrency limits (1 discovery per user at a time)
5. Validation against already discovering or completed campaigns
6. Background job orchestration, incremental progress, budget stop, and error recovery
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_campaign
from backend.services.discovery import (
    DiscoveryService,
    get_user_semaphore,
    reset_user_semaphores,
)

client = TestClient(app)

MOCK_USER_1 = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "user1@signalforge.ai",
}
MOCK_USER_2 = {
    "id": "22222222-2222-2222-2222-222222222222",
    "email": "user2@signalforge.ai",
}

SAMPLE_CAMPAIGN_ID = "33333333-3333-3333-3333-333333333333"

BASE_CAMPAIGN_ROW = {
    "id": SAMPLE_CAMPAIGN_ID,
    "user_id": MOCK_USER_1["id"],
    "name": "Nagpur Coaching Campaign",
    "industry": "coaching_institutes",
    "industry_label": "Coaching Institutes",
    "location": "Nagpur, Maharashtra",
    "keywords": ["IIT coaching", "NEET tuition"],
    "target_leads": 30,
    "min_rating": 3.5,
    "service_offered": "Website Development",
    "signals": ["no_website"],
    "whatsapp_settings": {
        "auto_send_after_approval": False,
        "followup_gap_days": 3,
        "max_followups": 3,
    },
    "max_budget": 500.0,
    "spent_amount": 0.0,
    "status": "draft",
    "discovery_queries_total": 0,
    "discovery_queries_completed": 0,
    "total_leads_found": 0,
    "started_at": None,
    "completed_at": None,
}


@pytest.fixture(autouse=True)
def clean_overrides():
    """Clean app dependency overrides and user semaphores before and after each test."""
    reset_user_semaphores()
    app.dependency_overrides.clear()
    yield
    reset_user_semaphores()
    app.dependency_overrides.clear()


# =========================================================================
# 1. Authentication and Authorization Tests
# =========================================================================

def test_discovery_endpoints_require_auth():
    """Verify endpoints reject unauthenticated requests with 401."""
    assert client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery").status_code == 401
    assert client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/status").status_code == 401


def test_discovery_unowned_campaign_returns_404():
    """Per docs/decisions.md Section 3: Unowned campaign must return 404, never 403."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_2

    with patch("backend.dependencies.supabase") as mock_sb:
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_query

        # User 2 tries to access User 1's campaign
        resp_start = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
        assert resp_start.status_code == 404
        assert resp_start.json()["detail"] == f"Campaign with ID '{SAMPLE_CAMPAIGN_ID}' not found"

        resp_status = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/status")
        assert resp_status.status_code == 404
        assert resp_status.json()["detail"] == f"Campaign with ID '{SAMPLE_CAMPAIGN_ID}' not found"


# =========================================================================
# 2. Trigger Discovery Endpoint Tests (POST /start-discovery)
# =========================================================================

def test_start_discovery_success_202():
    """Verify start discovery initiates background job and returns 202 Accepted."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: dict(BASE_CAMPAIGN_ROW)

    with patch("backend.routers.campaigns.supabase") as mock_sb, \
         patch("backend.services.discovery.DiscoveryService.run_discovery_job") as mock_run:

        # 1. Check for active discovery jobs (returns empty)
        active_query = MagicMock()
        active_query.select.return_value = active_query
        active_query.eq.return_value = active_query
        active_query.execute.return_value = MagicMock(data=[])

        # 2. Update campaign to discovering
        update_query = MagicMock()
        update_query.update.return_value = update_query
        update_query.eq.return_value = update_query
        update_query.execute.return_value = MagicMock(data=[dict(BASE_CAMPAIGN_ROW, status="discovering")])

        mock_sb.table.side_effect = [active_query, update_query]

        resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
        assert resp.status_code == 202
        body = resp.json()

        assert body["message"] == "Discovery task accepted and running in background"
        assert body["data"]["campaign_id"] == SAMPLE_CAMPAIGN_ID
        assert body["data"]["status"] == "discovering"
        assert body["data"]["queries_total"] >= 4
        assert body["data"]["target_leads"] == 30
        assert body["data"]["estimated_duration_seconds"] > 0


def test_start_discovery_rejects_already_discovering():
    """Verify start discovery returns 400 if campaign is already in discovering status."""
    discovering_camp = dict(BASE_CAMPAIGN_ROW, status="discovering")
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: discovering_camp

    resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
    assert resp.status_code == 400
    assert "Cannot start discovery while campaign is in 'discovering' state" in resp.json()["detail"]


def test_start_discovery_rejects_completed_campaign():
    """Verify start discovery returns 400 if campaign is completed."""
    completed_camp = dict(BASE_CAMPAIGN_ROW, status="completed")
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: completed_camp

    resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
    assert resp.status_code == 400
    assert "completed campaign" in resp.json()["detail"]


def test_start_discovery_enforces_user_concurrency():
    """Verify only 1 discovery job is allowed concurrently per user (docs/decisions.md Section 9)."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: dict(BASE_CAMPAIGN_ROW)

    with patch("backend.routers.campaigns.supabase") as mock_sb:
        active_query = MagicMock()
        active_query.select.return_value = active_query
        active_query.eq.return_value = active_query
        # User already has another active discovering campaign
        active_query.execute.return_value = MagicMock(data=[{"id": "other-campaign-id"}])
        mock_sb.table.return_value = active_query

        resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
        assert resp.status_code == 400
        assert "Only 1 concurrent discovery" in resp.json()["detail"]


# =========================================================================
# 3. Discovery Status Endpoint Tests (GET /status)
# =========================================================================

def test_get_discovery_status_progress():
    """Verify status endpoint returns progress metrics and budget alert flag."""
    camp_state = dict(
        BASE_CAMPAIGN_ROW,
        status="discovering",
        discovery_queries_total=6,
        discovery_queries_completed=3,
        total_leads_found=18,
        spent_amount=450.0,
        max_budget=500.0,
        started_at="2026-10-28T10:00:00Z",
    )
    app.dependency_overrides[get_owned_campaign] = lambda: camp_state

    resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Discovery status retrieved successfully"
    data = body["data"]

    assert data["campaign_id"] == SAMPLE_CAMPAIGN_ID
    assert data["status"] == "discovering"
    assert data["discovery_queries_total"] == 6
    assert data["discovery_queries_completed"] == 3
    assert data["total_leads_found"] == 18
    assert data["target_leads"] == 30
    assert data["spent_amount"] == 450.0
    assert data["max_budget"] == 500.0
    # 450 >= (500 * 0.8 = 400), so is_near_budget must be True
    assert data["is_near_budget"] is True
    assert data["started_at"] == "2026-10-28T10:00:00Z"


def test_get_discovery_status_not_near_budget():
    """Verify is_near_budget is False when spent < 80% of max_budget."""
    camp_state = dict(
        BASE_CAMPAIGN_ROW,
        spent_amount=50.0,
        max_budget=500.0,
    )
    app.dependency_overrides[get_owned_campaign] = lambda: camp_state

    resp = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_near_budget"] is False


# =========================================================================
# 4. Background Job Orchestration Tests (run_discovery_job)
# =========================================================================

@pytest.mark.anyio
async def test_run_discovery_job_full_flow():
    """Verify discovery background runner iterates queries, logs costs, ingests leads and marks complete."""
    mock_db = MagicMock()
    service = DiscoveryService(db_client=mock_db)

    # 1. Fetch campaign mock
    camp_fetch = MagicMock()
    camp_fetch.select.return_value = camp_fetch
    camp_fetch.eq.return_value = camp_fetch
    camp_fetch.execute.return_value = MagicMock(data=[dict(BASE_CAMPAIGN_ROW)])

    # 2. Budget check queries
    budget_check = MagicMock()
    budget_check.select.return_value = budget_check
    budget_check.eq.return_value = budget_check
    budget_check.execute.return_value = MagicMock(data=[{"spent_amount": 0.0, "max_budget": 500.0}])

    # 3. Campaign update mock
    camp_update = MagicMock()
    camp_update.update.return_value = camp_update
    camp_update.eq.return_value = camp_update
    camp_update.execute.return_value = MagicMock(data=[{"id": SAMPLE_CAMPAIGN_ID}])

    # Wire side effects for table calls
    mock_db.table.side_effect = lambda t: {
        "campaigns": camp_fetch,
        "api_costs": camp_update,
        "leads": camp_update,
    }.get(t, camp_fetch)

    # Mock search_places and ingest_leads
    mock_places = [
        {"id": "p1", "displayName": {"text": "Apex Institute"}, "internationalPhoneNumber": "+91 712 254 1111"},
        {"id": "p2", "displayName": {"text": "Allen Classes"}, "internationalPhoneNumber": "+91 712 254 2222"},
    ]

    with patch.object(service, "search_places", new_callable=AsyncMock) as mock_search, \
         patch.object(service, "ingest_leads") as mock_ingest, \
         patch.object(service, "log_api_cost") as mock_cost:

        mock_search.return_value = (mock_places, None)
        mock_ingest.return_value = {"inserted_count": 2}

        queries = ["coaching in nagpur", "classes in nagpur"]
        result = await service.run_discovery_job(
            campaign_id=SAMPLE_CAMPAIGN_ID,
            user_id=MOCK_USER_1["id"],
            queries=queries,
        )

        assert result["status"] == "discovery_complete"
        assert result["queries_completed"] == 2
        assert result["total_leads_found"] == 4  # 2 per query * 2 queries
        assert mock_search.call_count == 2
        assert mock_ingest.call_count == 2
        assert mock_cost.call_count == 2


@pytest.mark.anyio
async def test_run_discovery_job_halts_on_budget_exceeded():
    """Verify discovery halts when campaign spent_amount exceeds max_budget."""
    mock_db = MagicMock()
    service = DiscoveryService(db_client=mock_db)

    # Initial campaign with 0 spent
    camp_fetch = MagicMock()
    camp_fetch.select.return_value = camp_fetch
    camp_fetch.eq.return_value = camp_fetch
    camp_fetch.execute.return_value = MagicMock(data=[dict(BASE_CAMPAIGN_ROW, max_budget=3.0, spent_amount=0.0)])

    # Budget check returns spent_amount = 3.0 (budget reached limit)
    budget_check = MagicMock()
    budget_check.select.return_value = budget_check
    budget_check.eq.return_value = budget_check
    budget_check.execute.return_value = MagicMock(data=[{"spent_amount": 3.0, "max_budget": 3.0}])

    mock_db.table.side_effect = lambda t: {
        "campaigns": camp_fetch,
        "api_costs": camp_fetch,
    }.get(t, camp_fetch)

    # Make check_budget return False
    with patch.object(service, "check_budget", return_value=False), \
         patch.object(service, "search_places", new_callable=AsyncMock) as mock_search:

        queries = ["query 1", "query 2"]
        result = await service.run_discovery_job(
            campaign_id=SAMPLE_CAMPAIGN_ID,
            user_id=MOCK_USER_1["id"],
            queries=queries,
        )

        assert result["status"] == "discovery_complete"
        assert result["halt_reason"] == "budget_exceeded"
        # Search should not have been called because budget was checked before search
        assert mock_search.call_count == 0


@pytest.mark.anyio
async def test_run_discovery_job_halts_on_target_leads_reached():
    """Verify discovery halts when total_leads_found reaches target_leads."""
    mock_db = MagicMock()
    service = DiscoveryService(db_client=mock_db)

    # Campaign targeting 5 leads
    camp_fetch = MagicMock()
    camp_fetch.select.return_value = camp_fetch
    camp_fetch.eq.return_value = camp_fetch
    camp_fetch.execute.return_value = MagicMock(data=[dict(BASE_CAMPAIGN_ROW, target_leads=5, total_leads_found=0)])

    mock_db.table.side_effect = lambda t: camp_fetch

    with patch.object(service, "search_places", new_callable=AsyncMock) as mock_search, \
         patch.object(service, "ingest_leads") as mock_ingest, \
         patch.object(service, "log_api_cost"):

        mock_search.return_value = ([{"id": "p1"}], None)
        # First query inserts 5 leads directly reaching target
        mock_ingest.return_value = {"inserted_count": 5}

        queries = ["query 1", "query 2", "query 3"]
        result = await service.run_discovery_job(
            campaign_id=SAMPLE_CAMPAIGN_ID,
            user_id=MOCK_USER_1["id"],
            queries=queries,
        )

        assert result["status"] == "discovery_complete"
        assert result["queries_completed"] == 1
        assert result["total_leads_found"] == 5
        assert mock_search.call_count == 1  # Halts after 1st query


@pytest.mark.anyio
async def test_run_discovery_job_error_recovery():
    """Verify unhandled error in discovery recovers campaign status to draft so it does not remain stuck."""
    mock_db = MagicMock()
    service = DiscoveryService(db_client=mock_db)

    camp_fetch = MagicMock()
    camp_fetch.select.return_value = camp_fetch
    camp_fetch.eq.return_value = camp_fetch
    camp_fetch.execute.return_value = MagicMock(data=[dict(BASE_CAMPAIGN_ROW)])

    update_tracker = []
    def track_update(payload):
        update_tracker.append(payload)
        return camp_fetch

    camp_fetch.update.side_effect = track_update
    mock_db.table.side_effect = lambda t: camp_fetch

    with patch.object(service, "log_api_cost", side_effect=RuntimeError("Database connection lost")):
        with pytest.raises(RuntimeError):
            await service.run_discovery_job(
                campaign_id=SAMPLE_CAMPAIGN_ID,
                user_id=MOCK_USER_1["id"],
                queries=["query 1"],
            )

        # Status should have been set to 'discovering' initially, then safely recovered to 'draft'
        statuses = [u.get("status") for u in update_tracker if "status" in u]
        assert "discovering" in statuses
        assert statuses[-1] == "draft"


@pytest.mark.anyio
async def test_user_semaphore_concurrency_isolation():
    """Verify user semaphores are isolated per user (1 concurrent discovery per user)."""
    sem1 = await get_user_semaphore(MOCK_USER_1["id"])
    sem2 = await get_user_semaphore(MOCK_USER_2["id"])
    sem1_again = await get_user_semaphore(MOCK_USER_1["id"])

    assert sem1 is sem1_again
    assert sem1 is not sem2

    # Acquiring sem1 does not block sem2
    async with sem1:
        assert sem1.locked() is True
        assert sem2.locked() is False


def test_start_discovery_rejects_auditing_campaign():
    """Verify start discovery returns 400 if campaign is currently auditing."""
    auditing_camp = dict(BASE_CAMPAIGN_ROW, status="auditing")
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: auditing_camp

    resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
    assert resp.status_code == 400
    assert "Cannot start discovery while campaign is in 'auditing' state" in resp.json()["detail"]


@pytest.mark.anyio
async def test_start_discovery_rejects_when_user_semaphore_locked():
    """Verify start discovery returns 400 immediately if user discovery semaphore is already locked."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: dict(BASE_CAMPAIGN_ROW)

    user_sem = await get_user_semaphore(MOCK_USER_1["id"])
    async with user_sem:
        resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
        assert resp.status_code == 400
        assert "Only 1 concurrent discovery" in resp.json()["detail"]


def test_start_discovery_resets_completed_at():
    """Verify starting discovery clears any previous completed_at timestamp in database."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: dict(BASE_CAMPAIGN_ROW, completed_at="2026-10-27T10:00:00Z")

    with patch("backend.routers.campaigns.supabase") as mock_sb, \
         patch("backend.services.discovery.DiscoveryService.run_discovery_job"):

        active_query = MagicMock()
        active_query.select.return_value = active_query
        active_query.eq.return_value = active_query
        active_query.execute.return_value = MagicMock(data=[])

        update_capture = []
        update_query = MagicMock()
        def capture_update(payload):
            update_capture.append(payload)
            return update_query
        update_query.update.side_effect = capture_update
        update_query.eq.return_value = update_query
        update_query.execute.return_value = MagicMock(data=[{"id": SAMPLE_CAMPAIGN_ID}])

        mock_sb.table.side_effect = [active_query, update_query]

        resp = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/start-discovery")
        assert resp.status_code == 202
        assert len(update_capture) == 1
        assert update_capture[0]["completed_at"] is None
        assert update_capture[0]["status"] == "discovering"


@pytest.mark.anyio
async def test_search_places_retries_on_rate_limit():
    """Verify search_places retries with backoff on HTTP 429 response."""
    import httpx
    from backend.config import settings
    service = DiscoveryService()

    call_count = 0
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(status_code=429, json={"error": "Rate limit exceeded"})
        return httpx.Response(status_code=200, json={"places": [{"id": "p_ok"}]})

    orig_key = settings.GOOGLE_PLACES_API_KEY
    settings.GOOGLE_PLACES_API_KEY = "mock-key"
    try:
        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as mock_client:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                places, _ = await service.search_places("test query", client=mock_client)
                assert len(places) == 1
                assert call_count == 2
                assert mock_sleep.call_count == 1
    finally:
        settings.GOOGLE_PLACES_API_KEY = orig_key


@pytest.mark.anyio
async def test_recover_stale_discovery_jobs():
    """Verify recover_stale_discovery_jobs resets campaigns older than 15 minutes to 'draft'."""
    from backend.main import recover_stale_discovery_jobs

    mock_db = MagicMock()
    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.lt.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=[{"id": "camp-stale-1"}, {"id": "camp-stale-2"}])

    update_chain = MagicMock()
    update_chain.update.return_value = update_chain
    update_chain.in_.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    mock_db.table.side_effect = [select_chain, update_chain]

    with patch("backend.main.get_supabase_client", return_value=mock_db):
        recovered = await recover_stale_discovery_jobs()
        assert recovered == 2
        update_chain.update.assert_called_once_with({"status": "draft"})

