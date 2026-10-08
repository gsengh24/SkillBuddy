"""Feature switches and limits (A6), against real PostgreSQL.

Switches are global, so these tests use their own fresh database, and the in-process cache
is cleared before and after each test so nothing leaks into other tests.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from httpx import AsyncClient, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, AIResult, FallbackReason, Prompt, Source, Task
from app.ai.providers import FakeProvider
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import INTENTS, MESSAGE_MAX_LENGTH, AdminRole
from app.services import app_settings
from app.services.app_settings import Feature, Limit
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import Person, admin_with, email, two_step
from tests.integration.test_admin_portal import join as join_admin
from tests.integration.test_auth_codes import error_code
from tests.integration.test_chat import connect, say

SETTINGS = "/api/v1/admin/settings"
FEATURES = "/api/v1/features"
REASON = "Incident on the chat service tonight."
OWNER = email("owner")


@pytest.fixture(autouse=True)
def fresh_cache() -> Iterator[None]:
    app_settings.cache.invalidate()
    yield
    app_settings.cache.invalidate()


@pytest.fixture
def fresh_url() -> Iterator[str]:
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def settings(make_settings: SettingsFactory, fresh_url: str) -> Settings:
    return make_settings(
        database_url=fresh_url,
        ai_llm_enabled=False,
        admin_owner_emails=[OWNER],
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
        otp_request_limit_per_ip=1000,
        otp_verify_limit_per_ip=1000,
    )


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def owner_of(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Person:
    owner = await join_admin(client, settings, delivery, OWNER)
    await two_step(client, owner)
    return owner


async def test_defaults_equal_todays_behaviour(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        page = (await client.get(SETTINGS, headers=owner.headers)).json()
        public = (await client.get(FEATURES)).json()

    assert page["server"] == {
        "app_name": settings.app_name,
        "terms_version": settings.terms_version,
        "environment": settings.environment.value,
    }
    assert page["signup_mode"] == "open"
    assert {f["key"]: f["on"] for f in page["features"]} == {f.value: True for f in Feature}
    limits = {item["key"]: (item["value"], item["default"]) for item in page["limits"]}
    assert limits == {
        "match_requests_per_day": (settings.match_requests_per_day,) * 2,
        "intros_per_day": (settings.intros_per_day,) * 2,
        "max_pending_intros": (settings.max_pending_intros,) * 2,
        "message_max_length": (MESSAGE_MAX_LENGTH,) * 2,
    }
    assert page["intents"] == list(INTENTS)
    assert public == {
        "features": {f.value: True for f in Feature},
        "message_max_length": MESSAGE_MAX_LENGTH,
    }


async def test_a_switch_turned_off_blocks_its_endpoints(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async def switch(owner: Person, feature: str, on: bool) -> int:
        response = await client.post(
            f"{SETTINGS}/features/{feature}",
            json={"on": on, "reason": REASON},
            headers=owner.headers,
        )
        return response.status_code

    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        asha, _, connection = await connect(client, settings, delivery, fresh_url)
        before = await say(client, asha, connection, "before")
        assert [
            await switch(owner, f, False) for f in ("chats", "intro_requests", "pair_spaces")
        ] == [
            204,
            204,
            204,
        ]
        chat = await say(client, asha, connection, "during")
        history = await client.get(
            f"/api/v1/connections/{connection}/messages", headers=asha.headers
        )
        intro = await client.post(
            f"/api/v1/matches/{uuid.uuid4()}/intro", json={"note": "Hi"}, headers=asha.headers
        )
        space = await client.get(f"/api/v1/connections/{connection}/space", headers=asha.headers)
        public = (await client.get(FEATURES)).json()["features"]
        assert await switch(owner, "chats", True) == 204
        after = await say(client, asha, connection, "after")

    assert before.status_code == 201
    assert chat.status_code == 503
    assert error_code(chat) == "feature_off"
    assert chat.json()["error"]["details"] == [{"feature": "chats"}]
    assert error_code(history) == "feature_off"
    assert error_code(intro) == "feature_off"
    assert error_code(space) == "feature_off"
    assert public == {
        "intro_requests": False,
        "chats": False,
        "ai_matching": True,
        "pair_spaces": False,
        "email_notifications": True,
    }
    assert after.status_code == 201
    actions = run_sql(
        fresh_url,
        "SELECT action, target_id FROM admin_audit_log WHERE action LIKE 'settings.%' "
        "ORDER BY created_at",
    )
    assert [(row["action"], row["target_id"]) for row in actions] == [
        ("settings.feature_off", "chats"),
        ("settings.feature_off", "intro_requests"),
        ("settings.feature_off", "pair_spaces"),
        ("settings.feature_on", "chats"),
    ]


async def test_limits_are_stored_checked_and_enforced(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async def set_limit(owner: Person, key: str, value: int) -> Response:
        return await client.post(
            f"{SETTINGS}/limits/{key}",
            json={"value": value, "reason": REASON},
            headers=owner.headers,
        )

    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        asha, _, connection = await connect(client, settings, delivery, fresh_url)
        changed = await set_limit(owner, "message_max_length", 100)
        too_low = await set_limit(owner, "message_max_length", 10)
        too_high = await set_limit(owner, "intros_per_day", 101)
        long = await say(client, asha, connection, "x" * 101)
        fits = await say(client, asha, connection, "x" * 100)
        page = (await client.get(SETTINGS, headers=owner.headers)).json()
        public = (await client.get(FEATURES)).json()

    assert changed.status_code == 204
    assert error_code(too_low) == "limit_out_of_range"
    assert error_code(too_high) == "limit_out_of_range"
    assert long.status_code == 422
    assert error_code(long) == "message_too_long"
    assert fits.status_code == 201
    message = next(item for item in page["limits"] if item["key"] == "message_max_length")
    assert (message["value"], message["default"]) == (100, MESSAGE_MAX_LENGTH)
    assert public["message_max_length"] == 100
    rows = run_sql(
        fresh_url,
        "SELECT target_id FROM admin_audit_log WHERE action = 'settings.limit_changed'",
    )
    assert [row["target_id"] for row in rows] == ["message_max_length=100"]


async def test_stored_limits_replace_the_server_defaults(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], fresh_url: str
) -> None:
    async with session_factory() as db:
        assert await app_settings.limit(db, settings, Limit.MAX_PENDING_INTROS) == (
            settings.max_pending_intros
        )
    run_sql(
        fresh_url,
        "INSERT INTO app_settings (key, value) VALUES ('limit:max_pending_intros', '3'::jsonb), "
        "('limit:intros_per_day', '999'::jsonb), ('feature:chats', '\"no\"'::jsonb)",
    )
    app_settings.cache.invalidate()
    async with session_factory() as db:
        assert await app_settings.limit(db, settings, Limit.MAX_PENDING_INTROS) == 3
        # Out of range or the wrong type: ignored, so the default stands.
        assert await app_settings.limit(db, settings, Limit.INTROS_PER_DAY) == (
            settings.intros_per_day
        )
        assert await app_settings.is_on(db, Feature.CHATS) is True


async def test_the_cache_expires_after_a_minute(
    session_factory: async_sessionmaker[AsyncSession], fresh_url: str
) -> None:
    now = [1000.0]
    original = app_settings.cache.clock
    app_settings.cache.clock = lambda: now[0]
    try:
        async with session_factory() as db:
            assert await app_settings.is_on(db, Feature.CHATS) is True
        run_sql(
            fresh_url,
            "INSERT INTO app_settings (key, value) VALUES ('feature:chats', 'false'::jsonb)",
        )
        async with session_factory() as db:
            cached = await app_settings.is_on(db, Feature.CHATS)
            now[0] += 59
            still_cached = await app_settings.is_on(db, Feature.CHATS)
            now[0] += 2
            fresh = await app_settings.is_on(db, Feature.CHATS)
    finally:
        app_settings.cache.clock = original

    assert (cached, still_cached, fresh) == (True, True, False)


class Answer(BaseModel):
    answer: str


async def test_ai_matching_off_uses_the_rule_based_fallback(
    make_settings: SettingsFactory,
    fresh_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=fresh_url, ai_llm_enabled=True)

    async def ask() -> AIResult[Answer]:
        provider = FakeProvider(
            name=f"fake-{uuid.uuid4().hex[:6]}", replies=[json.dumps({"answer": "llm"})]
        )
        gateway = AIGateway(settings, session_factory, [provider], cooling_until={})
        return await gateway.complete(
            Task.SELECT,
            Prompt(version="test-v1", system="Pick.", data={"q": "hi"}, name_hints=[]),
            Answer,
            user_id=str(uuid.uuid4()),
            fallback=lambda: Answer(answer="template"),
        )

    on = await ask()
    run_sql(
        fresh_url,
        "INSERT INTO app_settings (key, value) VALUES ('feature:ai_matching', 'false'::jsonb)",
    )
    app_settings.cache.invalidate()
    off = await ask()

    assert (on.source, on.value) == (Source.LLM, Answer(answer="llm"))
    assert (off.source, off.reason, off.value) == (
        Source.TEMPLATE,
        FallbackReason.DISABLED,
        Answer(answer="template"),
    )


async def test_only_owners_and_admins_manage_settings(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        people = {
            role: await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        }
        views = {
            role.value: (await client.get(SETTINGS, headers=person.headers)).status_code
            for role, person in people.items()
        }
        no_reason = await client.post(
            f"{SETTINGS}/features/chats",
            json={"on": False, "reason": "short"},
            headers=owner.headers,
        )
        moderator = await client.post(
            f"{SETTINGS}/features/chats",
            json={"on": False, "reason": REASON},
            headers=people[AdminRole.MODERATOR].headers,
        )
        unknown = await client.post(
            f"{SETTINGS}/features/teleport",
            json={"on": False, "reason": REASON},
            headers=owner.headers,
        )
        chats = (await client.get(FEATURES)).json()["features"]["chats"]

    assert views == {"admin": 200, "moderator": 403, "readonly": 403}
    assert no_reason.status_code == 422
    assert moderator.status_code == 403
    assert unknown.status_code == 422
    assert chats is True
