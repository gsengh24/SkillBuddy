"""A team's goals, skills and progress notes through the API, against real PostgreSQL
(ADR 0016)."""

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
from app.models import MAX_GOALS_PER_SPACE
from app.services.spaces import purge_spaces
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
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


def base(team: str) -> str:
    return f"{TEAMS}/{team}/space"


async def space(client: AsyncClient, person: Person, team: str) -> Any:
    return await client.get(base(team), headers=person.headers)


async def post(client: AsyncClient, person: Person, team: str, path: str, body: Any) -> Any:
    return await client.post(f"{base(team)}/{path}", json=body, headers=person.headers)


async def test_members_build_a_team_space_together(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        empty = (await space(client, asha, team)).json()
        goal = await post(
            client, asha, team, "goals", {"title": "  Ship the demo  ", "due_on": "2026-12-01"}
        )
        goal_id = goal.json()["id"]
        done = await client.patch(
            f"{base(team)}/goals/{goal_id}",
            json={"status": "done", "due_on": None},
            headers=ravi.headers,
        )
        skill = await post(client, ravi, team, "skills", {"name": "Figma"})
        same_skill = await post(client, ravi, team, "skills", {"name": "Figma"})
        same_name_other_person = await post(client, asha, team, "skills", {"name": "Figma"})
        log = await post(
            client, asha, team, "logs", {"note": "Wrote the pitch", "goal_id": goal_id}
        )
        about_skill = await post(
            client, ravi, team, "logs", {"note": "Two tutorials", "skill_id": skill.json()["id"]}
        )
        not_her_skill = await post(
            client, asha, team, "logs", {"note": "Nope", "skill_id": skill.json()["id"]}
        )
        full = (await space(client, ravi, team)).json()
        page = (
            await client.get(f"{base(team)}/logs", params={"limit": 1}, headers=asha.headers)
        ).json()

    assert empty["team_id"] == team
    assert empty["goals"] == empty["skills"] == empty["logs"] == []
    assert (empty["retention_days"], empty["max_goals"]) == (90, MAX_GOALS_PER_SPACE)
    assert goal.status_code == 201, goal.text
    assert (goal.json()["title"], goal.json()["created_by"]) == ("Ship the demo", asha.id)
    assert done.json()["status"] == "done"  # any member changes a shared goal
    assert done.json()["due_on"] is None
    assert skill.json()["owner_id"] == ravi.id
    assert error_code(same_skill) == "skill_exists"
    assert same_name_other_person.status_code == 201
    assert log.json()["author_id"] == asha.id
    assert about_skill.status_code == 201, about_skill.text
    assert error_code(not_her_skill) == "skill_not_found"
    assert [item["title"] for item in full["goals"]] == ["Ship the demo"]
    assert sorted(item["owner_id"] for item in full["skills"]) == sorted([asha.id, ravi.id])
    assert [item["note"] for item in full["logs"]] == ["Two tutorials", "Wrote the pitch"]
    assert [item["note"] for item in page["items"]] == ["Two tutorials"]
    assert page["next_cursor"]


async def test_only_members_and_only_authors(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, migrated_database_url)
        mina = await join(client, settings, delivery, "Mina")
        goal = (await post(client, asha, team, "goals", {"title": "Launch"})).json()
        skill = (await post(client, asha, team, "skills", {"name": "Go"})).json()
        log = (await post(client, asha, team, "logs", {"note": "Started"})).json()
        outsider = [
            await space(client, mina, team),
            await post(client, mina, team, "goals", {"title": "Mine"}),
            await client.get(f"{base(team)}/logs", headers=mina.headers),
            await space(client, asha, str(uuid.uuid4())),
        ]
        signed_out = await client.get(base(team))
        not_yours = [
            await client.delete(f"{base(team)}/skills/{skill['id']}", headers=ravi.headers),
            await client.delete(f"{base(team)}/logs/{log['id']}", headers=ravi.headers),
        ]
        # A teammate can report a team's goal, like one in a pair space.
        reported = await client.post(
            f"/api/v1/space-goals/{goal['id']}/report",
            json={"reason": "spam"},
            headers=ravi.headers,
        )
        deleted = [
            await client.delete(f"{base(team)}/goals/{goal['id']}", headers=ravi.headers),
            await client.delete(f"{base(team)}/skills/{skill['id']}", headers=asha.headers),
            await client.delete(f"{base(team)}/logs/{log['id']}", headers=asha.headers),
        ]
        missing = await client.delete(f"{base(team)}/goals/{goal['id']}", headers=asha.headers)
        kept = (await post(client, ravi, team, "goals", {"title": "Ravi's goal"})).json()
        assert (await out(client, ravi, team, ravi)).status_code == 204
        after_leaving = await space(client, ravi, team)
        still_there = (await space(client, asha, team)).json()

    for response in outsider:
        assert response.status_code == 404
        assert error_code(response) == "team_not_found"
    assert signed_out.status_code == 401
    for response in not_yours:
        assert response.status_code == 403
        assert error_code(response) == "not_yours"
    assert reported.status_code == 201, reported.text
    assert [response.status_code for response in deleted] == [204, 204, 204]
    assert error_code(missing) == "goal_not_found"
    assert error_code(after_leaving) == "team_not_found"
    # What someone wrote stays with the team after they leave.
    assert [item["id"] for item in still_there["goals"]] == [kept["id"]]


async def test_limits_and_validation(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(space_writes_per_day=2)
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        invalid = [
            await post(client, ravi, team, "goals", {"title": " "}),
            await post(client, ravi, team, "skills", {"name": "x" * 61}),
            await post(client, ravi, team, "logs", {"note": "x" * 501}),
        ]
        run_sql(
            url,
            "INSERT INTO space_goals (team_id, author_id, title) "
            "SELECT :t, :u, 'Goal ' || n FROM generate_series(1, :count) AS n",
            t=team,
            u=asha.id,
            count=MAX_GOALS_PER_SPACE,
        )
        too_many = await post(client, ravi, team, "goals", {"title": "One more"})
        first = await post(client, ravi, team, "logs", {"note": "one"})
        second = await post(client, ravi, team, "logs", {"note": "two"})
        third = await post(client, ravi, team, "logs", {"note": "three"})

    assert [response.status_code for response in invalid] == [422, 422, 422]
    assert error_code(too_many) == "too_many_goals"
    assert (first.status_code, second.status_code, third.status_code) == (201, 201, 429)


async def test_notes_are_purged_after_90_days_and_rows_go_with_the_team(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, team = await pair_in_team(client, settings, delivery, url)
        old = (await post(client, asha, team, "logs", {"note": "old"})).json()
        await post(client, asha, team, "logs", {"note": "recent"})
        await post(client, asha, team, "goals", {"title": "kept"})
    run_sql(
        url,
        "UPDATE progress_logs SET created_at = now() - interval '91 days' WHERE id = :i",
        i=old["id"],
    )

    async with session_factory() as db:
        await purge_spaces(db, settings, datetime.now(UTC))

    def notes() -> list[str]:
        rows = run_sql(url, "SELECT note FROM progress_logs WHERE team_id = :t", t=team)
        return [row["note"] for row in rows]

    assert notes() == ["recent"]
    run_sql(url, "DELETE FROM teams WHERE id = :t", t=team)
    assert notes() == []
    assert run_sql(url, "SELECT id FROM space_goals WHERE team_id = :t", t=team) == []
