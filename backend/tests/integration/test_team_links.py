"""Team invite links through the API, against real PostgreSQL (ADR 0016)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.models import MAX_TEAM_MEMBERS
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_intros import Person, join, matched
from tests.integration.test_teams import TEAMS, members, pair_in_team, team_of

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


async def make_link(client: AsyncClient, owner: Person, team: str) -> Any:
    return await client.post(f"{TEAMS}/{team}/invite-link", headers=owner.headers)


async def preview(client: AsyncClient, person: Person, code: str) -> Any:
    return await client.get(f"{TEAMS}/join/{code}", headers=person.headers)


async def use(client: AsyncClient, person: Person, code: str) -> Any:
    return await client.post(f"{TEAMS}/join/{code}", headers=person.headers)


async def test_a_stranger_with_the_link_joins_at_once(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        before = (await team_of(client, asha, team)).json()
        link = await make_link(client, asha, team)
        code = link.json()["code"]
        owner_view = (await team_of(client, asha, team)).json()
        member_view = (await team_of(client, ravi, team)).json()
        seen = await preview(client, mina, code)
        not_yet = await team_of(client, mina, team)
        joined = await use(client, mina, code)
        again = await use(client, mina, code)

    assert before["invite_link_expires_at"] is None
    assert link.status_code == 201, link.text
    assert len(code) >= 16
    assert datetime.fromisoformat(owner_view["invite_link_expires_at"]) == datetime.fromisoformat(
        link.json()["expires_at"]
    )
    assert member_view["invite_link_expires_at"] is None  # only the owner is told
    assert seen.status_code == 200, seen.text
    assert (seen.json()["id"], seen.json()["member_count"]) == (team, 2)
    assert "members" not in seen.json()  # no names before joining
    assert error_code(not_yet) == "team_not_found"
    assert joined.status_code == 200, joined.text
    assert members(joined.json()) == [asha.id, ravi.id, mina.id]
    assert again.status_code == 200
    assert members(again.json()) == [asha.id, ravi.id, mina.id]
    stored = run_sql(url, "SELECT invite_code_hash FROM teams WHERE id = :t", t=team)[0]
    assert stored["invite_code_hash"] != code  # only a hash is kept
    notices = run_sql(
        url,
        "SELECT user_id FROM notifications WHERE team_id = :t AND kind = 'team_joined' "
        "AND user_id <> :owner",
        t=team,
        owner=asha.id,
    )
    assert [str(row["user_id"]) for row in notices] == [ravi.id]


async def test_a_link_can_be_replaced_turned_off_and_runs_out(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        not_owner = [
            await make_link(client, ravi, team),
            await client.delete(f"{TEAMS}/{team}/invite-link", headers=ravi.headers),
        ]
        first = (await make_link(client, asha, team)).json()["code"]
        second = (await make_link(client, asha, team)).json()["code"]
        old = await preview(client, mina, first)
        new = await preview(client, mina, second)
        run_sql(
            url,
            "UPDATE teams SET invite_expires_at = now() - interval '1 minute' WHERE id = :t",
            t=team,
        )
        expired = await use(client, mina, second)
        expired_view = (await team_of(client, asha, team)).json()
        third = (await make_link(client, asha, team)).json()["code"]
        off = await client.delete(f"{TEAMS}/{team}/invite-link", headers=asha.headers)
        turned_off = await use(client, mina, third)
        fourth = (await make_link(client, asha, team)).json()["code"]
        assert (await client.delete(f"{TEAMS}/{team}", headers=asha.headers)).status_code == 204
        closed = await use(client, mina, fourth)
        unknown = await preview(client, mina, "A" * 22)
        malformed = await preview(client, mina, "short")
        signed_out = await client.get(f"{TEAMS}/join/{fourth}")

    for response in not_owner:
        assert response.status_code == 403
        assert error_code(response) == "not_team_owner"
    assert first != second
    assert new.status_code == 200
    for response in (old, expired, turned_off, closed, unknown):
        assert response.status_code == 404
        assert error_code(response) == "team_link_invalid"
    assert expired_view["invite_link_expires_at"] is None
    assert off.status_code == 204
    assert malformed.status_code == 422
    assert signed_out.status_code == 401


async def test_room_blocks_and_the_daily_limit(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(team_link_tries_per_day=3)
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        kiran = await join(client, settings, delivery, "Kiran")
        code = (await make_link(client, asha, team)).json()["code"]
        # Kiran and Ravi have met through a match; Ravi blocks Kiran.
        matched(url, kiran, ravi)
        blocked = await client.post(
            "/api/v1/blocks", json={"user_id": kiran.id}, headers=ravi.headers
        )
        kept_out = await use(client, kiran, code)
        fillers = [await join(client, settings, delivery, f"Filler{n}") for n in range(4)]
        for person in fillers:
            run_sql(
                url,
                "INSERT INTO team_members (team_id, user_id) VALUES (:t, :u)",
                t=team,
                u=person.id,
            )
        full_preview = await preview(client, mina, code)
        full = await use(client, mina, code)
        third_try = await preview(client, mina, code)
        over = await preview(client, mina, code)

    assert blocked.status_code == 201, blocked.text
    assert error_code(kept_out) == "team_link_invalid"  # never says why
    assert full_preview.json()["member_count"] == MAX_TEAM_MEMBERS
    assert error_code(full) == "team_full"
    assert third_try.status_code == 200
    assert over.status_code == 429
