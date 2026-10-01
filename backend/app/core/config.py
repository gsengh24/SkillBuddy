"""Application settings, loaded from the environment and validated at startup.

Every variable is documented in ``backend/.env.example``. Settings are read once per
process via :func:`get_settings`; a missing or invalid value fails fast with a clear
pydantic validation error instead of surfacing later as a runtime bug.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        # An empty variable (e.g. `ADMIN_API_TOKEN=` from a Compose default) means "unset".
        env_ignore_empty=True,
    )

    # --- Identity --------------------------------------------------------------
    # The product name lives here and only here on the backend; rename by changing it.
    app_name: str = "Skill Buddy"
    # Set by the image build (git SHA or release tag) so every response is traceable.
    app_version: str = "dev"
    environment: Environment = Environment.LOCAL
    debug: bool = False

    # --- HTTP ------------------------------------------------------------------
    api_docs_enabled: bool = True
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Logging ---------------------------------------------------------------
    log_level: LogLevel = "INFO"
    log_json: bool = True

    # --- Security --------------------------------------------------------------
    secret_key: SecretStr = Field(min_length=32)

    # --- Authentication (ADR 0006) ---------------------------------------------
    session_cookie_name: str = Field(default="session", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    csrf_cookie_name: str = Field(default="csrf_token", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    # Must be true wherever the site is served over HTTPS (refused otherwise in staging/prod).
    session_cookie_secure: bool = True
    session_idle_days: int = Field(default=30, ge=1, le=90)
    session_max_days: int = Field(default=90, ge=1, le=365)
    otp_ttl_minutes: int = Field(default=10, ge=1, le=60)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    rate_limit_window_seconds: int = Field(default=600, ge=10, le=86_400)
    otp_request_limit_per_email: int = Field(default=3, ge=1, le=100)
    otp_request_limit_per_ip: int = Field(default=10, ge=1, le=1000)
    otp_verify_limit_per_email: int = Field(default=10, ge=1, le=100)
    otp_verify_limit_per_ip: int = Field(default=30, ge=1, le=1000)
    account_deletion_grace_days: int = Field(default=30, ge=1, le=90)
    # Recorded on each account when the user accepts the terms.
    terms_version: str = Field(default="2026-10-01-draft", min_length=1, max_length=32)
    # Audit-log retention; the daily purge job deletes older auth_events.
    auth_event_retention_days: int = Field(default=90, ge=7, le=730)

    # --- Email -----------------------------------------------------------------
    # "console" prints messages to stdout (local development and tests only);
    # "smtp" sends through any SMTP server (Mailpit locally, a free relay on staging).
    email_backend: Literal["console", "smtp"] = "console"
    email_from_address: str = Field(default="no-reply@localhost", pattern=r"^[^@\s]+@[^@\s]+$")
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_security: Literal["none", "starttls", "ssl"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    # --- Storage guard (docs/storage-budget.md) --------------------------------
    database_size_limit_mb: int = Field(default=500, ge=1)
    storage_warn_percent: int = Field(default=70, ge=1, le=100)
    storage_pause_percent: int = Field(default=90, ge=1, le=100)
    # Enables GET /api/v1/admin/storage when set (send it as X-Admin-Token).
    admin_api_token: SecretStr | None = Field(default=None, min_length=32)

    # --- Data stores -----------------------------------------------------------
    database_url: PostgresDsn
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=10.0, gt=0)
    db_echo: bool = False

    redis_url: RedisDsn

    # --- Health checks ---------------------------------------------------------
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, which is how it arrives from env files."""
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use the 'postgresql+psycopg://' scheme")
        return value

    @model_validator(mode="after")
    def _guard_production(self) -> Self:
        if self.environment is Environment.PRODUCTION:
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if "*" in self.cors_allow_origins:
                raise ValueError("CORS_ALLOW_ORIGINS must not contain '*' in production")
            if self.db_echo:
                raise ValueError("DB_ECHO must be false in production")
        deployed = self.environment in {Environment.STAGING, Environment.PRODUCTION}
        if deployed and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in staging and production")
        if deployed and self.email_backend != "smtp":
            raise ValueError("EMAIL_BACKEND must be 'smtp' in staging and production")
        if self.session_max_days < self.session_idle_days:
            raise ValueError("SESSION_MAX_DAYS must be at least SESSION_IDLE_DAYS")
        if self.storage_warn_percent >= self.storage_pause_percent:
            raise ValueError("STORAGE_WARN_PERCENT must be below STORAGE_PAUSE_PERCENT")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, validating them on first access."""
    return Settings()
