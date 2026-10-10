"""Listed teams and asking to join, through the API, against real PostgreSQL (ADR 0016)."""

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
from tests.integration.test_intros import Person, join, matched
from tests.integration.test_teams import TEAMS, answer, create, members, pair_in_team, team_of

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


async def list_it(client: AsyncClient, owner: Person, team: str, looking_for: str = "") -> Any:
    return await client.patch(
        f"{TEAMS}/{team}",
        json={"listed": True, "looking_for": looking_for},
        headers=owner.headers,
    )


async def listed_ids(client: AsyncClient, person: Person, **params: Any) -> list[str]:
    """Ids of every listed team ``person`` can see (the test database is shared)."""
    ids: list[str] = []
    cursor: str | None = None
    while True:
        query = params | ({"cursor": cursor} if cursor else {})
        page = (await client.get(f"{TEAMS}/listed", params=query, headers=person.headers)).json()
        ids += [item["id"] for item in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            return ids


async def ask(client: AsyncClient, person: Person, team: str, note: str = "Can I join?") -> Any:
    return await client.post(
        f"{TEAMS}/{team}/requests", json={"note": note}, headers=person.headers
    )


async def my_requests(client: AsyncClient, person: Person) -> list[dict[str, Any]]:
    body = (await client.get(f"{TEAMS}/requests", headers=person.headers)).json()
    return list(body["items"])


async def test_a_listed_team_is_found_and_the_owner_accepts_a_request(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        hidden_before = await listed_ids(client, mina)
        unlisted_ask = await ask(client, mina, team)
        not_owner = await list_it(client, ravi, team)
        listed = await list_it(client, asha, team, "  A designer who likes maps  ")
        found = await listed_ids(client, mina)
        by_purpose = await listed_ids(client, mina, purpose="hackathon")
        other_purpose = await listed_ids(client, mina, purpose="study")
        own = await listed_ids(client, ravi)
        page = (
            await client.get(f"{TEAMS}/listed", params={"limit": 1}, headers=mina.headers)
        ).json()
        asked = await ask(client, mina, team, "  I draw maps.  ")
        twice = await ask(client, mina, team)
        waiting = await my_requests(client, mina)
        owner_view = (await team_of(client, asha, team)).json()
        by_member = await answer(client, ravi, asked.json()["id"], True)
        by_asker = await answer(client, mina, asked.json()["id"], True)
        accepted = await answer(client, asha, asked.json()["id"], True)
        after = (await team_of(client, mina, team)).json()
        done = await my_requests(client, mina)

    assert team not in hidden_before
    assert error_code(unlisted_ask) == "team_not_found"
    assert error_code(not_owner) == "not_team_owner"
    assert listed.status_code == 200, listed.text
    assert (listed.json()["listed"], listed.json()["looking_for"]) == (
        True,
        "A designer who likes maps",
    )
    assert team in found
    assert team in by_purpose
    assert team not in other_purpose
    assert team not in own  # your own teams are not offered to you
    assert len(page["items"]) == 1
    assert "members" not in page["items"][0]  # no names before joining
    assert asked.status_code == 201, asked.text
    assert (asked.json()["kind"], asked.json()["note"]) == ("request", "I draw maps.")
    assert error_code(twice) == "team_invite_exists"
    assert [item["team"]["id"] for item in waiting] == [team]
    assert [
        (item["kind"], item["user_id"], item["display_name"], item["note"])
        for item in owner_view["invites"]
    ] == [("request", mina.id, "Mina", "I draw maps.")]
    assert error_code(by_member) == "team_invite_not_found"
    assert error_code(by_asker) == "team_invite_not_found"  # only the owner answers a request
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert members(after) == [asha.id, ravi.id, mina.id]
    assert done == []
    notices = run_sql(
        url,
        "SELECT user_id, kind FROM notifications WHERE team_id = :t "
        "AND kind IN ('team_request', 'team_request_accepted') ORDER BY created_at",
        t=team,
    )
    assert [(str(row["user_id"]), row["kind"]) for row in notices] == [
        (asha.id, "team_request"),
        (mina.id, "team_request_accepted"),
    ]
    joined = run_sql(
        url,
        "SELECT user_id FROM notifications WHERE team_id = :t AND kind = 'team_joined' "
        "AND user_id = :u",
        t=team,
        u=ravi.id,
    )
    assert len(joined) == 1  # the other member is told; the owner who said yes is not


async def test_a_decline_is_hidden_from_the_asker_and_a_request_can_be_taken_back(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        kiran = await join(client, settings, delivery, "Kiran")
        await list_it(client, asha, team)
        first = (await ask(client, mina, team)).json()
        declined = await answer(client, asha, first["id"], False)
        asker_view = await my_requests(client, mina)
        owner_view = (await team_of(client, asha, team)).json()
        again = await ask(client, mina, team)
        outsider = await team_of(client, mina, team)
        second = (await ask(client, kiran, team)).json()
        not_his = await client.delete(f"{TEAMS}/invites/{second['id']}", headers=mina.headers)
        not_owners = await client.delete(f"{TEAMS}/invites/{second['id']}", headers=asha.headers)
        taken_back = await client.delete(f"{TEAMS}/invites/{second['id']}", headers=kiran.headers)
        late = await answer(client, asha, second["id"], True)
        kiran_view = await my_requests(client, kiran)

    assert declined.status_code == 200, declined.text
    assert [item["status"] for item in asker_view] == ["pending"]  # looks pending to the asker
    assert owner_view["invites"] == []  # the owner has dealt with it
    assert error_code(again) == "team_invite_exists"
    assert error_code(outsider) == "team_not_found"
    assert error_code(not_his) == "team_invite_not_found"
    assert (
        error_code(not_owners) == "team_invite_not_found"
    )  # a request is the asker's to take back
    assert taken_back.status_code == 204
    assert error_code(late) == "team_invite_not_pending"
    assert kiran_view == []


async def test_blocks_limits_and_validation(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(team_requests_per_day=1)
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        other = (await create(client, asha, "Second team")).json()["id"]
        await list_it(client, asha, team)
        await list_it(client, asha, other)
        mina = await join(client, settings, delivery, "Mina")
        kiran = await join(client, settings, delivery, "Kiran")
        # Kiran and Ravi have met through a match; Ravi blocks Kiran.
        matched(url, kiran, ravi)
        blocked = await client.post(
            "/api/v1/blocks", json={"user_id": kiran.id}, headers=ravi.headers
        )
        kiran_sees = await listed_ids(client, kiran)
        kiran_asks = await ask(client, kiran, team)
        invalid = [
            await ask(client, mina, team, "x" * 301),
            await list_it(client, asha, team, "x" * 201),
            await client.get(f"{TEAMS}/listed", params={"purpose": "party"}, headers=mina.headers),
            await client.get(f"{TEAMS}/listed", params={"cursor": "nope"}, headers=mina.headers),
        ]
        signed_out = await client.get(f"{TEAMS}/listed")
        member_asks = await ask(client, ravi, team)
        missing = await ask(client, mina, str(uuid.uuid4()))
        first = await ask(client, mina, team)
        over = await ask(client, mina, other)
        unlisted = await client.patch(
            f"{TEAMS}/{team}", json={"listed": False}, headers=asha.headers
        )
        mina_sees = await listed_ids(client, mina)

    assert blocked.status_code == 201, blocked.text
    assert team not in kiran_sees  # a team with someone who blocked you is not shown
    assert other in kiran_sees
    assert error_code(kiran_asks) == "team_not_found"
    assert [response.status_code for response in invalid] == [422, 422, 422, 400]
    assert signed_out.status_code == 401
    assert error_code(member_asks) == "already_member"
    assert error_code(missing) == "team_not_found"
    assert first.status_code == 201, first.text
    assert over.status_code == 429
    assert unlisted.json()["listed"] is False
    assert team not in mina_sees
    assert other in mina_sees
