"""Reporting and moderating teams, against real PostgreSQL (ADR 0016).

Feature and rule switches are global, so these tests use their own fresh database and clear
the settings cache before and after each test.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from httpx import AsyncClient

from app.core.config import Settings
from app.services import app_settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import Person as Admin
from tests.integration.test_admin_portal import email, two_step
from tests.integration.test_admin_portal import join as join_admin
from tests.integration.test_auth_codes import error_code
from tests.integration.test_intros import Person, join
from tests.integration.test_teams import TEAMS, pair_in_team, team_of

ADMIN = "/api/v1/admin"
REASON = "Checked against the community rules."
OWNER = email("owner")


@pytest.fixture
def fresh_url() -> Iterator[str]:
    """A database of this test's own, with teams switched on."""
    app_settings.cache.invalidate()
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        run_sql(
            url, "INSERT INTO app_settings (key, value) VALUES ('feature:teams', 'true'::jsonb)"
        )
        yield url
    app_settings.cache.invalidate()


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


async def report(client: AsyncClient, person: Person, path: str, reason: str = "spam") -> Any:
    return await client.post(
        f"/api/v1/{path}/report", json={"reason": reason}, headers=person.headers
    )


async def owner_of(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Admin:
    owner = await join_admin(client, settings, delivery, OWNER)
    await two_step(client, owner)
    return owner


def saved(url: str, target: str) -> list[dict[str, Any]]:
    return run_sql(
        url,
        "SELECT reported_id, target_id, snapshot FROM reports WHERE target = :t "
        "ORDER BY created_at",
        t=target,
    )


async def test_team_messages_goals_and_notes_can_be_reported_by_teammates(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    url = fresh_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        message = (
            await client.post(
                f"{TEAMS}/{team}/messages", json={"body": "Buy my course"}, headers=asha.headers
            )
        ).json()
        goal = (
            await client.post(
                f"{TEAMS}/{team}/space/goals", json={"title": "Sell things"}, headers=asha.headers
            )
        ).json()
        note = (
            await client.post(
                f"{TEAMS}/{team}/space/logs", json={"note": "Sold some"}, headers=asha.headers
            )
        ).json()
        paths = {
            "team_message": f"team-messages/{message['id']}",
            "goal": f"space-goals/{goal['id']}",
            "progress_log": f"progress-logs/{note['id']}",
        }
        by_teammate = {target: await report(client, ravi, path) for target, path in paths.items()}
        twice = await report(client, ravi, paths["team_message"])
        own = {target: await report(client, asha, path) for target, path in paths.items()}
        outsider = {target: await report(client, mina, path) for target, path in paths.items()}
        unknown = await report(client, ravi, f"team-messages/{uuid.uuid4()}")
        signed_out = await client.post(
            f"/api/v1/{paths['team_message']}/report", json={"reason": "spam"}
        )
        invalid = await report(client, ravi, paths["team_message"], reason="boring")

    for target, response in by_teammate.items():
        assert response.status_code == 201, (target, response.text)
    assert error_code(twice) == "already_reported"
    assert error_code(own["team_message"]) == "cannot_report_own_message"
    assert error_code(own["goal"]) == "cannot_report_own_entry"
    assert error_code(own["progress_log"]) == "cannot_report_own_entry"
    assert error_code(outsider["team_message"]) == "message_not_found"
    assert error_code(outsider["goal"]) == "goal_not_found"
    assert error_code(outsider["progress_log"]) == "log_not_found"
    assert error_code(unknown) == "message_not_found"
    assert signed_out.status_code == 401
    assert invalid.status_code == 422
    [row] = saved(url, "team_message")
    # The report is about the sender, and keeps a copy of that one message only.
    assert (str(row["reported_id"]), str(row["target_id"])) == (asha.id, message["id"])
    assert [item["body"] for item in row["snapshot"]] == ["Buy my course"]
    assert [str(r["reported_id"]) for r in saved(url, "goal")] == [asha.id]
    assert [str(r["reported_id"]) for r in saved(url, "progress_log")] == [asha.id]


async def test_a_reported_listing_is_taken_down_when_the_moderator_acts(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    url = fresh_url
    async with auth_client(settings, delivery) as client:
        admin = await owner_of(client, settings, delivery)
        asha, ravi, team = await pair_in_team(client, settings, delivery, url)
        mina = await join(client, settings, delivery, "Mina")
        hidden = await report(client, mina, f"teams/{team}")
        listed = await client.patch(
            f"{TEAMS}/{team}",
            json={"listed": True, "looking_for": "Anyone with money"},
            headers=asha.headers,
        )
        by_stranger = await report(client, mina, f"teams/{team}", reason="scam")
        by_member = await report(client, ravi, f"teams/{team}")
        by_owner = await report(client, asha, f"teams/{team}")
        missing = await report(client, mina, f"teams/{uuid.uuid4()}")
        rows = saved(url, "team")
        report_ids = run_sql(
            url, "SELECT id FROM reports WHERE target = 'team' ORDER BY created_at"
        )
        dismissed = await client.post(
            f"{ADMIN}/safety/reports/{report_ids[0]['id']}/decide",
            json={"decision": "dismiss", "reason": REASON},
            headers=admin.headers,
        )
        still_listed = (await team_of(client, asha, team)).json()
        warned = await client.post(
            f"{ADMIN}/safety/reports/{report_ids[1]['id']}/decide",
            json={"decision": "warn", "reason": REASON},
            headers=admin.headers,
        )
        after = (await team_of(client, asha, team)).json()

    assert error_code(hidden) == "team_not_found"  # an unlisted team is not a stranger's to see
    assert listed.status_code == 200, listed.text
    assert by_stranger.status_code == 201, by_stranger.text
    assert by_member.status_code == 201, by_member.text
    assert error_code(by_owner) == "cannot_report_own_entry"
    assert error_code(missing) == "team_not_found"
    assert {str(row["reported_id"]) for row in rows} == {asha.id}  # about the owner
    assert [item["body"] for item in rows[0]["snapshot"]] == [
        "Hack night",
        "48 hours, one app.",
        "Anyone with money",
    ]
    assert dismissed.status_code == 200, dismissed.text
    assert still_listed["listed"] is True
    assert warned.status_code == 200, warned.text
    assert (after["listed"], after["looking_for"]) == (False, "")
    assert after["name"] == "Hack night"  # the team itself stays


async def test_listing_text_goes_through_the_content_rules(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    url = fresh_url
    async with auth_client(settings, delivery) as client:
        admin = await owner_of(client, settings, delivery)
        asha, _, team = await pair_in_team(client, settings, delivery, url)
        unlisted = await client.patch(
            f"{TEAMS}/{team}",
            json={"description": "Mail me at asha@example.com"},
            headers=asha.headers,
        )
        before = run_sql(url, "SELECT id FROM content_flags WHERE item_type = 'team'")
        listed = await client.patch(
            f"{TEAMS}/{team}",
            json={"listed": True, "looking_for": "Call 98765 43210"},
            headers=asha.headers,
        )
        queue = (await client.get(f"{ADMIN}/content/flags", headers=admin.headers)).json()
        flag = next(item for item in queue["items"] if item["item_type"] == "team")
        removed = await client.post(
            f"{ADMIN}/content/flags/{flag['id']}/decide",
            json={"decision": "remove", "reason": REASON},
            headers=admin.headers,
        )
        after = (await team_of(client, asha, team)).json()

    assert unlisted.status_code == 200, unlisted.text
    assert before == []  # only listed teams are checked: nobody else can read the others
    assert listed.status_code == 200, listed.text  # a flag never blocks the save
    assert flag["user_id"] == asha.id
    assert "98765 43210" in flag["flagged_text"]
    assert removed.status_code == 204, removed.text
    assert (after["listed"], after["description"], after["looking_for"]) == (False, "", "")
    assert after["name"] == "Hack night"
