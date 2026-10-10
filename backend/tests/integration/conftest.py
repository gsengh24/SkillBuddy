"""Fixtures backed by real PostgreSQL (with pgvector).

``DATABASE_URL`` must point at a server where the user may create databases (the
local Compose and CI ``postgres`` users can). Tests never touch that database itself:
each session, and each migration test, gets a freshly created database that is
dropped afterwards.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_otp_delivery
from app.core.config import Settings
from app.main import create_app
from app.services import app_settings
from tests.conftest import SettingsFactory

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _render(url: str, *, drivername: str | None = None, database: str | None = None) -> str:
    changed = make_url(url).set(drivername=drivername, database=database)
    return changed.render_as_string(hide_password=False)


@contextmanager
def temporary_database() -> Iterator[str]:
    """Create an empty database on the configured server; yield its SQLAlchemy URL."""
    base_url = os.environ["DATABASE_URL"]
    name = f"{make_url(base_url).database}_test_{uuid.uuid4().hex[:12]}"
    admin_dsn = _render(base_url, drivername="postgresql")
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield _render(base_url, database=name)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    config.attributes["skip_logging_config"] = True
    return config


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    """A database migrated to head, shared by the whole test session."""
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def empty_database_url() -> Iterator[str]:
    """A brand-new database with no migrations applied."""
    with temporary_database() as url:
        yield url


@pytest.fixture
def integration_settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url)


@asynccontextmanager
async def live_client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """A client for an app with its lifespan running (real DB pool and job runner)."""
    app: FastAPI = create_app(settings)
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# --- Authentication fixtures --------------------------------------------------------------


class CapturingDelivery:
    """Stands in for email delivery: records the codes that would have been sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_login_code(
        self, db: AsyncSession, otp_id: uuid.UUID, email: str, code: str
    ) -> None:
        self.sent.append((email, code))

    def last_code(self, email: str) -> str:
        return next(code for sent_to, code in reversed(self.sent) if sent_to == email)


@pytest.fixture
def auth_settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url)


@pytest.fixture
def delivery() -> CapturingDelivery:
    return CapturingDelivery()


@asynccontextmanager
async def auth_client(
    settings: Settings,
    delivery: CapturingDelivery | None,
    *,
    client_ip: str = "198.51.100.10",
    base_url: str = "https://testserver",
    routers: Sequence[APIRouter] = (),
) -> AsyncIterator[AsyncClient]:
    """A client for a running app; HTTPS by default so Secure cookies behave as in prod.

    With ``delivery=None`` the real queue-based delivery is used.
    """
    app: FastAPI = create_app(settings)
    for router in routers:
        app.include_router(router)
    if delivery is not None:
        app.dependency_overrides[get_otp_delivery] = lambda: delivery
    async with LifespanManager(app) as manager:
        # Each client starts with fresh rate-limit counters, so tests never see each other's
        # counts (production never clears them early).
        run_sql(
            settings.database_url.unicode_string(),
            "DELETE FROM rate_limit_counters WHERE key LIKE 'rl:%'",
        )
        transport = ASGITransport(app=manager.app, client=(client_ip, 40000))
        async with AsyncClient(transport=transport, base_url=base_url) as client:
            yield client


def run_sql(database_url: str, statement: str, **params: Any) -> list[dict[str, Any]]:
    """Run one SQL statement directly (for test setup and assertions)."""
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            result = connection.execute(text(statement), params)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []
    finally:
        engine.dispose()


@pytest.fixture
def teams_on(migrated_database_url: str) -> Iterator[None]:
    """Teams are off by default (ADR 0016): switch them on for one test, then back."""
    run_sql(
        migrated_database_url,
        "INSERT INTO app_settings (key, value) VALUES ('feature:teams', 'true'::jsonb) "
        "ON CONFLICT (key) DO UPDATE SET value = 'true'::jsonb",
    )
    app_settings.cache.invalidate()
    yield
    run_sql(migrated_database_url, "DELETE FROM app_settings WHERE key = 'feature:teams'")
    app_settings.cache.invalidate()
