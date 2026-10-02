"""Application settings, loaded from the environment and validated at startup.

Every variable is documented in ``backend/.env.example``. Settings are read once per
process via :func:`get_settings`; a missing or invalid value fails fast with a clear
pydantic validation error instead of surfacing later as a runtime bug.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.models.profile_embedding import EMBEDDING_DIMENSIONS

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

    # --- Background jobs and email log retention (ADR 0008) ---------------------
    # The hourly purge deletes finished jobs and email_log rows older than these.
    job_succeeded_retention_days: int = Field(default=7, ge=1, le=90)
    job_dead_retention_days: int = Field(default=30, ge=1, le=365)
    # At least 2 days: the email cap counts sends over the trailing 24 hours.
    email_log_retention_days: int = Field(default=30, ge=2, le=365)

    # --- Background job runner (ADR 0008) ----------------------------------------
    # How long a claimed job is reserved; a job whose process died runs again after this.
    jobs_lease_seconds: int = Field(default=300, ge=30, le=3600)
    # Retry delay: base * 2^(attempt - 1), capped at the maximum.
    jobs_retry_base_seconds: int = Field(default=10, ge=1, le=3600)
    jobs_retry_max_seconds: int = Field(default=3600, ge=1, le=86_400)
    # 0: never query the database while idle (free hosting; ADR 0008). The runner then wakes
    # only for jobs enqueued in its own process, known due times and ticks. A separate worker
    # process (dev stack, CI) sets a few seconds so it sees jobs other processes enqueue.
    jobs_idle_poll_seconds: float = Field(default=0, ge=0, le=3600)
    jobs_io_concurrency: int = Field(default=2, ge=1, le=20)
    # AI jobs run one at a time to protect the 512 MB host.
    jobs_ai_concurrency: int = Field(default=1, ge=1, le=4)
    jobs_shutdown_grace_seconds: float = Field(default=10, ge=0, le=300)
    # true (free hosting): the API process runs every job kind. false: the API runs only jobs
    # with a secret (login codes), and a separate worker process runs the rest.
    jobs_run_in_api: bool = False
    # Enables POST /api/v1/admin/jobs/tick when set (send it as X-Jobs-Tick-Token).
    jobs_tick_token: SecretStr | None = Field(default=None, min_length=32)
    # Stand-alone worker only: a file touched every few seconds, for a container healthcheck.
    jobs_heartbeat_file: str | None = None

    # --- Email -----------------------------------------------------------------
    # "console" prints messages to stdout (local development and tests only);
    # "smtp" sends through any SMTP server (Mailpit locally, a free relay on staging).
    # "gmail_api" sends as a Gmail account over HTTPS (staging/production; ADR 0008).
    email_backend: Literal["console", "smtp", "gmail_api"] = "console"
    email_from_address: str = Field(default="no-reply@localhost", pattern=r"^[^@\s]+@[^@\s]+$")
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_security: Literal["none", "starttls", "ssl"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    # Gmail API (EMAIL_BACKEND=gmail_api). Client id/secret of a Google Cloud OAuth client and
    # a refresh token with the gmail.send scope; secrets live only in the hosting dashboard.
    gmail_client_id: str | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_refresh_token: SecretStr | None = None
    gmail_sender: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+$")
    # Rolling 24-hour cap (Gmail allows 500 recipients) and the part kept for login codes.
    email_daily_cap: int = Field(default=450, ge=1, le=2000)
    email_reserve_for_codes: int = Field(default=150, ge=0)

    # --- Storage guard (docs/storage-budget.md) --------------------------------
    database_size_limit_mb: int = Field(default=500, ge=1)
    storage_warn_percent: int = Field(default=70, ge=1, le=100)
    storage_pause_percent: int = Field(default=90, ge=1, le=100)
    # Enables GET /api/v1/admin/storage when set (send it as X-Admin-Token).
    admin_api_token: SecretStr | None = Field(default=None, min_length=32)

    # --- Embeddings (ADR 0007) ---------------------------------------------------
    # fastembed: BAAI/bge-small-en-v1.5 on CPU in this process. fake: deterministic vectors
    # without a model, for tests only (refused in staging and production).
    embedding_backend: Literal["fastembed", "fake"] = "fastembed"
    embedding_model: Literal["BAAI/bge-small-en-v1.5"] = "BAAI/bge-small-en-v1.5"
    # Must equal the migrated column size (384); a different size needs a migration.
    embedding_dimensions: int = 384
    # Where the model files live; the production image bakes them into /opt/models.
    embedding_cache_dir: str | None = None
    embedding_threads: int = Field(default=1, ge=1, le=8)
    # Texts per inference call. Peak memory grows with it while one thread's speed does not
    # (measured 2026-10-02: batch 8 peaked about 80 MB higher than 2), so keep it small.
    embedding_batch_size: int = Field(default=2, ge=1, le=16)

    # --- AI gateway (ADR 0007) ---------------------------------------------------
    # Kill switch: false sends no request to any provider; matching uses templates.
    ai_llm_enabled: bool = True
    # Fallback order. Each provider is used only if its keys are set.
    ai_llm_providers: Annotated[list[Literal["groq", "cloudflare"]], NoDecode] = Field(
        default=["groq", "cloudflare"]
    )
    ai_llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    # Overall LLM calls per UTC day, across providers (counted in PostgreSQL).
    ai_llm_daily_call_cap: int = Field(default=400, ge=0)
    # Per user per UTC day: fresh match selections, and profile/request understanding calls.
    ai_user_daily_match_requests: int = Field(default=3, ge=0)
    ai_user_daily_understand_calls: int = Field(default=5, ge=0)

    # Groq (primary). Key from the Groq console; never in the repo.
    groq_api_key: SecretStr | None = Field(default=None, min_length=20)
    groq_models: Annotated[list[str], NoDecode] = Field(
        default=["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    )
    # Per model per UTC day, kept under Groq's free 200K tokens/day.
    groq_daily_token_budget: int = Field(default=190_000, ge=0)

    # Cloudflare Workers AI (backup). Token needs only the "Workers AI" permission.
    cloudflare_account_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    cloudflare_api_token: SecretStr | None = Field(default=None, min_length=20)
    cloudflare_model: str = "@cf/openai/gpt-oss-20b"
    # Kept under the free 10,000 neurons/day; prices per million tokens for the model above.
    cloudflare_daily_neuron_budget: int = Field(default=9_000, ge=0)
    cloudflare_neurons_per_m_input: float = Field(default=18_182, gt=0)
    cloudflare_neurons_per_m_output: float = Field(default=27_273, gt=0)

    # --- Data stores -----------------------------------------------------------
    database_url: PostgresDsn
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=10.0, gt=0)
    db_echo: bool = False

    # --- Health checks ---------------------------------------------------------
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, which is how it arrives from env files."""
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ai_llm_providers", "groq_models", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        """Accept a comma-separated string, which is how it arrives from env files."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_database_scheme(cls, value: object) -> object:
        """Accept the plain URLs hosts hand out (Neon: ``postgresql://...``)."""
        if isinstance(value, str):
            for plain in ("postgresql://", "postgres://"):
                if value.startswith(plain):
                    return "postgresql+psycopg://" + value[len(plain) :]
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
        if deployed and self.email_backend == "console":
            raise ValueError(
                "EMAIL_BACKEND must be 'gmail_api' or 'smtp' in staging and production"
            )
        if self.email_backend == "gmail_api" and not (
            self.gmail_client_id
            and self.gmail_client_secret
            and self.gmail_refresh_token
            and self.gmail_sender
        ):
            raise ValueError(
                "EMAIL_BACKEND=gmail_api needs GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, "
                "GMAIL_REFRESH_TOKEN and GMAIL_SENDER"
            )
        if self.email_reserve_for_codes >= self.email_daily_cap:
            raise ValueError("EMAIL_RESERVE_FOR_CODES must be below EMAIL_DAILY_CAP")
        if self.session_max_days < self.session_idle_days:
            raise ValueError("SESSION_MAX_DAYS must be at least SESSION_IDLE_DAYS")
        if self.embedding_dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"EMBEDDING_DIMENSIONS must be {EMBEDDING_DIMENSIONS} (the migrated column); "
                "another size needs a migration"
            )
        if deployed and self.embedding_backend == "fake":
            raise ValueError("EMBEDDING_BACKEND=fake is for tests only")
        if self.jobs_retry_base_seconds > self.jobs_retry_max_seconds:
            raise ValueError("JOBS_RETRY_BASE_SECONDS must not exceed JOBS_RETRY_MAX_SECONDS")
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
