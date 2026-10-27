from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class UserProfileResponse(BaseModel):
    """User profile response model matching public.profiles schema."""
    id: str
    email: str
    full_name: str = ""
    company_name: Optional[str] = ""
    whatsapp_number: Optional[str] = ""
    service_descriptions: list[str] = Field(default_factory=list)
    pricing_info: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "Asia/Kolkata"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """User profile update request payload."""
    full_name: Optional[str] = Field(default=None, max_length=100)
    company_name: Optional[str] = Field(default=None, max_length=100)
    whatsapp_number: Optional[str] = Field(default=None, max_length=20)
    service_descriptions: Optional[list[str]] = None
    pricing_info: Optional[dict[str, Any]] = None
    timezone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("whatsapp_number")
    @classmethod
    def validate_whatsapp_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().replace(" ", "").replace("-", "")
            if cleaned and not (cleaned.startswith("+") or cleaned.isdigit()):
                raise ValueError("WhatsApp number must contain valid digits or E.164 format (+...)")
            return cleaned
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            import zoneinfo
            try:
                zoneinfo.ZoneInfo(v.strip())
            except Exception:
                raise ValueError(f"Invalid timezone '{v}'. Must be a valid IANA timezone name like 'Asia/Kolkata'.")
            return v.strip()
        return v

