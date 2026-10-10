"""Teams through the API, against real PostgreSQL (ADR 0016)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import MAX_TEAM_MEMBERS, MAX_TEAMS_OWNED, TEAM_NAME_MAX_LENGTH
from app.services import app_settings
from app.services.teams import purge_teams
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_intros import Person, join, matched, send

TEAMS = "/api/v1/teams"


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


@pytest.fixture
def teams_on(migrated_database_url: str) -> Iterator[None]:
    """Teams are off by default: switch them on for one test, then back."""
    run_sql(
        migrated_database_url,
        "INSERT INTO app_settings (key, value) VALUES ('feature:teams', 'true'::jsonb) "
        "ON CONFLICT (key) DO UPDATE SET value = 'true'::jsonb",
    )
    app_settings.cache.invalidate()
    yield
    run_sql(migrated_database_url, "DELETE FROM app_settings WHERE key = 'feature:teams'")
    app_settings.cache.invalidate()


async def link(client: AsyncClient, url: str, sender: Person, recipient: Person) -> None:
    """Connect two people: an intro from ``sender`` that ``recipient`` accepts."""
    _, match = matched(url, sender, recipient)
    intro = (await send(client, sender, match)).json()
    answer = await client.post(
        f"/api/v1/intros/{intro['id']}/respond", json={"accept": True}, headers=recipient.headers
    )
    assert answer.status_code == 200, answer.text


async def create(client: AsyncClient, owner: Person, name: str = "Hack night") -> Any:
    return await client.post(
        TEAMS,
        json={"name": name, "purpose": "hackathon", "description": "48 hours, one app."},
        headers=owner.headers,
    )


async def invite(client: AsyncClient, owner: Person, team: str, other: Person) -> Any:
    return await client.post(
        f"{TEAMS}/{team}/invites", json={"user_id": other.id}, headers=owner.headers
    )


async def answer(client: AsyncClient, person: Person, invite_id: str, accept: bool) -> Any:
    return await client.post(
        f"{TEAMS}/invites/{invite_id}/respond", json={"accept": accept}, headers=person.headers
    )


async def team_of(client: AsyncClient, person: Person, team: str) -> Any:
    return await client.get(f"{TEAMS}/{team}", headers=person.headers)


async def out(client: AsyncClient, person: Person, team: str, member: Person) -> Any:
    return await client.delete(f"{TEAMS}/{team}/members/{member.id}", headers=person.headers)


async def pair_in_team(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, url: str
) -> tuple[Person, Person, str]:
    """An owner and one member who accepted an invite. Returns (owner, member, team id)."""
    asha = await join(client, settings, delivery, "Asha")
    ravi = await join(client, settings, delivery, "Ravi")
    await link(client, url, asha, ravi)
    team = (await create(client, asha)).json()["id"]
    sent = await invite(client, asha, team, ravi)
    assert sent.status_code == 201, sent.text
    joined = await answer(client, ravi, sent.json()["id"], True)
    assert joined.status_code == 200, joined.text
    return asha, ravi, team


def members(body: dict[str, Any]) -> list[str]:
    return [member["user_id"] for member in body["members"]]


# --- the switch ---------------------------------------------------------------------------


async def test_teams_are_off_until_switched_on(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    app_settings.cache.invalidate()
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        listing = await client.get(TEAMS, headers=asha.headers)
        made = await create(client, asha)
        public = (await client.get("/api/v1/features")).json()["features"]

    for response in (listing, made):
        assert response.status_code == 503
        assert error_code(response) == "feature_off"
    assert public["teams"] is False


# --- making a team and joining by invite --------------------------------------------------


@pytest.mark.usefixtures("teams_on")
async def test_an_owner_invites_a_connection_who_joins(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        await link(client, url, asha, ravi)
        made = await create(client, asha, "  Hack night  ")
        team = made.json()["id"]
        sent = await invite(client, asha, team, ravi)
        owner_view = (await team_of(client, asha, team)).json()
        outsider_view = await team_of(client, ravi, team)
        waiting = (await client.get(f"{TEAMS}/invites", headers=ravi.headers)).json()
        joined = await answer(client, ravi, sent.json()["id"], True)
        again = await answer(client, ravi, sent.json()["id"], True)
        member_view = (await team_of(client, ravi, team)).json()
        mine = (await client.get(TEAMS, headers=ravi.headers)).json()
        after = (await client.get(f"{TEAMS}/invites", headers=ravi.headers)).json()

    assert made.status_code == 201, made.text
    assert made.json()["name"] == "Hack night"
    assert made.json()["owner_id"] == asha.id
    assert made.json()["max_members"] == MAX_TEAM_MEMBERS
    assert members(made.json()) == [asha.id]
    assert sent.status_code == 201, sent.text
    assert (sent.json()["kind"], sent.json()["status"]) == ("invite", "pending")
    assert [(item["user_id"], item["display_name"]) for item in owner_view["invites"]] == [
        (ravi.id, "Ravi")
    ]
    assert error_code(outsider_view) == "team_not_found"  # invited is not yet a member
    assert [item["team"]["id"] for item in waiting["items"]] == [team]
    assert joined.status_code == 200, joined.text
    assert joined.json()["status"] == "accepted"
    assert joined.json()["team"]["member_count"] == 2
    assert error_code(again) == "team_invite_not_pending"
    assert members(member_view) == [asha.id, ravi.id]
    assert [member["display_name"] for member in member_view["members"]] == ["Asha", "Ravi"]
    assert member_view["invites"] == []  # only the owner sees invites
    assert [(item["id"], item["member_count"]) for item in mine["items"]] == [(team, 2)]
    assert (mine["max_teams"], mine["max_owned"]) == (5, MAX_TEAMS_OWNED)
    assert after["items"] == []
    notices = run_sql(
        url,
        "SELECT user_id, kind FROM notifications WHERE team_id = :t ORDER BY created_at",
        t=team,
    )
    assert [(str(row["user_id"]), row["kind"]) for row in notices] == [
        (ravi.id, "team_invite"),
        (asha.id, "team_joined"),
    ]


@pytest.mark.usefixtures("teams_on")
async def test_who_can_be_invited(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        stranger = await invite(client, asha, team, mina)
        herself = await invite(client, asha, team, asha)
        member = await invite(client, asha, team, ravi)
        await link(client, url, ravi, mina)
        not_owner = await invite(client, ravi, team, mina)
        await link(client, url, asha, mina)
        first = await invite(client, asha, team, mina)
        twice = await invite(client, asha, team, mina)
        unknown = await client.post(
            f"{TEAMS}/{uuid.uuid4()}/invites", json={"user_id": mina.id}, headers=asha.headers
        )

    assert error_code(stranger) == "cannot_invite"
    assert error_code(herself) == "already_member"
    assert error_code(member) == "already_member"
    assert not_owner.status_code == 403
    assert error_code(not_owner) == "not_team_owner"
    assert first.status_code == 201
    assert error_code(twice) == "team_invite_exists"
    assert error_code(unknown) == "team_not_found"


@pytest.mark.usefixtures("teams_on")
async def test_a_decline_is_not_shown_to_the_owner(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        await link(client, url, asha, ravi)
        team = (await create(client, asha)).json()["id"]
        sent = (await invite(client, asha, team, ravi)).json()
        someone_else = await answer(client, asha, sent["id"], False)
        declined = await answer(client, ravi, sent["id"], False)
        owner_view = (await team_of(client, asha, team)).json()
        waiting = (await client.get(f"{TEAMS}/invites", headers=ravi.headers)).json()
        again = await invite(client, asha, team, ravi)
        taken_back = await client.delete(f"{TEAMS}/invites/{sent['id']}", headers=asha.headers)
        by_invitee = await client.delete(f"{TEAMS}/invites/{sent['id']}", headers=ravi.headers)
        after = (await team_of(client, asha, team)).json()
        fresh = await invite(client, asha, team, ravi)

    assert error_code(someone_else) == "team_invite_not_found"
    assert declined.json()["status"] == "declined"
    assert [item["status"] for item in owner_view["invites"]] == ["pending"]
    assert members(owner_view) == [asha.id]
    assert waiting["items"] == []
    assert error_code(again) == "team_invite_exists"
    assert taken_back.status_code == 204
    assert error_code(by_invitee) == "team_invite_not_found"
    assert after["invites"] == []
    assert fresh.status_code == 201


# --- leaving, removing, closing -----------------------------------------------------------


@pytest.mark.usefixtures("teams_on")
async def test_leaving_passes_the_team_on_and_the_last_one_out_closes_it(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        left = await out(client, asha, team, asha)
        gone = await team_of(client, asha, team)
        inherited = (await team_of(client, ravi, team)).json()
        last = await out(client, ravi, team, ravi)
        closed = await team_of(client, ravi, team)

    assert left.status_code == 204
    assert error_code(gone) == "team_not_found"
    assert inherited["owner_id"] == ravi.id
    assert members(inherited) == [ravi.id]
    assert last.status_code == 204
    assert error_code(closed) == "team_not_found"
    row = run_sql(url, "SELECT closed_at FROM teams WHERE id = :t", t=team)[0]
    assert row["closed_at"] is not None


@pytest.mark.usefixtures("teams_on")
async def test_only_the_owner_changes_removes_and_closes(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        await link(client, url, asha, mina)
        pending = (await invite(client, asha, team, mina)).json()
        refused = [
            await client.patch(f"{TEAMS}/{team}", json={"name": "Mine now"}, headers=ravi.headers),
            await out(client, ravi, team, asha),
            await client.delete(f"{TEAMS}/{team}", headers=ravi.headers),
        ]
        renamed = await client.patch(
            f"{TEAMS}/{team}",
            json={"name": "Build week", "purpose": "project", "description": ""},
            headers=asha.headers,
        )
        nobody = await out(client, asha, team, mina)
        removed = await out(client, asha, team, ravi)
        removed_view = await team_of(client, ravi, team)
        closed = await client.delete(f"{TEAMS}/{team}", headers=asha.headers)
        after_close = await team_of(client, asha, team)
        late = await answer(client, mina, pending["id"], True)
        listing = (await client.get(TEAMS, headers=asha.headers)).json()

    for response in refused:
        assert response.status_code == 403
        assert error_code(response) == "not_team_owner"
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert (body["name"], body["purpose"], body["description"]) == ("Build week", "project", "")
    assert error_code(nobody) == "team_member_not_found"
    assert removed.status_code == 204
    assert error_code(removed_view) == "team_not_found"
    assert closed.status_code == 204
    assert error_code(after_close) == "team_not_found"
    assert error_code(late) == "team_invite_not_pending"
    assert listing["items"] == []


# --- blocks -------------------------------------------------------------------------------


async def block(client: AsyncClient, person: Person, other: Person) -> Any:
    return await client.post("/api/v1/blocks", json={"user_id": other.id}, headers=person.headers)


@pytest.mark.usefixtures("teams_on")
async def test_a_member_who_blocks_a_teammate_leaves(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        blocked = await block(client, ravi, asha)
        blocker_view = await team_of(client, ravi, team)
        owner_view = (await team_of(client, asha, team)).json()

    assert blocked.status_code == 201, blocked.text
    assert error_code(blocker_view) == "team_not_found"
    assert members(owner_view) == [asha.id]


@pytest.mark.usefixtures("teams_on")
async def test_an_owner_who_blocks_a_member_removes_them(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        blocked = await block(client, asha, ravi)
        removed_view = await team_of(client, ravi, team)
        owner_view = (await team_of(client, asha, team)).json()

    assert blocked.status_code == 201, blocked.text
    assert error_code(removed_view) == "team_not_found"
    assert members(owner_view) == [asha.id]


@pytest.mark.usefixtures("teams_on")
async def test_a_block_with_any_member_keeps_someone_out(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        kiran = await join(client, settings, delivery, "Kiran")
        await link(client, url, asha, mina)
        await link(client, url, asha, kiran)
        open_invite = (await invite(client, asha, team, mina)).json()
        # Mina and Ravi have met through a match, so either can block the other.
        matched(url, mina, ravi)
        matched(url, kiran, ravi)
        assert (await block(client, mina, ravi)).status_code == 201
        assert (await block(client, ravi, kiran)).status_code == 201
        ended = await answer(client, mina, open_invite["id"], True)
        refused = await invite(client, asha, team, mina)
        also_refused = await invite(client, asha, team, kiran)
        view = (await team_of(client, asha, team)).json()

    assert error_code(ended) == "team_invite_not_pending"  # the block withdrew it
    assert error_code(refused) == "cannot_invite"
    assert error_code(also_refused) == "cannot_invite"
    assert members(view) == [asha.id, ravi.id]
    assert view["invites"] == []


# --- limits and validation ----------------------------------------------------------------


@pytest.mark.usefixtures("teams_on")
async def test_limits_and_validation(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(team_invites_per_day=1)
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        signed_out = await client.get(TEAMS)
        bad = [
            await client.post(TEAMS, json=body, headers=asha.headers)
            for body in (
                {"name": " ", "purpose": "project"},
                {"name": "x" * (TEAM_NAME_MAX_LENGTH + 1), "purpose": "project"},
                {"name": "Team", "purpose": "party"},
                {"name": "Team", "purpose": "project", "description": "x" * 301},
                {"name": "Team", "purpose": "project", "owner_id": asha.id},
            )
        ]
        owned = [await create(client, asha, f"Team {n}") for n in range(MAX_TEAMS_OWNED)]
        one_more = await create(client, asha, "One too many")
        team = owned[0].json()["id"]
        # Fill the team to the limit without five more intros.
        others = [await join(client, settings, delivery, f"Member{n}") for n in range(6)]
        for person in others[: MAX_TEAM_MEMBERS - 1]:
            run_sql(
                url,
                "INSERT INTO team_members (team_id, user_id) VALUES (:t, :u)",
                t=team,
                u=person.id,
            )
        late = others[-1]
        await link(client, url, asha, late)
        full = await invite(client, asha, team, late)
        second = owned[1].json()["id"]
        first_invite = await invite(client, asha, second, late)
        ravi = await join(client, settings, delivery, "Ravi")
        await link(client, url, asha, ravi)
        over_daily_limit = await invite(client, asha, second, ravi)

    assert signed_out.status_code == 401
    assert [response.status_code for response in bad] == [422] * 5
    assert [response.status_code for response in owned] == [201] * MAX_TEAMS_OWNED
    assert error_code(one_more) == "too_many_teams_owned"
    assert error_code(full) == "team_full"
    assert first_invite.status_code == 201, first_invite.text
    assert over_daily_limit.status_code == 429


# --- retention ----------------------------------------------------------------------------


@pytest.mark.usefixtures("teams_on")
async def test_the_daily_purge(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, orphaned = await pair_in_team(client, settings, delivery, url)
        long_closed = (await create(client, asha, "Long closed")).json()["id"]
        just_closed = (await create(client, asha, "Just closed")).json()["id"]
        mina = await join(client, settings, delivery, "Mina")
        await link(client, url, asha, mina)
        stale = (await invite(client, asha, orphaned, mina)).json()["id"]
    run_sql(url, "UPDATE teams SET owner_id = NULL WHERE id = :t", t=orphaned)
    run_sql(
        url,
        "DELETE FROM team_members WHERE team_id = :t AND user_id = :u",
        t=orphaned,
        u=asha.id,
    )
    run_sql(
        url, "UPDATE teams SET closed_at = now() - interval '91 days' WHERE id = :t", t=long_closed
    )
    run_sql(
        url, "UPDATE teams SET closed_at = now() - interval '10 days' WHERE id = :t", t=just_closed
    )
    run_sql(
        url,
        "UPDATE team_invites SET expires_at = now() - interval '1 day' WHERE id = :i",
        i=stale,
    )

    async with session_factory() as db:
        first = await purge_teams(db, settings, datetime.now(UTC))
    run_sql(
        url,
        "UPDATE team_invites SET expires_at = now() - interval '91 days' WHERE id = :i",
        i=stale,
    )
    async with session_factory() as db:
        second = await purge_teams(db, settings, datetime.now(UTC))

    def owner(team: str) -> list[str | None]:
        rows = run_sql(url, "SELECT owner_id FROM teams WHERE id = :t", t=team)
        return [str(row["owner_id"]) if row["owner_id"] else None for row in rows]

    assert owner(orphaned) == [ravi.id]  # the longest-standing member took over
    assert owner(long_closed) == []
    assert owner(just_closed) == [asha.id]
    assert first["teams_adopted"] >= 1
    assert first["teams_deleted"] >= 1
    assert first["invites_expired"] >= 1
    assert second["invites_deleted"] >= 1
    assert run_sql(url, "SELECT id FROM team_invites WHERE id = :i", i=stale) == []
