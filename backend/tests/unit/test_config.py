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
        environment=Environment.PRODUCTION, cors_allow_origins=["https://app.example.com"]
    )

    assert settings.is_production
