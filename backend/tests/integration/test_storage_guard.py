"""The storage monitor endpoint and the pause at the free-tier storage limit."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.api.deps import require_storage_capacity
from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    auth_client,
)
from tests.integration.test_auth_codes import error_code, new_email, request_code, sign_in, verify

ADMIN_TOKEN = "test-admin-token-with-more-than-32-characters"
STORAGE = "/api/v1/admin/storage"


def guarded_settings(
    make_settings: SettingsFactory, database_url: str, **overrides: object
) -> Settings:
    return make_settings(
        database_url=database_url,
        admin_api_token=ADMIN_TOKEN,
        **overrides,
    )


async def _get_report(client: AsyncClient, token: str | None) -> tuple[int, dict[str, object]]:
    headers = {} if token is None else {"X-Admin-Token": token}
    response = await client.get(STORAGE, headers=headers)
    return response.status_code, response.json()


async def test_storage_endpoint_is_disabled_without_a_configured_token(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        status, _ = await _get_report(client, ADMIN_TOKEN)

    assert status == 404


async def test_storage_endpoint_requires_the_admin_token(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = guarded_settings(make_settings, migrated_database_url)
    async with auth_client(settings, delivery) as client:
        missing, _ = await _get_report(client, None)
        wrong, _ = await _get_report(client, "x" * 40)

    # No token and no session is anonymous (ADR 0015); a wrong token is refused.
    assert missing == 401
    assert wrong == 403


async def test_storage_report_against_the_free_limit(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = guarded_settings(make_settings, migrated_database_url)
    async with auth_client(settings, delivery) as client:
        status, report = await _get_report(client, ADMIN_TOKEN)

    assert status == 200
    assert report["status"] == "ok"
    assert isinstance(report["database_bytes"], int)
    assert report["database_bytes"] > 0
    assert report["limit_bytes"] == 500_000_000
    assert (report["warn_at_percent"], report["pause_at_percent"]) == (70, 90)
    assert isinstance(report["largest_tables"], list)
    assert {"name", "bytes"} <= set(report["largest_tables"][0])


async def test_near_the_limit_new_signups_pause_but_existing_users_sign_in(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    existing = new_email()
    normal = guarded_settings(make_settings, migrated_database_url)
    async with auth_client(normal, delivery) as client:
        await sign_in(client, delivery, existing)

    # Any real database exceeds 90% of a 1 MB limit.
    full = guarded_settings(make_settings, migrated_database_url, database_size_limit_mb=1)
    newcomer = new_email()
    async with auth_client(full, delivery) as client:
        _, report = await _get_report(client, ADMIN_TOKEN)
        await request_code(client, newcomer)
        refused = await verify(client, newcomer, delivery.last_code(newcomer))
        await request_code(client, existing)
        allowed = await verify(client, existing, delivery.last_code(existing))

    assert report["status"] == "critical"
    assert refused.status_code == 503
    assert error_code(refused) == "signups_paused"
    assert "try again later" in refused.json()["error"]["message"]
    assert allowed.status_code == 200


async def test_optional_writes_are_refused_near_the_limit(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    router = APIRouter()

    @router.post("/_test/optional-write", dependencies=[Depends(require_storage_capacity)])
    async def optional_write() -> dict[str, str]:
        return {"status": "written"}

    results = []
    for limit_mb in (500, 1):
        settings = guarded_settings(
            make_settings, migrated_database_url, database_size_limit_mb=limit_mb
        )
        async with auth_client(settings, delivery, routers=[router]) as client:
            results.append(await client.post("/_test/optional-write"))

    assert results[0].status_code == 200
    assert results[1].status_code == 503
    assert error_code(results[1]) == "storage_full"
