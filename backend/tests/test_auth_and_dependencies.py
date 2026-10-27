import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.main import app
from backend.dependencies import get_current_user, get_owned_campaign

client = TestClient(app)


def test_auth_me_requires_token():
    """Verify GET /api/auth/me returns 401 when Authorization header is missing."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert "Authorization" in data["detail"] or "token" in data["detail"]


def test_auth_profile_requires_token():
    """Verify PUT /api/auth/profile returns 401 when Authorization header is missing."""
    response = client.put("/api/auth/profile", json={"full_name": "New Name"})
    assert response.status_code == 401


def test_invalid_bearer_token_rejected():
    """Verify malformed or invalid token returns 401."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer totally_fake_token_123"},
    )
    assert response.status_code == 401


def test_get_current_profile_authenticated():
    """Verify GET /api/auth/me returns standard profile envelope for authenticated user."""
    mock_user = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "agent@signalforge.ai",
        "metadata": {"full_name": "SignalForge Agent"},
    }
    mock_profile = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "agent@signalforge.ai",
        "full_name": "SignalForge Agent",
        "company_name": "Agency Inc",
        "whatsapp_number": "+919876543210",
        "service_descriptions": ["Website Development"],
        "pricing_info": {"website": "₹30,000"},
        "timezone": "Asia/Kolkata",
    }

    # Override dependency for isolated router testing
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_resp = MagicMock()
    mock_resp.data = [mock_profile]

    with patch("backend.routers.auth.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        response = client.get("/api/auth/me")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert "data" in res_json
    assert res_json["message"] == "User profile retrieved successfully"
    assert res_json["data"]["email"] == "agent@signalforge.ai"
    assert res_json["data"]["company_name"] == "Agency Inc"


def test_update_profile_authenticated():
    """Verify PUT /api/auth/profile updates profile and returns updated envelope."""
    mock_user = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "agent@signalforge.ai",
        "metadata": {},
    }
    updated_profile = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "agent@signalforge.ai",
        "full_name": "New Agency Name",
        "company_name": "Updated Co",
        "whatsapp_number": "+919999999999",
        "service_descriptions": ["Web", "SEO"],
        "pricing_info": {},
        "timezone": "Asia/Kolkata",
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_resp = MagicMock()
    mock_resp.data = [updated_profile]

    with patch("backend.routers.auth.supabase.table") as mock_table:
        mock_table.return_value.update.return_value.eq.return_value.execute.return_value = mock_resp
        response = client.put(
            "/api/auth/profile",
            json={
                "full_name": "New Agency Name",
                "company_name": "Updated Co",
                "whatsapp_number": "+919999999999",
                "service_descriptions": ["Web", "SEO"],
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["message"] == "Profile updated successfully"
    assert res_json["data"]["full_name"] == "New Agency Name"


def test_update_profile_validation_error():
    """Verify invalid phone numbers trigger 422 validation error."""
    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.com"}
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.put(
        "/api/auth/profile",
        json={"whatsapp_number": "invalid-abc-phone"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_update_profile_invalid_timezone_rejected():
    """Verify invalid timezone strings trigger 422 validation error."""
    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.com"}
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.put(
        "/api/auth/profile",
        json={"timezone": "Invalid/Fake_Zone"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_update_profile_empty_payload_rejected():
    """Verify empty update payload returns 400 Bad Request."""
    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.com"}
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = client.put("/api/auth/profile", json={})
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "No valid fields provided" in response.json()["detail"]


def test_get_owned_campaign_invalid_uuid_returns_404():
    """Verify invalid UUID returns 404 without database query."""
    import asyncio

    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@test.com"}
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_owned_campaign(campaign_id="not-a-valid-uuid", user=mock_user))

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_owned_campaign_returns_404_when_unowned():
    """Verify decisions.md rule: unowned campaign returns 404, NEVER 403."""
    import asyncio

    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@test.com"}
    valid_uuid = "22222222-2222-2222-2222-222222222222"
    mock_resp = MagicMock()
    mock_resp.data = []  # No campaign found for user

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_owned_campaign(campaign_id=valid_uuid, user=mock_user))

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


def test_get_owned_campaign_success_when_owned():
    """Verify owned campaign returns campaign record."""
    import asyncio

    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@test.com"}
    valid_uuid = "22222222-2222-2222-2222-222222222222"
    campaign_record = {"id": valid_uuid, "user_id": mock_user["id"], "name": "Dental Clinics"}

    mock_resp = MagicMock()
    mock_resp.data = [campaign_record]

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        result = asyncio.run(get_owned_campaign(campaign_id=valid_uuid, user=mock_user))

        assert result == campaign_record
        assert result["user_id"] == mock_user["id"]


def test_get_owned_lead_returns_404_when_unowned():
    """Verify decisions.md rule: unowned lead returns 404, NEVER 403."""
    import asyncio
    from backend.dependencies import get_owned_lead

    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@test.com"}
    valid_lead_uuid = "33333333-3333-3333-3333-333333333333"

    mock_resp = MagicMock()
    mock_resp.data = []

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_owned_lead(lead_id=valid_lead_uuid, user=mock_user))

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


def test_get_owned_lead_success_when_owned():
    """Verify owned lead returns lead record."""
    import asyncio
    from backend.dependencies import get_owned_lead

    mock_user = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@test.com"}
    valid_lead_uuid = "33333333-3333-3333-3333-333333333333"
    lead_record = {"id": valid_lead_uuid, "business_name": "Smile Clinic", "campaigns": {"user_id": mock_user["id"]}}

    mock_resp = MagicMock()
    mock_resp.data = [lead_record]

    with patch("backend.dependencies.supabase.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        result = asyncio.run(get_owned_lead(lead_id=valid_lead_uuid, user=mock_user))

        assert result == lead_record


