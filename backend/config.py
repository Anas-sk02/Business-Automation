import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and backend/.env."""

    # Supabase credentials (mandatory)
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Google Places API (New)
    GOOGLE_PLACES_API_KEY: str = ""

    # AI Provider
    AI_PROVIDER: str = "gemini"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-2.5-flash"

    # WhatsApp API (Twilio)
    WHATSAPP_PROVIDER: str = "twilio"
    WHATSAPP_ACCOUNT_SID: str = ""
    WHATSAPP_AUTH_TOKEN: str = ""
    WHATSAPP_FROM_NUMBER: str = ""

    # Safeguards and operational defaults
    DAILY_SEND_LIMIT: int = 50
    QUIET_HOURS_START: str = "21:00"
    QUIET_HOURS_END: str = "09:00"
    USD_TO_INR_RATE: float = 86.0
    GOOGLE_PLACES_COST_PER_SEARCH_USD: float = 0.035

    # Web & Server
    CORS_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("SUPABASE_URL must begin with http:// or https://")
        return v.rstrip("/")

    @field_validator("DAILY_SEND_LIMIT")
    @classmethod
    def validate_daily_send_limit(cls, v: int) -> int:
        if v < 1 or v > 1000:
            raise ValueError("DAILY_SEND_LIMIT must be between 1 and 1000")
        return v

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        allowed = {"gemini", "claude"}
        if v.lower() not in allowed:
            raise ValueError(f"AI_PROVIDER must be one of {allowed}")
        return v.lower()

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

