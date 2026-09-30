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
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, validating them on first access."""
    return Settings()
