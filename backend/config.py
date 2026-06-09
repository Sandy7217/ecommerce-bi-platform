from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "E-Commerce BI Platform"
    environment: Literal["development", "local", "staging", "production"] = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001", "https://ecommerce-bi-platform.vercel.app"])
    cors_origin_regex: str | None = None
    max_upload_bytes: int = 25 * 1024 * 1024
    allowed_upload_extensions: set[str] = Field(default_factory=lambda: {".csv", ".xls", ".xlsx"})

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_storage_bucket: str = "uploads"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str | None = None

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    whatsapp_to: str | None = None

    resend_api_key: str | None = None
    resend_from_email: str = "E-Commerce BI <reports@example.com>"

    lead_time_days: int = 45

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
