from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user, get_owned_campaign

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

VALID_CREATE_PAYLOAD = {
    "name": "Nagpur Coaching Institutes",
    "industry": "coaching_institutes",
    "industry_label": "Coaching Institutes",
    "location": "Nagpur, Maharashtra",
    "keywords": ["tuition", "IIT coaching"],
    "target_leads": 50,
    "min_rating": 3.5,
    "service_offered": "Website Development",
    "signals": ["no_website", "mobile_issues"],
    "whatsapp_settings": {
        "auto_send_after_approval": False,
        "followup_gap_days": 3,
        "max_followups": 3,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "09:00",
    },
    "max_budget": 100.0,
}


def test_campaign_endpoints_require_auth():
    """Verify all campaign endpoints reject unauthenticated requests with 401."""
    assert client.post("/api/campaigns", json=VALID_CREATE_PAYLOAD).status_code == 401
    assert client.get("/api/campaigns").status_code == 401
    assert client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}").status_code == 401
    assert client.put(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}", json={"name": "New"}).status_code == 401
    assert client.delete(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}").status_code == 401
    assert client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/pause").status_code == 401
    assert client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/resume").status_code == 401


def test_create_campaign_success():
    """Verify authenticated user can create campaign with correct defaults and ownership."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    mock_db_campaign = {
        "id": SAMPLE_CAMPAIGN_ID,
        "user_id": MOCK_USER_1["id"],
        **VALID_CREATE_PAYLOAD,
        "spent_amount": 0.0,
        "status": "draft",
        "discovery_queries_total": 0,
        "discovery_queries_completed": 0,
        "total_leads_found": 0,
    }

    mock_resp = MagicMock()
    mock_resp.data = [mock_db_campaign]

    with patch("backend.routers.campaigns.supabase.table") as mock_table:
        mock_table.return_value.insert.return_value.execute.return_value = mock_resp
        response = client.post("/api/campaigns", json=VALID_CREATE_PAYLOAD)

    app.dependency_overrides.clear()

    assert response.status_code == 201
    res_json = response.json()
    assert "data" in res_json
    assert res_json["message"] == "Campaign created successfully"
    assert res_json["data"]["name"] == "Nagpur Coaching Institutes"
    assert res_json["data"]["user_id"] == MOCK_USER_1["id"]
    assert res_json["data"]["status"] == "draft"


def test_create_campaign_validation_failure():
    """Verify invalid payloads (target_leads > 500, rating > 5.0) return 422."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    # Target leads exceeds maximum 500
    bad_payload = dict(VALID_CREATE_PAYLOAD, target_leads=600)
    response = client.post("/api/campaigns", json=bad_payload)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"

    # Rating exceeds 5.0
    bad_rating_payload = dict(VALID_CREATE_PAYLOAD, min_rating=6.5)
    response_rating = client.post("/api/campaigns", json=bad_rating_payload)
    assert response_rating.status_code == 422

    app.dependency_overrides.clear()


def test_list_campaigns_user_isolation():
    """Verify list campaigns only returns campaigns belonging to authenticated user."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    mock_campaigns = [
        {
            "id": SAMPLE_CAMPAIGN_ID,
            "user_id": MOCK_USER_1["id"],
            **VALID_CREATE_PAYLOAD,
            "spent_amount": 0.0,
            "status": "draft",
            "discovery_queries_total": 0,
            "discovery_queries_completed": 0,
            "total_leads_found": 0,
        }
    ]

    mock_resp = MagicMock()
    mock_resp.data = mock_campaigns
    mock_resp.count = 1

    with patch("backend.routers.campaigns.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_resp
        response = client.get("/api/campaigns?page=1&page_size=10")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert "data" in res_json
    assert res_json["total"] == 1
    assert res_json["page"] == 1
    assert res_json["page_size"] == 10
    assert len(res_json["data"]) == 1
    assert res_json["data"][0]["user_id"] == MOCK_USER_1["id"]


def test_get_campaign_unowned_returns_404():
    """Verify decisions.md rule: accessing another user's campaign returns 404 (not 403)."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_2

    # Database returns no match when filtering by user_id = MOCK_USER_2
    mock_resp = MagicMock()
    mock_resp.data = []

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        response = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_campaign_success_when_owned():
    """Verify owned campaign returns single item envelope."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    mock_campaign = {
        "id": SAMPLE_CAMPAIGN_ID,
        "user_id": MOCK_USER_1["id"],
        **VALID_CREATE_PAYLOAD,
        "spent_amount": 0.0,
        "status": "draft",
        "discovery_queries_total": 0,
        "discovery_queries_completed": 0,
        "total_leads_found": 0,
    }

    mock_resp = MagicMock()
    mock_resp.data = [mock_campaign]

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        response = client.get(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"]["id"] == SAMPLE_CAMPAIGN_ID
    assert res_json["data"]["user_id"] == MOCK_USER_1["id"]


def test_update_campaign_success():
    """Verify PUT updates allowed fields on owned campaign."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    owned_campaign = {
        "id": SAMPLE_CAMPAIGN_ID,
        "user_id": MOCK_USER_1["id"],
        **VALID_CREATE_PAYLOAD,
        "spent_amount": 0.0,
        "status": "draft",
        "discovery_queries_total": 0,
        "discovery_queries_completed": 0,
        "total_leads_found": 0,
    }
    updated_campaign = dict(owned_campaign, name="Renamed Campaign", target_leads=75)

    mock_get_resp = MagicMock()
    mock_get_resp.data = [owned_campaign]

    mock_update_resp = MagicMock()
    mock_update_resp.data = [updated_campaign]

    with patch("backend.dependencies.supabase.table") as mock_dep_table:
        mock_dep_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_get_resp
        with patch("backend.routers.campaigns.supabase.table") as mock_router_table:
            mock_router_table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_update_resp
            response = client.put(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}", json={"name": "Renamed Campaign", "target_leads": 75})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"]["name"] == "Renamed Campaign"
    assert res_json["data"]["target_leads"] == 75


def test_delete_campaign_success():
    """Verify DELETE removes campaign and returns deletion envelope."""
    owned_campaign = {
        "id": SAMPLE_CAMPAIGN_ID,
        "user_id": MOCK_USER_1["id"],
    }
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1
    app.dependency_overrides[get_owned_campaign] = lambda: owned_campaign

    with patch("backend.routers.campaigns.supabase.table") as mock_router_table:
        mock_router_table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        response = client.delete(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["data"]["id"] == SAMPLE_CAMPAIGN_ID
    assert "deleted successfully" in res_json["message"]


def test_pause_and_resume_campaign():
    """Verify pause and resume endpoints update campaign status."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_1

    base_campaign = {
        "id": SAMPLE_CAMPAIGN_ID,
        "user_id": MOCK_USER_1["id"],
        **VALID_CREATE_PAYLOAD,
        "spent_amount": 0.0,
        "status": "active",
        "discovery_queries_total": 0,
        "discovery_queries_completed": 0,
        "total_leads_found": 0,
    }
    paused_campaign = dict(base_campaign, status="paused")
    resumed_campaign = dict(base_campaign, status="active")

    mock_dep_resp = MagicMock()
    mock_dep_resp.data = [base_campaign]

    # Test Pause
    mock_pause_resp = MagicMock()
    mock_pause_resp.data = [paused_campaign]
    with patch("backend.dependencies.supabase.table") as mock_dep_table:
        mock_dep_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_dep_resp
        with patch("backend.routers.campaigns.supabase.table") as mock_router_table:
            mock_router_table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_pause_resp
            pause_res = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/pause")

    assert pause_res.status_code == 200
    assert pause_res.json()["data"]["status"] == "paused"

    # Test Resume
    mock_resume_resp = MagicMock()
    mock_resume_resp.data = [resumed_campaign]
    with patch("backend.dependencies.supabase.table") as mock_dep_table:
        mock_dep_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_dep_resp
        with patch("backend.routers.campaigns.supabase.table") as mock_router_table:
            mock_router_table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resume_resp
            resume_res = client.post(f"/api/campaigns/{SAMPLE_CAMPAIGN_ID}/resume")

    assert resume_res.status_code == 200
    assert resume_res.json()["data"]["status"] == "active"

    app.dependency_overrides.clear()
