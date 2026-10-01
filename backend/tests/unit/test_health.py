from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.core.config import Environment, Settings
from app.main import create_app
from tests.conftest import SettingsFactory


async def test_liveness_reports_service_identity(client: AsyncClient, settings: Settings) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment.value,
    }


async def test_liveness_sets_security_headers(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


async def test_openapi_documents_health_endpoints(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/health/ready" in paths


async def test_responses_are_not_cacheable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in response.headers  # local: plain http


async def test_deployed_environments_send_hsts(make_settings: SettingsFactory) -> None:
    app = create_app(make_settings(environment=Environment.STAGING, email_backend="smtp"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.get("/api/v1/health")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
