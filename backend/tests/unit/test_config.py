from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment
from tests.conftest import SettingsFactory


def test_defaults_are_safe(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    assert settings.app_name == "Skill Buddy"
    assert settings.debug is False
    assert settings.db_echo is False


def test_cors_origins_parse_from_comma_separated_env(
    make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://localhost:3000/, https://app.example.com ,")

    settings = make_settings()

    assert settings.cors_allow_origins == ["http://localhost:3000", "https://app.example.com"]


def test_secret_key_must_be_long(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="secret_key"):
        make_settings(secret_key="too-short")


def test_secret_key_is_not_rendered(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    assert settings.secret_key.get_secret_value() not in repr(settings)


def test_database_url_requires_psycopg_driver(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        make_settings(database_url="postgresql://app:app@db:5432/app")


def test_missing_required_setting_fails_fast(
    make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError, match="database_url"):
        make_settings()


@pytest.mark.parametrize(
    "overrides",
    [
        {"debug": True},
        {"cors_allow_origins": ["*"]},
        {"db_echo": True},
    ],
)
def test_production_rejects_unsafe_options(
    make_settings: SettingsFactory, overrides: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="production"):
        make_settings(environment=Environment.PRODUCTION, **overrides)


def test_production_accepts_safe_options(make_settings: SettingsFactory) -> None:
    settings = make_settings(
        environment=Environment.PRODUCTION,
        cors_allow_origins=["https://app.example.com"],
        email_backend="smtp",
        embedding_backend="fastembed",
    )

    assert settings.is_production


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_deployed_environments_require_secure_session_cookie(
    make_settings: SettingsFactory, environment: Environment
) -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        make_settings(environment=environment, session_cookie_secure=False)


def test_local_environment_may_disable_secure_cookie(make_settings: SettingsFactory) -> None:
    assert make_settings(session_cookie_secure=False).session_cookie_secure is False


def test_session_max_age_cannot_be_shorter_than_idle_timeout(
    make_settings: SettingsFactory,
) -> None:
    with pytest.raises(ValidationError, match="SESSION_MAX_DAYS"):
        make_settings(session_idle_days=30, session_max_days=7)


def test_auth_defaults_match_the_policy(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    assert settings.session_cookie_secure is True
    assert (settings.session_idle_days, settings.session_max_days) == (30, 90)
    assert (settings.otp_ttl_minutes, settings.otp_max_attempts) == (10, 5)
    assert settings.account_deletion_grace_days == 30


def test_job_table_retention_defaults_match_adr_0008(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    assert settings.job_succeeded_retention_days == 7
    assert settings.job_dead_retention_days == 30
    assert settings.email_log_retention_days == 30


def test_email_log_must_cover_the_24_hour_cap_window(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="email_log_retention_days"):
        make_settings(email_log_retention_days=1)


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_deployed_environments_must_send_real_email(
    make_settings: SettingsFactory, environment: Environment
) -> None:
    with pytest.raises(ValidationError, match="EMAIL_BACKEND"):
        make_settings(environment=environment, email_backend="console")


def test_storage_warning_must_come_before_the_pause(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="STORAGE_WARN_PERCENT"):
        make_settings(storage_warn_percent=90, storage_pause_percent=80)


def test_empty_environment_values_count_as_unset(
    make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADMIN_API_TOKEN", "")

    assert make_settings().admin_api_token is None


def test_short_admin_token_is_rejected(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="admin_api_token"):
        make_settings(admin_api_token="too-short")
