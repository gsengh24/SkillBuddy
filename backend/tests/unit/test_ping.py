"""``/ping``, the keep-alive for uptime monitors (no database: the app runs without its
lifespan here, so it has no engine at all)."""

from __future__ import annotations

import logging

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.conftest import SettingsFactory


def client(make_settings: SettingsFactory) -> AsyncClient:
    app = create_app(make_settings())
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver")


async def test_get_returns_ok(make_settings: SettingsFactory) -> None:
    async with client(make_settings) as http:
        response = await http.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Middleware still applies: security headers yes, cookies or sessions no.
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "set-cookie" not in response.headers


async def test_head_returns_ok(make_settings: SettingsFactory) -> None:
    async with client(make_settings) as http:
        response = await http.head("/ping")

    assert response.status_code == 200


async def test_never_rate_limited(make_settings: SettingsFactory) -> None:
    async with client(make_settings) as http:
        statuses = {(await http.get("/ping")).status_code for _ in range(60)}

    assert statuses == {200}


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


async def test_logged_at_debug_level_only(make_settings: SettingsFactory) -> None:
    # Creating the app reconfigures logging (it clears the root handlers, including pytest's
    # capture handler), so listen on the access logger itself, after the app exists.
    http_client = client(make_settings)
    access = logging.getLogger("app.access")
    collect = _Collect()
    previous = access.level
    access.addHandler(collect)
    access.setLevel(logging.DEBUG)
    try:
        async with http_client as http:
            await http.get("/ping")
            await http.get("/api/v1/health")
    finally:
        access.removeHandler(collect)
        access.setLevel(previous)

    levels = {getattr(r, "path", None): r.levelno for r in collect.records}
    assert levels["/ping"] == logging.DEBUG
    assert levels["/api/v1/health"] == logging.INFO
