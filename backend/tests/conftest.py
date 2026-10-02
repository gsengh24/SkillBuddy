"""Shared fixtures.

Unit tests (``tests/unit``) need no infrastructure. Integration tests
(``tests/integration``) run against the real PostgreSQL and Redis given by
``DATABASE_URL`` and ``REDIS_URL``; each run works in its own throwaway database.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# Defaults so the suite runs with no .env; real values from the environment win.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LOG_JSON", "true")
# Tests never download or run the real embedding model (the CI memory check does that).
os.environ.setdefault("EMBEDDING_BACKEND", "fake")

from app.core.config import Settings  # must follow the env defaults
from app.main import create_app

INTEGRATION_DIR = Path(__file__).parent / "integration"

SettingsFactory = Callable[..., Settings]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if INTEGRATION_DIR in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def make_settings() -> SettingsFactory:
    """Build settings from the environment (never a local .env) plus overrides."""

    def factory(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **overrides)

    return factory


@pytest.fixture
def settings(make_settings: SettingsFactory) -> Settings:
    return make_settings()


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """HTTP client for an app whose lifespan (DB and Redis pools) is not started."""
    app = create_app(settings)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
