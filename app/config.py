"""Application configuration loaded from environment variables via Pydantic Settings."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic_settings import BaseSettings


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    MOCK = "mock"


class Settings(BaseSettings):
    """All configuration is sourced from env vars (or a .env file)."""

    # ── Twilio ──
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"

    # ── LLM ──
    llm_provider: LLMProviderType = LLMProviderType.MOCK
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Database ──
    database_url: str = "postgresql://settli:settli@localhost:5432/settli"

    # ── App ──
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_env: Literal["development", "production", "testing"] = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton — import this from anywhere
settings = Settings()
