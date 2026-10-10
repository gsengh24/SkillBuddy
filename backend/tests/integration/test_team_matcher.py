"""The matcher finds teammates, against real PostgreSQL (ADR 0016)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_intros import join
from tests.integration.test_matching import match, matches, person, unit
from tests.integration.test_teams import TEAMS, answer, create, members, pair_in_team, team_of

REASON = "They offer design, which the team is looking for."


@pytest.fixture
def model() -> str:
    """A model version of this test's own, so retrieval sees only this test's people."""
    return f"fixed-test-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def suggest(url: str, request: str, candidate: str) -> str:
    """A match for ``request``, as the matcher job would store it. Returns its id."""
    row = run_sql(
        url,
        "INSERT INTO matches (request_id, candidate_id, rank, score, reason) "
        "VALUES (:r, :c, 1, 0.9, :why) "
        "ON CONFLICT (request_id, candidate_id) DO UPDATE SET reason = :why RETURNING id",
        r=request,
        c=candidate,
        why=REASON,
    )[0]
    return str(row["id"])


async def test_a_team_request_leaves_out_members_and_people_blocked_with_them(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    owner = person(url, model=model, offer=unit((axis + 1, 1.0)))
    teammate = person(url, model=model, offer=unit((axis, 1.0)))
    blocked = person(url, model=model, offer=unit((axis, 1.0)))
    free = person(url, model=model, offer=unit((axis, 0.8), (axis + 2, 0.6)))
    team = run_sql(
        url,
        "INSERT INTO teams (name, purpose, owner_id) VALUES ('Makers', 'project', :o) RETURNING id",
        o=owner,
    )[0]["id"]
    for member in (owner, teammate):
        run_sql(
            url, "INSERT INTO team_members (team_id, user_id) VALUES (:t, :u)", t=team, u=member
        )
    run_sql(
        url, "INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)", a=teammate, b=blocked
    )
    request = run_sql(
        url,
        "INSERT INTO match_requests (user_id, raw_text, requested_intent, team_id, expires_at) "
        "VALUES (:u, 'A React developer for our team.', 'build_together', :t, "
        "now() + interval '30 days') RETURNING id",
        u=owner,
        t=team,
    )[0]["id"]

    assert await match(settings, session_factory, request, unit((axis, 1.0)), model)

    found = [row["candidate_id"] for row in matches(url, request)]
    assert found == [free]


@pytest.mark.usefixtures("teams_on")
async def test_the_owner_asks_for_a_teammate_and_invites_a_match(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        body = {"text": "We need a designer for our hackathon team."}
        asked = await client.post(
            "/api/v1/requests", json=body | {"team_id": team}, headers=asha.headers
        )
        not_owner = await client.post(
            "/api/v1/requests", json=body | {"team_id": team}, headers=ravi.headers
        )
        not_member = await client.post(
            "/api/v1/requests", json=body | {"team_id": team}, headers=mina.headers
        )
        plain = await client.post("/api/v1/requests", json=body, headers=asha.headers)
        for_team = suggest(url, asked.json()["id"], mina.id)
        not_for_team = suggest(url, plain.json()["id"], mina.id)
        invites = f"{TEAMS}/{team}/invites"
        wrong_match = await client.post(
            invites, json={"match_id": not_for_team}, headers=asha.headers
        )
        both = await client.post(
            invites, json={"match_id": for_team, "user_id": mina.id}, headers=asha.headers
        )
        neither = await client.post(invites, json={}, headers=asha.headers)
        invited = await client.post(invites, json={"match_id": for_team}, headers=asha.headers)
        twice = await client.post(invites, json={"match_id": for_team}, headers=asha.headers)
        waiting = (await client.get(f"{TEAMS}/invites", headers=mina.headers)).json()["items"]
        joined = await answer(client, mina, invited.json()["id"], True)
        after = (await team_of(client, mina, team)).json()
        other_team = (await create(client, asha, "Second team")).json()["id"]
        other_teams_match = await client.post(
            f"{TEAMS}/{other_team}/invites", json={"match_id": for_team}, headers=asha.headers
        )

    assert asked.status_code == 202, asked.text
    assert asked.json()["team_id"] == team
    assert error_code(not_owner) == "not_team_owner"
    assert error_code(not_member) == "team_not_found"
    assert plain.json()["team_id"] is None
    assert error_code(wrong_match) == "cannot_invite"
    assert [both.status_code, neither.status_code] == [422, 422]
    assert invited.status_code == 201, invited.text
    # No connection is needed, and the person is told why they were suggested.
    assert (invited.json()["kind"], invited.json()["note"]) == ("suggested", REASON)
    assert error_code(twice) == "team_invite_exists"
    assert [(item["team"]["id"], item["kind"], item["note"]) for item in waiting] == [
        (team, "suggested", REASON)
    ]
    assert joined.status_code == 200, joined.text
    assert members(after) == [asha.id, ravi.id, mina.id]
    assert error_code(other_teams_match) == "cannot_invite"


async def test_a_team_request_needs_the_teams_switch(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        refused = await client.post(
            "/api/v1/requests",
            json={"text": "We need a designer for our team.", "team_id": str(uuid.uuid4())},
            headers=asha.headers,
        )

    assert refused.status_code == 503
    assert error_code(refused) == "feature_off"
