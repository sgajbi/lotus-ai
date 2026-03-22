from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "lotus-ai"
    service_version: str = "0.1.0"
    delivery_phase: str = "foundation"
    provider_mode: str = "disabled"
    retrieval_mode: str = "disabled"
    safety_mode: str = "documented_only"
    audit_store_mode: str = "memory"
    database_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="LOTUS_AI_", extra="ignore")


settings = Settings()
