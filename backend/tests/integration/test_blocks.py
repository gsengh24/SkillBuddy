"""Blocking through the API, against real PostgreSQL (ARCHITECTURE.md §8)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_chat import connect, poll, say
from tests.integration.test_intros import Person, join, matched, send


@pytest.fixture
def make(make_settings: SettingsFactory, migrated_database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        return make_settings(database_url=migrated_database_url, ai_llm_enabled=False, **overrides)

    return build


@pytest.fixture
def settings(make: Callable[..., Settings]) -> Settings:
    return make()


async def block(client: AsyncClient, person: Person, other: Person | str) -> Any:
    user_id = other if isinstance(other, str) else other.id
    return await client.post("/api/v1/blocks", json={"user_id": user_id}, headers=person.headers)


async def connections_of(client: AsyncClient, person: Person) -> list[str]:
    body = (await client.get("/api/v1/connections", headers=person.headers)).json()
    return [item["id"] for item in body["items"]]


async def test_a_block_closes_chat_and_the_connection_for_both(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        start = (await poll(client, ravi)).json()
        message = (await say(client, asha, connection, "Something nasty")).json()
        blocked = await block(client, ravi, asha)
        results = []
        for person in (asha, ravi):
            results += [
                await say(client, person, connection, "Hello?"),
                await client.get(
                    f"/api/v1/connections/{connection}/messages", headers=person.headers
                ),
                await client.post(f"/api/v1/connections/{connection}/read", headers=person.headers),
            ]
        lists = [await connections_of(client, asha), await connections_of(client, ravi)]
        run_sql(
            url,
            "UPDATE messages SET created_at = now() - interval '1 minute' WHERE id = :m",
            m=message["id"],
        )
        polled = (await poll(client, ravi, start["cursor"])).json()
        # The messages stay (until the 90-day purge), so they can still be reported.
        reported = await client.post(
            f"/api/v1/messages/{message['id']}/report",
            json={"reason": "harassment"},
            headers=ravi.headers,
        )

    assert blocked.status_code == 201, blocked.text
    body = blocked.json()
    assert body["user_id"] == asha.id
    assert body["person"]["display_name"] is None
    assert body["person"]["links"] is None
    assert [response.status_code for response in results] == [404] * 6
    assert lists == [[], []]
    assert polled["items"] == []
    assert reported.status_code == 201


async def test_unblocking_does_not_reopen_the_connection(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        await say(client, asha, connection, "Old message")
        await block(client, ravi, asha)
        listed = (await client.get("/api/v1/blocks", headers=ravi.headers)).json()
        asha_sees = (await client.get("/api/v1/blocks", headers=asha.headers)).json()
        unblocked = await client.delete(f"/api/v1/blocks/{asha.id}", headers=ravi.headers)
        again = await client.delete(f"/api/v1/blocks/{asha.id}", headers=ravi.headers)
        after = [await connections_of(client, asha), await connections_of(client, ravi)]
        still_closed = await say(client, asha, connection, "Back?")

        # A new intro, accepted, starts a fresh connection (the old messages go with the
        # ended one).
        _, match = matched(url, asha, ravi)
        intro = (await send(client, asha, match)).json()
        await client.post(
            f"/api/v1/intros/{intro['id']}/respond", json={"accept": True}, headers=ravi.headers
        )
        fresh = await connections_of(client, asha)
        history = await client.get(f"/api/v1/connections/{fresh[0]}/messages", headers=asha.headers)

    assert [item["user_id"] for item in listed["items"]] == [asha.id]
    assert asha_sees["items"] == []  # the blocked person doesn't see who blocked them
    assert unblocked.status_code == 204
    assert again.status_code == 404
    assert error_code(again) == "block_not_found"
    assert after == [[], []]
    assert still_closed.status_code == 404
    assert fresh
    assert fresh[0] != connection
    assert history.json()["items"] == []


async def test_blocking_from_an_intro_withdraws_it_and_stops_new_ones(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, first_match = matched(url, asha, ravi)
        intro = (await send(client, asha, first_match)).json()
        blocked = await block(client, ravi, asha)
        inbox = (await client.get("/api/v1/intros?box=received", headers=ravi.headers)).json()
        sent = (await client.get("/api/v1/intros?box=sent", headers=asha.headers)).json()
        one = await client.get(f"/api/v1/intros/{intro['id']}", headers=asha.headers)
        _, second_match = matched(url, asha, ravi)
        retry = await send(client, asha, second_match)
        # The other way round too: Ravi can't send to Asha.
        _, reverse = matched(url, ravi, asha)
        reverse_try = await send(client, ravi, reverse)

    assert blocked.status_code == 201
    status = run_sql(url, "SELECT status FROM intros WHERE id = :i", i=intro["id"])[0]["status"]
    assert status == "withdrawn"
    assert inbox["items"] == []
    assert sent["items"] == []
    assert one.status_code == 404
    for response in (retry, reverse_try):
        assert response.status_code == 409
        assert error_code(response) == "candidate_unavailable"


async def test_blocked_people_disappear_from_matches_already_shown(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        request, _ = matched(url, asha, ravi)
        before = await client.get(f"/api/v1/requests/{request}/matches", headers=asha.headers)
        await block(client, asha, ravi)
        after = await client.get(f"/api/v1/requests/{request}/matches", headers=asha.headers)

    assert len(before.json()["items"]) == 1
    assert after.json()["items"] == []


async def test_who_can_be_blocked(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    settings = make(blocks_per_day=1)
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        mina = await join(client, settings, delivery, "Mina")
        stranger = await join(client, settings, delivery, "Stranger")
        matched(url, asha, ravi)
        matched(url, mina, asha)  # Asha appeared in Mina's matches: that's contact too

        no_contact = await block(client, asha, stranger)
        unknown = await block(client, asha, str(uuid.uuid4()))
        myself = await block(client, asha, asha)
        bad = await client.post("/api/v1/blocks", json={"user_id": "x"}, headers=asha.headers)
        anonymous = await client.post("/api/v1/blocks", json={"user_id": ravi.id})
        first = await block(client, asha, ravi)
        repeat = await block(client, asha, ravi)
        over_limit = await block(client, asha, mina)

    for response in (no_contact, unknown, myself):
        assert response.status_code == 404
        assert error_code(response) == "person_not_found"
    assert bad.status_code == 422
    assert anonymous.status_code == 401
    assert first.status_code == 201
    # Blocking again is harmless and doesn't count towards the daily limit.
    assert repeat.status_code == 201
    assert repeat.json()["created_at"] == first.json()["created_at"]
    assert over_limit.status_code == 429
