"""Onboarding P4 through the API, against real PostgreSQL (ADR 0022): profile strength, chip
edits on You, the soft gate, in-context nudges and aggregate demand."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.services.demand import MIN_COUNT
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_intros import Person, join, matched, send
from tests.integration.test_profile_api import jobs_for, signed_in
from tests.integration.test_teams import TEAMS, create, link

PROFILE = "/api/v1/me/profile"
NUDGE = "/api/v1/me/nudge"
DEMAND = "/api/v1/stats/demand"


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


async def stranger(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Person:
    """Signed in, no profile at all."""
    token = await signed_in(client, settings, delivery)
    me = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()
    return Person(token=token, id=me["id"])


async def offers(client: AsyncClient, person: Person, skills: list[str]) -> Any:
    return await client.put(
        "/api/v1/me/onboarding/offers", json={"skills": skills}, headers=person.headers
    )


def finished(url: str, person: Person) -> None:
    run_sql(
        url,
        "UPDATE profiles SET onboarding_completed_at = now(), parse_status = 'parsed', "
        'structured = \'{"offers": ["React"], "seeks": []}\'::jsonb WHERE user_id = :u',
        u=person.id,
    )


# --- strength -------------------------------------------------------------------------------


async def test_strength_is_computed_by_the_api(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        nobody = await stranger(client, settings, delivery)
        empty = (await client.get("/api/v1/me/onboarding", headers=nobody.headers)).json()
        await client.put(
            "/api/v1/me/onboarding/intents",
            json={"intents": ["build_together"]},
            headers=nobody.headers,
        )
        await offers(client, nobody, ["React", "Python", "Figma"])
        started = (await client.get("/api/v1/me/onboarding", headers=nobody.headers)).json()
        unauthorised = await client.get("/api/v1/me/onboarding")

    assert empty["strength"] == {
        "percent": 0,
        "done": 0,
        "total": 7,
        "missing": [
            "intents",
            "offers",
            "wants",
            "about_text",
            "availability",
            "headline",
            "links",
        ],
    }
    assert started["strength"]["done"] == 2
    assert started["strength"]["percent"] == 29
    assert started["strength"]["missing"][0] == "wants"
    assert unauthorised.status_code == 401


# --- chip edits on You ----------------------------------------------------------------------


async def test_you_edits_the_chip_columns_and_re_embeds(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        finished(url, asha)
        saved = await client.patch(
            PROFILE,
            json={"offer_skills": ["Go", "go", "SQL"], "want_skills": ["Figma"]},
            headers=asha.headers,
        )
        too_long = await client.patch(
            PROFILE, json={"offer_skills": ["x" * 61]}, headers=asha.headers
        )
        too_many = await client.patch(
            PROFILE, json={"offer_skills": [f"s{n}" for n in range(21)]}, headers=asha.headers
        )

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["offer_skills"] == ["Go", "SQL"]
    assert body["want_skills"] == ["Figma"]
    # The matcher's view follows the edit, and the profile is embedded again.
    assert body["understanding"]["offers"] == ["Go", "SQL"]
    assert body["understanding"]["seeks"] == ["Figma"]
    # Two offered skills: not enough for that strength item yet.
    assert "offers" in body["strength"]["missing"]
    assert jobs_for(url, asha.id, "embed_profile")
    assert error_code(too_long) == "validation_error"
    assert error_code(too_many) == "validation_error"


# --- the soft gate --------------------------------------------------------------------------


async def test_an_intro_needs_three_offered_skills(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        await offers(client, asha, ["React", "Figma"])
        _, match = matched(url, asha, ravi)
        blocked = await send(client, asha, match)
        await offers(client, asha, ["React", "Figma", "Python"])
        sent = await send(client, asha, match)

    assert blocked.status_code == 409
    assert error_code(blocked) == "skills_required"
    assert sent.status_code == 201, sent.text


@pytest.mark.usefixtures("teams_on")
async def test_joining_a_team_needs_three_offered_skills(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        team = (await create(client, asha)).json()["id"]
        await client.patch(f"{TEAMS}/{team}", json={"listed": True}, headers=asha.headers)
        code = (await client.post(f"{TEAMS}/{team}/invite-link", headers=asha.headers)).json()[
            "code"
        ]
        nobody = await stranger(client, settings, delivery)
        by_link = await client.post(f"{TEAMS}/join/{code}", headers=nobody.headers)
        asked = await client.post(
            f"{TEAMS}/{team}/requests", json={"note": ""}, headers=nobody.headers
        )
        await offers(client, nobody, ["React", "Figma", "Python"])
        joined = await client.post(f"{TEAMS}/join/{code}", headers=nobody.headers)

        # Accepting an invite is joining too.
        ravi = await join(client, settings, delivery, "Ravi")
        await link(client, url, asha, ravi)
        await offers(client, ravi, ["React"])
        invite = (
            await client.post(
                f"{TEAMS}/{team}/invites", json={"user_id": ravi.id}, headers=asha.headers
            )
        ).json()
        accepted = await client.post(
            f"{TEAMS}/invites/{invite['id']}/respond", json={"accept": True}, headers=ravi.headers
        )
        declined = await client.post(
            f"{TEAMS}/invites/{invite['id']}/respond", json={"accept": False}, headers=ravi.headers
        )

    assert error_code(by_link) == "skills_required"
    assert error_code(asked) == "skills_required"
    assert joined.status_code == 200, joined.text
    assert error_code(accepted) == "skills_required"
    # Saying no is always allowed.
    assert declined.status_code == 200, declined.text


# --- nudges ---------------------------------------------------------------------------------


async def test_the_availability_nudge_after_a_first_match(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        run_sql(url, "UPDATE profiles SET available_days = '{}' WHERE user_id = :u", u=asha.id)
        before = (await client.get(NUDGE, headers=asha.headers)).json()
        matched(url, asha, ravi)
        first = (await client.get(NUDGE, headers=asha.headers)).json()
        again = (await client.get(NUDGE, headers=asha.headers)).json()
        dismissed = await client.post(
            "/api/v1/me/nudges/availability/dismiss", headers=asha.headers
        )
        after = (await client.get(NUDGE, headers=asha.headers)).json()
        # Even a day later a dismissed nudge stays gone.
        run_sql(
            url,
            "UPDATE profiles SET nudge_shown_at = now() - interval '2 days' WHERE user_id = :u",
            u=asha.id,
        )
        later = (await client.get(NUDGE, headers=asha.headers)).json()
        unknown = await client.post("/api/v1/me/nudges/nope/dismiss", headers=asha.headers)
        unauthorised = await client.get(NUDGE)

    assert before == {"nudge": None}
    assert first["nudge"]["kind"] == "availability"
    # A reload the same day keeps it.
    assert again == first
    assert dismissed.status_code == 204
    assert after == {"nudge": None}
    assert later == {"nudge": None}
    assert unknown.status_code == 422
    assert unauthorised.status_code == 401


@pytest.mark.usefixtures("teams_on")
async def test_at_most_one_nudge_a_day_and_the_team_skill_nudge(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        run_sql(url, "UPDATE profiles SET available_days = '{}' WHERE user_id = :u", u=ravi.id)
        team = (await create(client, asha, "ML study circle")).json()["id"]
        code = (await client.post(f"{TEAMS}/{team}/invite-link", headers=asha.headers)).json()[
            "code"
        ]
        joined = await client.post(f"{TEAMS}/join/{code}", headers=ravi.headers)
        matched(url, ravi, asha)
        today = (await client.get(NUDGE, headers=ravi.headers)).json()
        # Both kinds apply, but the day's slot is taken: dismissing doesn't free it.
        await client.post("/api/v1/me/nudges/team_skill/dismiss", headers=ravi.headers)
        same_day = (await client.get(NUDGE, headers=ravi.headers)).json()
        run_sql(
            url,
            "UPDATE profiles SET nudge_shown_at = now() - interval '25 hours' WHERE user_id = :u",
            u=ravi.id,
        )
        next_day = (await client.get(NUDGE, headers=ravi.headers)).json()
        # The owner made the team: no "you joined" nudge for them.
        owner = (await client.get(NUDGE, headers=asha.headers)).json()

    assert joined.status_code == 200, joined.text
    assert today["nudge"] == {
        "kind": "team_skill",
        "skill": "Machine learning",
        "team_id": team,
        "team_name": "ML study circle",
    }
    assert same_day == {"nudge": None}
    assert next_day["nudge"]["kind"] == "availability"
    assert owner == {"nudge": None}


# --- demand ---------------------------------------------------------------------------------


async def test_demand_is_a_count_hidden_below_the_minimum(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        viewer = await join(client, settings, delivery, "Viewer")
        wanters = [await join(client, settings, delivery, f"W{n}") for n in range(MIN_COUNT)]
        for person in wanters[:-1]:
            run_sql(
                url,
                "UPDATE profiles SET want_skills = ARRAY['python'] WHERE user_id = :u",
                u=person.id,
            )
        below = await client.get(DEMAND, params={"skill": "Python"}, headers=viewer.headers)
        # The last one asked for it in a request instead.
        run_sql(
            url,
            "INSERT INTO match_requests (user_id, raw_text, status, expires_at, structured) "
            "VALUES (:u, 'A Python mentor.', 'ready', now() + interval '30 days', "
            '\'{"seeks": ["Python"]}\'::jsonb)',
            u=wanters[-1].id,
        )
        at = await client.get(DEMAND, params={"skill": "Python"}, headers=viewer.headers)
        # Someone the viewer blocked isn't counted.
        run_sql(
            url,
            "INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)",
            a=viewer.id,
            b=wanters[0].id,
        )
        blocked = await client.get(DEMAND, params={"skill": "Python"}, headers=viewer.headers)
        empty = await client.get(DEMAND, params={"skill": " "}, headers=viewer.headers)
        unauthorised = await client.get(DEMAND, params={"skill": "Python"})

    assert below.json() == {"skill": "Python", "count": None, "window_days": 7}
    assert at.json() == {"skill": "Python", "count": MIN_COUNT, "window_days": 7}
    assert blocked.json()["count"] is None
    # Only the count: no names, ids or pictures anywhere in the answer.
    assert set(at.json()) == {"skill", "count", "window_days"}
    assert empty.status_code == 422
    assert unauthorised.status_code == 401
