"""Chat through the API, against real PostgreSQL (ADR 0012)."""

from __future__ import annotations

import asyncio
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
from app.services import blocks
from app.services.chat import purge_old_messages
from app.services.cursors import encode
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_intros import Person, join, matched, send

LONG_AGO = encode(datetime(2000, 1, 1, tzinfo=UTC), uuid.UUID(int=0))


async def clear_of_minute_boundary() -> None:
    """Per-minute limits use fixed windows: start a counting test well inside one."""
    second = datetime.now(UTC).second
    if second >= 50:
        await asyncio.sleep(61 - second)


@pytest.fixture
def make(make_settings: SettingsFactory, migrated_database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        return make_settings(database_url=migrated_database_url, ai_llm_enabled=False, **overrides)

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


async def connect(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, url: str
) -> tuple[Person, Person, str]:
    """Two people who accepted an intro. Returns (sender, recipient, connection id)."""
    asha = await join(client, settings, delivery, "Asha")
    ravi = await join(client, settings, delivery, "Ravi")
    _, match = matched(url, asha, ravi)
    intro = (await send(client, asha, match)).json()
    answer = await client.post(
        f"/api/v1/intros/{intro['id']}/respond", json={"accept": True}, headers=ravi.headers
    )
    assert answer.status_code == 200, answer.text
    connections = (await client.get("/api/v1/connections", headers=asha.headers)).json()
    return asha, ravi, connections["items"][0]["id"]


async def say(client: AsyncClient, person: Person, connection: str, body: str) -> Any:
    return await client.post(
        f"/api/v1/connections/{connection}/messages", json={"body": body}, headers=person.headers
    )


async def poll(client: AsyncClient, person: Person, after: str | None = None) -> Any:
    params = {"after": after} if after else {}
    return await client.get("/api/v1/messages/updates", params=params, headers=person.headers)


# --- sending and reading ------------------------------------------------------------------


async def test_both_people_send_and_read_newest_first(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        first = await say(client, asha, connection, "  Hi Ravi!  ")
        second = await say(client, ravi, connection, "Hello Asha.")
        page = await client.get(f"/api/v1/connections/{connection}/messages", headers=asha.headers)

    assert first.status_code == 201, first.text
    assert first.json()["body"] == "Hi Ravi!"
    assert first.json()["sender_id"] == asha.id
    assert first.json()["connection_id"] == connection
    assert second.json()["sender_id"] == ravi.id
    items = page.json()["items"]
    assert [item["body"] for item in items] == ["Hello Asha.", "Hi Ravi!"]
    assert page.json()["next_cursor"] is None
    assert page.json()["retention_days"] == 90


async def test_history_pages_back_with_before(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, migrated_database_url)
        for number in range(3):
            await say(client, asha, connection, f"message {number}")
        url = f"/api/v1/connections/{connection}/messages"
        first = (await client.get(url, params={"limit": 2}, headers=asha.headers)).json()
        rest = (
            await client.get(
                url, params={"limit": 2, "before": first["next_cursor"]}, headers=asha.headers
            )
        ).json()

    assert [item["body"] for item in first["items"]] == ["message 2", "message 1"]
    assert [item["body"] for item in rest["items"]] == ["message 0"]
    assert rest["next_cursor"] is None


async def test_no_messages_without_an_accepted_connection(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(migrated_database_url, asha, ravi)
        await send(client, asha, match)  # pending, not accepted
        connections = (await client.get("/api/v1/connections", headers=asha.headers)).json()
        unknown = await say(client, asha, str(uuid.uuid4()), "Hi")

    assert connections["items"] == []
    assert unknown.status_code == 404
    assert error_code(unknown) == "conversation_not_found"


async def test_outsiders_cannot_send_read_or_mark_read(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, migrated_database_url)
        await say(client, asha, connection, "Just between us.")
        mallory = await join(client, settings, delivery, "Mallory")
        sent = await say(client, mallory, connection, "Hi")
        read = await client.get(
            f"/api/v1/connections/{connection}/messages", headers=mallory.headers
        )
        marked = await client.post(
            f"/api/v1/connections/{connection}/read", headers=mallory.headers
        )
        start = (await poll(client, mallory)).json()
        run_sql(
            migrated_database_url,
            "UPDATE messages SET created_at = now() - interval '1 minute' WHERE connection_id = :c",
            c=connection,
        )
        polled = await poll(client, mallory, LONG_AGO)

    for response in (sent, read, marked):
        assert response.status_code == 404
        assert error_code(response) == "conversation_not_found"
    assert start["items"] == []
    assert polled.status_code == 200
    assert polled.json()["items"] == []


async def test_requests_need_a_session(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        connection = str(uuid.uuid4())
        responses = [
            await client.get(f"/api/v1/connections/{connection}/messages"),
            await client.post(f"/api/v1/connections/{connection}/messages", json={"body": "x"}),
            await client.post(f"/api/v1/connections/{connection}/read"),
            await client.get("/api/v1/messages/updates"),
        ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401]


@pytest.mark.parametrize("body", ["", "   ", "x" * (MESSAGE_MAX_LENGTH + 1)])
async def test_message_text_is_validated(
    body: str, settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, migrated_database_url)
        response = await say(client, asha, connection, body)
        longest = await say(client, asha, connection, "y" * MESSAGE_MAX_LENGTH)

    assert response.status_code == 422
    assert longest.status_code == 201


async def test_no_sending_to_an_account_being_deleted(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        await say(client, asha, connection, "Before.")
        run_sql(
            migrated_database_url,
            "UPDATE users SET status = 'pending_deletion' WHERE id = :u",
            u=ravi.id,
        )
        refused = await say(client, asha, connection, "After.")
        history = await client.get(
            f"/api/v1/connections/{connection}/messages", headers=asha.headers
        )

    assert refused.status_code == 409
    assert error_code(refused) == "conversation_closed"
    assert [item["body"] for item in history.json()["items"]] == ["Before."]


# --- polling ------------------------------------------------------------------------------


async def test_polling_delivers_new_messages_and_never_skips_one(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        start = (await poll(client, ravi)).json()
        sent = (await say(client, asha, connection, "Are you free on Friday?")).json()
        first = (await poll(client, ravi, start["cursor"])).json()
        # Within a few seconds of sending, the cursor holds back: the message can repeat.
        again = (await poll(client, ravi, first["cursor"])).json()
        # Once older than the visibility lag, the cursor moves past it.
        run_sql(
            migrated_database_url,
            "UPDATE messages SET created_at = now() - interval '1 minute' WHERE id = :m",
            m=sent["id"],
        )
        settled = (await poll(client, ravi, start["cursor"])).json()
        after = (await poll(client, ravi, settled["cursor"])).json()

    assert start["items"] == []
    assert start["poll_after_seconds"] is None
    assert [item["id"] for item in first["items"]] == [sent["id"]]
    assert first["items"][0]["sender_id"] == asha.id
    assert first["has_more"] is False
    assert [item["id"] for item in again["items"]] == [sent["id"]]
    assert after["items"] == []


async def test_poll_reports_has_more_and_rejects_a_bad_cursor(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        start = (await poll(client, ravi)).json()
        for number in range(3):
            await say(client, asha, connection, f"m{number}")
        page = await client.get(
            "/api/v1/messages/updates",
            params={"after": start["cursor"], "limit": 2},
            headers=ravi.headers,
        )
        bad = await poll(client, ravi, "not-a-cursor")

    assert [item["body"] for item in page.json()["items"]] == ["m0", "m1"]
    assert page.json()["has_more"] is True
    assert bad.status_code == 400
    assert error_code(bad) == "invalid_cursor"


async def test_unread_counts_and_mark_read(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        await say(client, asha, connection, "One")
        await say(client, asha, connection, "Two")
        ravi_before = (await client.get("/api/v1/connections", headers=ravi.headers)).json()
        asha_view = (await client.get("/api/v1/connections", headers=asha.headers)).json()
        marked = await client.post(f"/api/v1/connections/{connection}/read", headers=ravi.headers)
        ravi_after = (await client.get("/api/v1/connections", headers=ravi.headers)).json()

    assert ravi_before["items"][0]["unread_messages"] == 2
    assert ravi_before["items"][0]["last_message_at"] is not None
    assert asha_view["items"][0]["unread_messages"] == 0  # your own messages are read
    assert marked.status_code == 204
    assert ravi_after["items"][0]["unread_messages"] == 0


async def test_a_block_stops_sending_and_reading_both_ways(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hook item 7 fills in: chat asks ``blocks.blocked_with`` on every path."""
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        start = (await poll(client, ravi)).json()
        await say(client, asha, connection, "Before the block.")
        run_sql(
            migrated_database_url,
            "UPDATE messages SET created_at = now() - interval '1 minute' WHERE connection_id = :c",
            c=connection,
        )
        pair = {uuid.UUID(asha.id): uuid.UUID(ravi.id), uuid.UUID(ravi.id): uuid.UUID(asha.id)}

        async def blocked(_db: Any, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
            return frozenset({pair[user_id]}) if user_id in pair else frozenset()

        monkeypatch.setattr(blocks, "blocked_with", blocked)
        results = []
        for person in (asha, ravi):
            results += [
                await say(client, person, connection, "Hello?"),
                await client.get(
                    f"/api/v1/connections/{connection}/messages", headers=person.headers
                ),
                await client.post(f"/api/v1/connections/{connection}/read", headers=person.headers),
            ]
        polled = (await poll(client, ravi, start["cursor"])).json()

    assert [response.status_code for response in results] == [404] * 6
    assert polled["items"] == []


# --- limits -------------------------------------------------------------------------------


async def test_daily_message_limit(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    settings = make(messages_per_day=2)
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, migrated_database_url)
        statuses = [(await say(client, asha, connection, "x")).status_code for _ in range(3)]

    assert statuses == [201, 201, 429]


async def test_per_person_poll_limit(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    settings = make(chat_polls_per_minute=5)
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        await clear_of_minute_boundary()
        responses = [await poll(client, asha) for _ in range(6)]

    assert [response.status_code for response in responses] == [200] * 5 + [429]
    assert int(responses[-1].headers["Retry-After"]) <= 60


async def test_spent_daily_budget_slows_chat_to_one_poll_a_minute(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    settings = make(chat_polls_per_day=1)
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        await clear_of_minute_boundary()
        normal = await poll(client, asha)
        slow = await poll(client, asha)
        refused = await poll(client, asha)

    assert normal.json()["poll_after_seconds"] is None
    assert slow.status_code == 200
    assert slow.json()["poll_after_seconds"] == 60
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) <= 60


# --- retention ----------------------------------------------------------------------------


async def test_messages_are_purged_after_the_retention_period(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, url)
        old = (await say(client, asha, connection, "Old")).json()
        await say(client, asha, connection, "Recent")
    run_sql(
        url,
        "UPDATE messages SET created_at = now() - interval '91 days' WHERE id = :m",
        m=old["id"],
    )

    async with session_factory() as db:
        deleted = await purge_old_messages(db, settings, datetime.now(UTC))

    assert deleted >= 1
    left = run_sql(url, "SELECT body FROM messages WHERE connection_id = :c", c=connection)
    assert [row["body"] for row in left] == ["Recent"]
    assert settings.message_retention_days == 90


async def test_deleting_an_account_deletes_the_conversation(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        await say(client, asha, connection, "Hi")
        await say(client, ravi, connection, "Hello")
    run_sql(url, "DELETE FROM users WHERE id = :u", u=ravi.id)

    assert run_sql(url, "SELECT 1 FROM messages WHERE connection_id = :c", c=connection) == []
