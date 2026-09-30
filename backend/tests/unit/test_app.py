"""App-level wiring: docs toggle, CORS, request ids."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.conftest import SettingsFactory


def _client_for(make_settings: SettingsFactory, **overrides: object) -> AsyncClient:
    app = create_app(make_settings(**overrides))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_generates_request_id_when_absent(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    int(request_id, 16)  # a uuid4 hex string


async def test_propagates_valid_caller_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "lb-trace.123:abc"})

    assert response.headers["X-Request-ID"] == "lb-trace.123:abc"


@pytest.mark.parametrize("unsafe_id", ["has spaces", "x" * 129, "line\\nbreak", "<script>"])
async def test_replaces_unsafe_caller_request_id(client: AsyncClient, unsafe_id: str) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": unsafe_id})

    assert response.headers["X-Request-ID"] != unsafe_id


async def test_docs_can_be_disabled(make_settings: SettingsFactory) -> None:
    async with _client_for(make_settings, api_docs_enabled=False) as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404


async def test_docs_enabled_by_default(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200


async def test_cors_allows_configured_origin(make_settings: SettingsFactory) -> None:
    async with _client_for(make_settings, cors_allow_origins=["http://localhost:3000"]) as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_cors_rejects_unlisted_origin(make_settings: SettingsFactory) -> None:
    async with _client_for(make_settings, cors_allow_origins=["http://localhost:3000"]) as client:
        response = await client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers
