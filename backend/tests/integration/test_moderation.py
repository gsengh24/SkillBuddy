"""The moderation API (MODERATOR_EMAILS), suspend and the audit log, against real PostgreSQL."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.services.moderation import purge_old_actions
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code, new_email, sign_in
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_chat import clear_of_minute_boundary, connect, say
from tests.integration.test_intros import Person

TOKEN = "moderator-token-for-tests-only-0123456789abcdef"  # test value


@pytest.fixture
def mod_email() -> str:
    return new_email()


@pytest.fixture
def make(
    make_settings: SettingsFactory, migrated_database_url: str, mod_email: str
) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "database_url": migrated_database_url,
            "ai_llm_enabled": False,
            "moderator_emails": [mod_email],
            "admin_api_token": TOKEN,
        }
        return make_settings(**(values | overrides))

    return build


@pytest.fixture
def settings(make: Callable[..., Settings]) -> Settings:
    return make()


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def as_person(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, email: str
) -> Person:
    await sign_in(client, delivery, email)
    token = client.cookies[settings.session_cookie_name]
    client.cookies.clear()
    me = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()
    return Person(token=token, id=me["id"])


async def reported_case(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, url: str
) -> tuple[Person, Person, str]:
    """Asha sends Ravi a message; Ravi reports it. Returns (asha, ravi, report id)."""
    asha, ravi, connection = await connect(client, settings, delivery, url)
    message = (await say(client, asha, connection, "You'll regret this")).json()
    report = await client.post(
        f"/api/v1/messages/{message['id']}/report",
        json={"reason": "safety"},
        headers=ravi.headers,
    )
    return asha, ravi, report.json()["id"]


def actions(url: str, **where: str) -> list[dict[str, Any]]:
    clause = " AND ".join(f"{key} = :{key}" for key in where)
    return run_sql(
        url,
        f"SELECT moderator_id, action, subject_id, report_id, note FROM moderation_actions "  # noqa: S608  # test helper, keys are fixed
        f"WHERE {clause} ORDER BY created_at",
        **where,
    )


async def test_only_moderators_get_in(
    settings: Settings, delivery: CapturingDelivery, mod_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        mod = await as_person(client, settings, delivery, mod_email)
        someone = await as_person(client, settings, delivery, new_email())
        mod_me = (await client.get("/api/v1/auth/me", headers=mod.headers)).json()
        someone_me = (await client.get("/api/v1/auth/me", headers=someone.headers)).json()
        refused = [
            await client.get("/api/v1/moderation/reports", headers=someone.headers),
            await client.get("/api/v1/moderation/accounts/suspended", headers=someone.headers),
            await client.post(
                f"/api/v1/moderation/accounts/{mod.id}/suspend", json={}, headers=someone.headers
            ),
        ]
        anonymous = await client.get("/api/v1/moderation/reports")
        allowed = await client.get("/api/v1/moderation/reports", headers=mod.headers)

    assert mod_me["is_moderator"] is True
    assert someone_me["is_moderator"] is False
    for response in refused:
        assert response.status_code == 403
        assert error_code(response) == "moderator_only"
    assert anonymous.status_code == 401
    assert allowed.status_code == 200


async def test_resolving_is_logged_with_who_did_it(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, mod_email: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, report = await reported_case(client, settings, delivery, url)
        mod = await as_person(client, settings, delivery, mod_email)
        listed = (await client.get("/api/v1/moderation/reports", headers=mod.headers)).json()
        resolved = await client.post(
            f"/api/v1/moderation/reports/{report}/resolve",
            json={"note": "Warned them."},
            headers=mod.headers,
        )
        _, _, other = await reported_case(client, settings, delivery, url)
        by_token = await client.post(
            f"/api/v1/admin/reports/{other}/resolve", json={}, headers={"X-Admin-Token": TOKEN}
        )

    mine = next(item for item in listed["items"] if item["id"] == report)
    assert mine["reported_status"] == "active"
    assert mine["messages"][-1]["body"] == "You'll regret this"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert actions(url, report_id=report) == [
        {
            "moderator_id": uuid.UUID(mod.id),
            "action": "resolve_report",
            "subject_id": uuid.UUID(asha.id),
            "report_id": uuid.UUID(report),
            "note": "Warned them.",
        }
    ]
    assert by_token.status_code == 200
    assert actions(url, report_id=other)[0]["moderator_id"] is None


async def test_suspend_signs_them_out_and_unsuspend_lets_them_back(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, mod_email: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, report = await reported_case(client, settings, delivery, url)
        mod = await as_person(client, settings, delivery, mod_email)
        base = f"/api/v1/moderation/accounts/{asha.id}"
        suspended = await client.post(
            f"{base}/suspend", json={"note": "Threats.", "report_id": report}, headers=mod.headers
        )
        asha_now = await client.get("/api/v1/auth/me", headers=asha.headers)
        listed = (
            await client.get("/api/v1/moderation/accounts/suspended", headers=mod.headers)
        ).json()
        shown = await client.get(f"/api/v1/moderation/reports/{report}", headers=mod.headers)
        again = await client.post(f"{base}/suspend", json={}, headers=mod.headers)
        unsuspended = await client.post(f"{base}/unsuspend", json={}, headers=mod.headers)
        twice = await client.post(f"{base}/unsuspend", json={}, headers=mod.headers)
        myself = await client.post(
            f"/api/v1/moderation/accounts/{mod.id}/suspend", json={}, headers=mod.headers
        )
        unknown = await client.post(
            f"/api/v1/moderation/accounts/{uuid.uuid4()}/suspend", json={}, headers=mod.headers
        )

    assert suspended.status_code == 200, suspended.text
    body = suspended.json()
    assert body["status"] == "suspended"
    assert "email" not in body
    assert asha_now.status_code == 401  # signed out everywhere
    entry = next(item for item in listed["items"] if item["user_id"] == asha.id)
    assert entry["note"] == "Threats."
    assert entry["suspended_at"] is not None
    assert shown.json()["reported_status"] == "suspended"
    assert again.status_code == 409
    assert error_code(again) == "cannot_suspend"
    assert unsuspended.status_code == 200
    assert unsuspended.json()["status"] == "active"
    assert twice.status_code == 409
    assert error_code(twice) == "not_suspended"
    assert myself.status_code == 409
    assert unknown.status_code == 404
    assert error_code(unknown) == "account_not_found"
    kinds = [row["action"] for row in actions(url, subject_id=asha.id)]
    assert kinds == ["suspend_user", "unsuspend_user"]


async def test_moderation_requests_are_rate_limited(
    make: Callable[..., Settings], delivery: CapturingDelivery, mod_email: str
) -> None:
    settings = make(moderation_requests_per_minute=3)
    async with auth_client(settings, delivery) as client:
        mod = await as_person(client, settings, delivery, mod_email)
        await clear_of_minute_boundary()
        statuses = [
            (await client.get("/api/v1/moderation/reports", headers=mod.headers)).status_code
            for _ in range(4)
        ]

    assert statuses == [200, 200, 200, 429]


async def test_the_audit_log_is_purged_after_a_year(
    settings: Settings,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    old = run_sql(
        url,
        "INSERT INTO moderation_actions (action, note, created_at) "
        "VALUES ('unsuspend_user', 'old', now() - interval '366 days') RETURNING id",
    )[0]["id"]
    recent = run_sql(
        url,
        "INSERT INTO moderation_actions (action, note) VALUES ('unsuspend_user', 'recent') "
        "RETURNING id",
    )[0]["id"]

    async with session_factory() as db:
        await purge_old_actions(db, settings, datetime.now(UTC))

    left = {row["id"] for row in run_sql(url, "SELECT id FROM moderation_actions")}
    assert old not in left
    assert recent in left
