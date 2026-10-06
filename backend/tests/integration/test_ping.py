"""``/ping`` makes no database call, with the full app and a real PostgreSQL engine."""

from __future__ import annotations

from typing import Any

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.config import Settings
from app.main import create_app


async def test_ping_makes_zero_database_calls(integration_settings: Settings) -> None:
    app = create_app(integration_settings)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(str(args[2]))  # the SQL text

    async with LifespanManager(app) as manager:
        engine = app.state.engine.sync_engine  # set by the lifespan
        event.listen(engine, "before_cursor_execute", count)
        try:
            transport = ASGITransport(app=manager.app)
            async with AsyncClient(transport=transport, base_url="https://testserver") as http:
                get = await http.get("/ping")
                head = await http.head("/ping")
                after_ping = len(statements)
                # Prove the counter works: readiness does query the database.
                ready = await http.get("/api/v1/health/ready")
        finally:
            event.remove(engine, "before_cursor_execute", count)

    assert get.status_code == 200
    assert head.status_code == 200
    assert after_ping == 0
    assert ready.status_code == 200
    assert len(statements) > 0
