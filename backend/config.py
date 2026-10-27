import os
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
    AI_MODEL: str = "gemini-2.0-flash"

    # WhatsApp API (Twilio)
    WHATSAPP_PROVIDER: str = "twilio"
    WHATSAPP_ACCOUNT_SID: str = ""
    WHATSAPP_AUTH_TOKEN: str = ""
    WHATSAPP_FROM_NUMBER: str = ""

    # Safeguards and operational defaults
    DAILY_SEND_LIMIT: int = 50
    QUIET_HOURS_START: str = "21:00"
    QUIET_HOURS_END: str = "09:00"

    # Web & Server
    CORS_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
