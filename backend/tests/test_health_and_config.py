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


def test_database_connection_check():
    """Verify database connection checker runs without unhandled exception."""
    from backend.database import check_database_connection

    result = check_database_connection()
    assert isinstance(result, bool)


def test_exception_handler_sanitizes_500():
    """Verify unhandled exceptions return sanitized JSON error without stack traces."""
    from fastapi import APIRouter

    dummy_router = APIRouter()

    @dummy_router.get("/test-error")
    def trigger_error():
        raise RuntimeError("Secret DB connection string leaked!")

    app.include_router(dummy_router)

    safe_client = TestClient(app, raise_server_exceptions=False)
    response = safe_client.get("/test-error")
    assert response.status_code == 500
    data = response.json()
    assert data["error_code"] == "INTERNAL_SERVER_ERROR"
    assert "Secret DB connection string" not in data["detail"]
    assert data["detail"] == "An internal server error occurred"



def test_settings_validation_rejects_bad_input():
    """Verify Settings rejects invalid values."""
    from backend.config import Settings
    from pydantic import ValidationError

    # Bad URL
    with pytest.raises(ValidationError):
        Settings(SUPABASE_URL="ftp://invalid.com", SUPABASE_SERVICE_KEY="key")

    # Bad send limit
    with pytest.raises(ValidationError):
        Settings(
            SUPABASE_URL="https://example.com",
            SUPABASE_SERVICE_KEY="key",
            DAILY_SEND_LIMIT=0,
        )

    # Bad AI provider
    with pytest.raises(ValidationError):
        Settings(
            SUPABASE_URL="https://example.com",
            SUPABASE_SERVICE_KEY="key",
            AI_PROVIDER="unknown_ai",
        )

