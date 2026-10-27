import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import supabase, get_supabase_client
from backend.main import app

client = TestClient(app)


def test_settings_loaded():
    """Verify settings loaded properly from backend/.env."""
    assert settings.SUPABASE_URL.startswith("https://")
    assert len(settings.SUPABASE_SERVICE_KEY) > 20
    assert settings.PORT == 8000
    assert settings.DAILY_SEND_LIMIT == 50
    assert settings.ENVIRONMENT in ["development", "production", "test"]


def test_supabase_client_initialized():
    """Verify Supabase client initialized with configured credentials."""
    assert supabase is not None
    assert get_supabase_client() is supabase
    assert str(supabase.supabase_url).rstrip("/") == settings.SUPABASE_URL.rstrip("/")


def test_health_endpoint():
    """Verify GET /health returns HTTP 200 with expected status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == settings.ENVIRONMENT


def test_cors_preflight_headers():
    """Verify CORS middleware responds with correct headers for allowed origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
