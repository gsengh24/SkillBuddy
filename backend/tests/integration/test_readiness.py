"""Readiness against real dependencies: no mocks, so a pass means the wiring works."""

from __future__ import annotations

from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import live_client


async def test_ready_when_all_dependencies_are_up(integration_settings: Settings) -> None:
    async with live_client(integration_settings) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"database", "pgvector", "redis"}
    assert all(check["status"] == "ok" for check in body["checks"].values())


async def test_unavailable_when_redis_is_unreachable(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url="redis://127.0.0.1:1/0",  # nothing listens on port 1
        readiness_timeout_seconds=1.0,
    )

    async with live_client(settings) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    checks = response.json()["checks"]
    assert checks["redis"]["status"] == "fail"
    assert checks["redis"]["detail"]
    assert checks["database"]["status"] == "ok"


async def test_unavailable_when_pgvector_is_missing(
    make_settings: SettingsFactory, empty_database_url: str
) -> None:
    # A fresh database has no extensions until the first migration runs.
    settings = make_settings(database_url=empty_database_url)

    async with live_client(settings) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    checks = response.json()["checks"]
    assert checks["database"]["status"] == "ok"
    assert checks["pgvector"] == {
        "status": "fail",
        "latency_ms": checks["pgvector"]["latency_ms"],
        "detail": "pgvector extension is not installed",
    }
