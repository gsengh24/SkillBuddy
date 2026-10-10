"""Team chat through the API, against real PostgreSQL (ADR 0016)."""

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
from app.models import MESSAGE_MAX_LENGTH
from app.services import app_settings
from app.services.chat import purge_old_messages
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_chat import connect, poll, say
from tests.integration.test_intros import Person, join
from tests.integration.test_teams import TEAMS, out, pair_in_team

pytestmark = pytest.mark.usefixtures("teams_on")


@pytest.fixture
def make(make_settings: SettingsFactory, migrated_database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {"database_url": migrated_database_url, "ai_llm_enabled": False}
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


async def tell(client: AsyncClient, person: Person, team: str, body: str) -> Any:
    return await client.post(
        f"{TEAMS}/{team}/messages", json={"body": body}, headers=person.headers
    )


async def history(client: AsyncClient, person: Person, team: str, **params: Any) -> Any:
    return await client.get(f"{TEAMS}/{team}/messages", params=params, headers=person.headers)


async def my_team(client: AsyncClient, person: Person, team: str) -> dict[str, Any]:
    items = (await client.get(TEAMS, headers=person.headers)).json()["items"]
    return next(item for item in items if item["id"] == team)


async def test_members_chat_and_the_one_poll_carries_it(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        start = (await poll(client, ravi)).json()
        first = await tell(client, asha, team, "  Kick-off at six?  ")
        second = await tell(client, ravi, team, "Works for me.")
        page = (await history(client, asha, team)).json()
        older = (await history(client, asha, team, limit=1)).json()
        rest = (await history(client, asha, team, limit=1, before=older["next_cursor"])).json()
        polled = (await poll(client, ravi, start["cursor"])).json()
        unread_before = await my_team(client, asha, team)
        read = await client.post(f"{TEAMS}/{team}/read", headers=asha.headers)
        unread_after = await my_team(client, asha, team)

    assert start["team_items"] == []
    assert first.status_code == 201, first.text
    assert first.json()["body"] == "Kick-off at six?"
    assert (first.json()["team_id"], first.json()["sender_id"]) == (team, asha.id)
    assert [item["body"] for item in page["items"]] == ["Works for me.", "Kick-off at six?"]
    assert page["retention_days"] == 90
    assert [item["body"] for item in older["items"]] == ["Works for me."]
    assert [item["body"] for item in rest["items"]] == ["Kick-off at six?"]
    assert [item["body"] for item in polled["team_items"]] == ["Kick-off at six?", "Works for me."]
    assert polled["items"] == []
    # Asha sent first, so only Ravi's message is unread for her.
    assert unread_before["unread"] == 1
    assert unread_before["last_message_at"] == second.json()["created_at"]
    assert read.status_code == 204
    assert unread_after["unread"] == 0


async def test_one_cursor_orders_team_and_one_to_one_messages(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        connection = (await client.get("/api/v1/connections", headers=asha.headers)).json()[
            "items"
        ][0]["id"]
        start = (await poll(client, ravi)).json()
        await tell(client, asha, team, "team one")
        await say(client, asha, connection, "direct two")
        await tell(client, asha, team, "team three")
        first = (
            await client.get(
                "/api/v1/messages/updates",
                params={"after": start["cursor"], "limit": 2},
                headers=ravi.headers,
            )
        ).json()
        everything = (await poll(client, ravi, start["cursor"])).json()

    assert [item["body"] for item in first["team_items"]] == ["team one"]
    assert [item["body"] for item in first["items"]] == ["direct two"]
    assert first["has_more"] is True
    assert [item["body"] for item in everything["team_items"]] == ["team one", "team three"]
    assert [item["body"] for item in everything["items"]] == ["direct two"]
    assert everything["has_more"] is False


async def test_only_members_of_an_open_team(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        mina = await join(client, settings, delivery, "Mina")
        await tell(client, asha, team, "For the team only")
        outsider_start = (await poll(client, mina)).json()
        refused = [
            await tell(client, mina, team, "Let me in"),
            await history(client, mina, team),
            await client.post(f"{TEAMS}/{team}/read", headers=mina.headers),
            await tell(client, asha, str(uuid.uuid4()), "Nobody here"),
        ]
        signed_out = await client.get(f"{TEAMS}/{team}/messages")
        ravi_start = (await poll(client, ravi)).json()
        assert (await out(client, ravi, team, ravi)).status_code == 204
        await tell(client, asha, team, "After Ravi left")
        after_leaving = [
            await tell(client, ravi, team, "Still here?"),
            await history(client, ravi, team),
        ]
        ravi_poll = (await poll(client, ravi, ravi_start["cursor"])).json()
        mina_poll = (await poll(client, mina, outsider_start["cursor"])).json()

    for response in refused + after_leaving:
        assert response.status_code == 404
        assert error_code(response) == "team_not_found"
    assert signed_out.status_code == 401
    assert ravi_poll["team_items"] == []
    assert mina_poll["team_items"] == []


async def test_limits_validation_and_switches(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(messages_per_day=2)
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        invalid = [
            await tell(client, asha, team, "   "),
            await tell(client, asha, team, "x" * (MESSAGE_MAX_LENGTH + 1)),
        ]
        sent = [await tell(client, asha, team, f"message {n}") for n in range(3)]
        start = (await poll(client, ravi)).json()
        # With teams switched off, the poll leaves team messages out and the endpoints stop.
        run_sql(url, "UPDATE app_settings SET value = 'false'::jsonb WHERE key = 'feature:teams'")
        app_settings.cache.invalidate()
        off_poll = (await poll(client, ravi, start["cursor"])).json()
        off_send = await tell(client, ravi, team, "hello?")

    assert [response.status_code for response in invalid] == [422, 422]
    assert [response.status_code for response in sent] == [201, 201, 429]
    assert off_poll["team_items"] == []
    assert error_code(off_send) == "feature_off"


async def test_team_messages_are_purged_and_go_with_the_team(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, team = await pair_in_team(client, settings, delivery, url)
        old = (await tell(client, asha, team, "Old")).json()
        await tell(client, asha, team, "Recent")
    run_sql(
        url,
        "UPDATE team_messages SET created_at = now() - interval '91 days' WHERE id = :m",
        m=old["id"],
    )

    async with session_factory() as db:
        deleted = await purge_old_messages(db, settings, datetime.now(UTC))

    def bodies() -> list[str]:
        rows = run_sql(url, "SELECT body FROM team_messages WHERE team_id = :t", t=team)
        return [row["body"] for row in rows]

    assert deleted >= 1
    assert bodies() == ["Recent"]
    run_sql(url, "DELETE FROM teams WHERE id = :t", t=team)
    assert bodies() == []


async def test_one_to_one_chat_is_unchanged(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        start = (await poll(client, ravi)).json()
        await say(client, asha, connection, "Hi Ravi")
        polled = (await poll(client, ravi, start["cursor"])).json()

    assert [item["body"] for item in polled["items"]] == ["Hi Ravi"]
    assert polled["team_items"] == []
