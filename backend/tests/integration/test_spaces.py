"""Pair spaces through the API, against real PostgreSQL (ADR 0013)."""

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
from app.models import GOAL_TITLE_MAX_LENGTH, MAX_GOALS_PER_SPACE
from app.services import blocks
from app.services.spaces import purge_spaces
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_chat import connect
from tests.integration.test_intros import Person, join


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


def base(connection: str) -> str:
    return f"/api/v1/connections/{connection}/space"


async def space(client: AsyncClient, person: Person, connection: str) -> Any:
    return await client.get(base(connection), headers=person.headers)


async def post(client: AsyncClient, person: Person, connection: str, path: str, body: Any) -> Any:
    return await client.post(f"{base(connection)}/{path}", json=body, headers=person.headers)


# --- using a space ------------------------------------------------------------------------


async def test_both_people_build_a_space_together(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        empty = (await space(client, asha, connection)).json()
        goal = await post(
            client, asha, connection, "goals", {"title": "  Ship the MVP  ", "due_on": "2026-12-01"}
        )
        goal_id = goal.json()["id"]
        done = await client.patch(
            f"{base(connection)}/goals/{goal_id}",
            json={"status": "done", "due_on": None},
            headers=ravi.headers,
        )
        renamed = await client.patch(
            f"{base(connection)}/goals/{goal_id}",
            json={"title": "Ship the beta", "status": "open"},
            headers=ravi.headers,
        )
        skill = await post(client, ravi, connection, "skills", {"name": "Figma"})
        log = await post(
            client, asha, connection, "logs", {"note": "Wrote the sign-up page", "goal_id": goal_id}
        )
        about_skill = await post(
            client,
            ravi,
            connection,
            "logs",
            {"note": "Two tutorials", "skill_id": skill.json()["id"]},
        )
        full = (await space(client, ravi, connection)).json()

    assert empty["goals"] == empty["skills"] == empty["logs"] == []
    assert empty["retention_days"] == 90
    assert empty["max_goals"] == MAX_GOALS_PER_SPACE
    assert goal.status_code == 201, goal.text
    assert goal.json()["title"] == "Ship the MVP"
    assert goal.json()["created_by"] == asha.id
    assert done.json()["status"] == "done"
    assert done.json()["done_at"] is not None
    assert done.json()["due_on"] is None  # null clears the date
    assert renamed.json()["title"] == "Ship the beta"
    assert renamed.json()["done_at"] is None
    assert skill.json()["owner_id"] == ravi.id
    assert log.json()["author_id"] == asha.id
    assert log.json()["goal_id"] == goal_id
    assert about_skill.status_code == 201
    assert [item["note"] for item in full["logs"]] == ["Two tutorials", "Wrote the sign-up page"]
    assert [item["name"] for item in full["skills"]] == ["Figma"]


async def test_only_owners_remove_skills_and_notes(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        skill = (await post(client, ravi, connection, "skills", {"name": "Figma"})).json()
        log = (await post(client, ravi, connection, "logs", {"note": "Progress"})).json()
        goal = (await post(client, ravi, connection, "goals", {"title": "Launch"})).json()
        not_my_skill = await client.delete(
            f"{base(connection)}/skills/{skill['id']}", headers=asha.headers
        )
        not_my_note = await client.delete(
            f"{base(connection)}/logs/{log['id']}", headers=asha.headers
        )
        their_skill_in_my_note = await post(
            client, asha, connection, "logs", {"note": "x", "skill_id": skill["id"]}
        )
        both_links = await post(
            client,
            ravi,
            connection,
            "logs",
            {"note": "x", "skill_id": skill["id"], "goal_id": goal["id"]},
        )
        shared_goal = await client.delete(
            f"{base(connection)}/goals/{goal['id']}", headers=asha.headers
        )
        own_note = await client.delete(f"{base(connection)}/logs/{log['id']}", headers=ravi.headers)
        own_skill = await client.delete(
            f"{base(connection)}/skills/{skill['id']}", headers=ravi.headers
        )
        missing = await client.delete(
            f"{base(connection)}/goals/{uuid.uuid4()}", headers=ravi.headers
        )

    for response in (not_my_skill, not_my_note):
        assert response.status_code == 403
        assert error_code(response) == "not_yours"
    assert their_skill_in_my_note.status_code == 404
    assert error_code(their_skill_in_my_note) == "skill_not_found"
    assert both_links.status_code == 422
    assert shared_goal.status_code == 204  # goals are shared: either person deletes
    assert own_note.status_code == 204
    assert own_skill.status_code == 204
    assert missing.status_code == 404
    assert error_code(missing) == "goal_not_found"


# --- who can see it -----------------------------------------------------------------------


async def test_only_the_two_people_see_a_space(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        _, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        mallory = await join(client, settings, delivery, "Mallory")
        outsider = await space(client, mallory, connection)
        outsider_write = await post(client, mallory, connection, "goals", {"title": "x"})
        unknown = await space(client, ravi, str(uuid.uuid4()))
        anonymous = await client.get(base(connection))

    for response in (outsider, outsider_write, unknown):
        assert response.status_code == 404
        assert error_code(response) == "space_not_found"
    assert anonymous.status_code == 401


async def test_a_block_closes_the_space_for_both(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        await post(client, asha, connection, "goals", {"title": "Launch"})
        blocked = await client.post(
            "/api/v1/blocks", json={"user_id": asha.id}, headers=ravi.headers
        )
        after = [
            await space(client, asha, connection),
            await space(client, ravi, connection),
            await post(client, asha, connection, "goals", {"title": "Again"}),
        ]

    assert blocked.status_code == 201
    for response in after:
        assert response.status_code == 404
        assert error_code(response) == "space_not_found"


async def test_the_block_hook_alone_closes_it(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)

        async def everyone(_db: Any, _user_id: uuid.UUID) -> frozenset[uuid.UUID]:
            return frozenset({uuid.UUID(asha.id), uuid.UUID(ravi.id)})

        monkeypatch.setattr(blocks, "blocked_with", everyone)
        response = await space(client, asha, connection)

    assert response.status_code == 404


# --- limits and validation ----------------------------------------------------------------


async def test_limits_and_validation(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    settings = make(space_writes_per_day=3)
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        too_long = await post(
            client, asha, connection, "goals", {"title": "x" * (GOAL_TITLE_MAX_LENGTH + 1)}
        )
        bad_date = await post(client, asha, connection, "goals", {"title": "x", "due_on": "soon"})
        blank_note = await post(client, asha, connection, "logs", {"note": "   "})
        first = await post(client, asha, connection, "skills", {"name": "Python"})
        duplicate = await post(client, asha, connection, "skills", {"name": "Python"})
        second = await post(client, asha, connection, "logs", {"note": "One"})
        over_limit = await post(client, asha, connection, "logs", {"note": "Two"})

        for number in range(MAX_GOALS_PER_SPACE):
            run_sql(
                url,
                "INSERT INTO space_goals (connection_id, from_a, title) VALUES (:c, true, :t)",
                c=connection,
                t=f"goal {number}",
            )
        full = await post(client, ravi, connection, "goals", {"title": "One more"})

    for response in (too_long, bad_date, blank_note):
        assert response.status_code == 422
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "skill_exists"
    assert second.status_code == 201
    assert over_limit.status_code == 429
    assert full.status_code == 409
    assert error_code(full) == "too_many_goals"


async def test_logs_page_back_with_a_cursor(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, _, connection = await connect(client, settings, delivery, migrated_database_url)
        for number in range(3):
            await post(client, asha, connection, "logs", {"note": f"note {number}"})
        first = (
            await client.get(f"{base(connection)}/logs", params={"limit": 2}, headers=asha.headers)
        ).json()
        rest = (
            await client.get(
                f"{base(connection)}/logs",
                params={"limit": 2, "before": first["next_cursor"]},
                headers=asha.headers,
            )
        ).json()
        bad = await client.get(
            f"{base(connection)}/logs", params={"before": "nope"}, headers=asha.headers
        )

    assert [item["note"] for item in first["items"]] == ["note 2", "note 1"]
    assert [item["note"] for item in rest["items"]] == ["note 0"]
    assert rest["next_cursor"] is None
    assert bad.status_code == 400


# --- retention ----------------------------------------------------------------------------


async def test_old_notes_and_long_ended_spaces_are_purged(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, _, open_space = await connect(client, settings, delivery, url)
        old = (await post(client, asha, open_space, "logs", {"note": "old"})).json()
        await post(client, asha, open_space, "logs", {"note": "recent"})
        await post(client, asha, open_space, "goals", {"title": "kept"})
        mina, _, ended_long_ago = await connect(client, settings, delivery, url)
        await post(client, mina, ended_long_ago, "goals", {"title": "gone"})
        await post(client, mina, ended_long_ago, "logs", {"note": "gone too"})
        kiran, _, ended_recently = await connect(client, settings, delivery, url)
        await post(client, kiran, ended_recently, "goals", {"title": "still here"})
    run_sql(
        url,
        "UPDATE progress_logs SET created_at = now() - interval '91 days' WHERE id = :i",
        i=old["id"],
    )
    run_sql(
        url,
        "UPDATE connections SET ended_at = now() - interval '91 days' WHERE id = :c",
        c=ended_long_ago,
    )
    run_sql(
        url,
        "UPDATE connections SET ended_at = now() - interval '10 days' WHERE id = :c",
        c=ended_recently,
    )

    async with session_factory() as db:
        deleted = await purge_spaces(db, settings, datetime.now(UTC))

    def notes(connection: str) -> list[str]:
        rows = run_sql(url, "SELECT note FROM progress_logs WHERE connection_id = :c", c=connection)
        return sorted(row["note"] for row in rows)

    def goals(connection: str) -> list[str]:
        rows = run_sql(url, "SELECT title FROM space_goals WHERE connection_id = :c", c=connection)
        return [row["title"] for row in rows]

    assert deleted["progress_logs"] >= 2
    assert notes(open_space) == ["recent"]
    assert goals(open_space) == ["kept"]
    assert notes(ended_long_ago) == []
    assert goals(ended_long_ago) == []
    assert goals(ended_recently) == ["still here"]  # hidden, but not deleted for 90 days
