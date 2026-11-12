"""Onboarding step saves, skips and progress (ADR 0022), against real PostgreSQL."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client
from tests.integration.test_auth_codes import error_code, new_email, sign_in
from tests.integration.test_auth_sessions import bearer, csrf_headers
from tests.integration.test_profile_api import PROFILE, body, jobs_for, signed_in

ONBOARDING = "/api/v1/me/onboarding"


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


def states(progress: dict[str, Any]) -> dict[str, str]:
    return {item["step"]: item["state"] for item in progress["steps"]}


# --- reading ---------------------------------------------------------------------------


async def test_progress_needs_sign_in(settings: Settings, delivery: CapturingDelivery) -> None:
    async with auth_client(settings, delivery) as client:
        response = await client.get(ONBOARDING)

    assert response.status_code == 401
    assert error_code(response) == "authentication_required"


async def test_progress_before_a_profile_exists(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        progress = await client.get(ONBOARDING, headers=bearer(token))
        profile = await client.get(PROFILE, headers=bearer(token))

    assert progress.status_code == 200
    data = progress.json()
    assert data["completed_at"] is None
    assert data["next_step"] == "intents"
    assert states(data) == {
        "intents": "todo",
        "offers": "todo",
        "wants": "todo",
        "about": "todo",
    }
    assert data["offer_skills"] == []
    # Reading progress creates nothing.
    assert profile.status_code == 404


# --- saving steps ----------------------------------------------------------------------


async def test_each_step_saves_on_its_own_and_resumes_at_the_next(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        auth = bearer(token)
        step1 = await client.put(
            f"{ONBOARDING}/intents",
            json={"intents": ["build_together", "skill_exchange", "build_together"]},
            headers=auth,
        )
        step2 = await client.put(
            f"{ONBOARDING}/offers",
            json={"skills": ["React", " Figma ", "react", "Python"]},
            headers=auth,
        )
        resumed = await client.get(ONBOARDING, headers=auth)
        step3 = await client.put(
            f"{ONBOARDING}/wants",
            json={
                "skills": ["Backend development"],
                "interests": ["Chess", "Hackathons"],
                "note": "  a designer for my app ",
            },
            headers=auth,
        )
        step4 = await client.put(
            f"{ONBOARDING}/about",
            json={
                "study_year": "3",
                "branch": "computer",
                "available_days": ["sat", "sun", "sat"],
                "weekly_hours": "4_6",
                "display_name": "Aarav S.",
            },
            headers=auth,
        )
        profile = await client.get(PROFILE, headers=auth)

    assert step1.status_code == 200, step1.text
    assert step1.json()["intents"] == ["build_together", "skill_exchange"]
    assert step1.json()["next_step"] == "offers"
    assert step2.status_code == 200, step2.text
    # Trimmed, and repeats ignoring case dropped, keeping the first spelling.
    assert step2.json()["offer_skills"] == ["React", "Figma", "Python"]
    assert resumed.json()["next_step"] == "wants"
    assert step3.status_code == 200, step3.text
    assert step3.json()["want_note"] == "a designer for my app"
    assert step3.json()["interest_tags"] == ["Chess", "Hackathons"]
    assert step4.status_code == 200, step4.text
    done = step4.json()
    assert done["next_step"] == "review"
    assert done["completed_at"] is None
    assert set(states(done).values()) == {"saved"}
    assert (done["study_year"], done["branch"], done["weekly_hours"]) == ("3", "computer", "4_6")
    assert done["available_days"] == ["sat", "sun"]
    assert done["display_name"] == "Aarav S."

    # The steps made a profile with no about text: nothing to parse, no AI, not matchable yet.
    assert profile.status_code == 200
    saved = profile.json()
    assert saved["parse_status"] == "empty"
    assert saved["offer_skills"] == ["React", "Figma", "Python"]
    assert saved["onboarding_completed_at"] is None
    assert saved["ai_consent_at"] is None
    assert jobs_for(migrated_database_url, saved["user_id"], "parse_profile") == []


async def test_skipping_keeps_what_was_saved_and_saving_replaces_the_skip(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        auth = bearer(token)
        await client.put(f"{ONBOARDING}/intents", json={"intents": ["explore"]}, headers=auth)
        await client.put(f"{ONBOARDING}/offers", json={"skills": ["SQL"]}, headers=auth)
        skipped_offers = await client.post(f"{ONBOARDING}/offers/skip", headers=auth)
        skipped_wants = await client.post(f"{ONBOARDING}/wants/skip", headers=auth)
        skipped_about = await client.post(f"{ONBOARDING}/about/skip", headers=auth)
        saved_wants = await client.put(
            f"{ONBOARDING}/wants", json={"interests": ["Music"]}, headers=auth
        )

    assert skipped_offers.status_code == 200, skipped_offers.text
    assert states(skipped_offers.json())["offers"] == "skipped"
    assert skipped_offers.json()["offer_skills"] == ["SQL"]
    assert skipped_wants.json()["next_step"] == "about"
    assert skipped_about.json()["next_step"] == "review"
    assert states(saved_wants.json()) == {
        "intents": "saved",
        "offers": "skipped",
        "wants": "saved",
        "about": "skipped",
    }


async def test_about_step_keeps_omitted_fields_and_null_clears(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        auth = bearer(token)
        await client.put(
            f"{ONBOARDING}/about",
            json={"study_year": "postgrad", "branch": "other", "available_days": ["mon"]},
            headers=auth,
        )
        changed = await client.put(
            f"{ONBOARDING}/about",
            json={"study_year": None, "weekly_hours": "10_plus"},
            headers=auth,
        )

    assert changed.status_code == 200, changed.text
    data = changed.json()
    assert data["study_year"] is None
    assert data["branch"] == "other"
    assert data["available_days"] == ["mon"]
    assert data["weekly_hours"] == "10_plus"


async def test_a_full_profile_save_finishes_onboarding_and_keeps_the_chips(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        auth = bearer(token)
        await client.put(f"{ONBOARDING}/offers", json={"skills": ["Arduino"]}, headers=auth)
        saved = await client.put(PROFILE, json=body(), headers=auth)
        progress = await client.get(ONBOARDING, headers=auth)
        again = await client.put(
            PROFILE, json=body(about_text=body()["about_text"] + " Also Go."), headers=auth
        )

    assert saved.status_code == 200, saved.text
    finished = saved.json()["onboarding_completed_at"]
    assert finished is not None
    assert saved.json()["offer_skills"] == ["Arduino"]
    assert progress.json()["next_step"] is None
    assert progress.json()["completed_at"] == finished
    # A later save doesn't move the date.
    assert again.json()["onboarding_completed_at"] == finished


# --- failures --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("intents", {"intents": []}),
        ("intents", {"intents": ["networking"]}),
        ("intents", {}),
        ("offers", {"skills": [f"skill {n}" for n in range(21)]}),
        ("offers", {"skills": ["x" * 61]}),
        ("offers", {"skills": ["   "]}),
        ("offers", {"skills": ["SQL"], "extra": True}),
        ("wants", {"note": "x" * 141}),
        ("wants", {"interests": [f"interest {n}" for n in range(21)]}),
        ("about", {"study_year": "5"}),
        ("about", {"branch": "law"}),
        ("about", {"weekly_hours": "1_2"}),
        ("about", {"available_days": ["someday"]}),
        ("about", {"display_name": "x" * 61}),
    ],
)
async def test_step_validation(
    settings: Settings, delivery: CapturingDelivery, path: str, payload: dict[str, Any]
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        response = await client.put(f"{ONBOARDING}/{path}", json=payload, headers=bearer(token))
        profile = await client.get(PROFILE, headers=bearer(token))

    assert response.status_code == 422, response.text
    assert error_code(response) == "validation_error"
    # A refused save creates nothing.
    assert profile.status_code == 404


async def test_only_steps_two_to_four_can_be_skipped(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        intents = await client.post(f"{ONBOARDING}/intents/skip", headers=bearer(token))
        unknown = await client.post(f"{ONBOARDING}/review/skip", headers=bearer(token))

    assert intents.status_code == 422
    assert unknown.status_code == 422


async def test_writes_need_sign_in_json_and_csrf(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.put(f"{ONBOARDING}/offers", json={"skills": ["SQL"]})
        anonymous_skip = await client.post(f"{ONBOARDING}/offers/skip")
        await sign_in(client, delivery, new_email())
        # Signed in with the cookie: writes need the CSRF header.
        no_csrf = await client.put(f"{ONBOARDING}/offers", json={"skills": ["SQL"]})
        no_csrf_skip = await client.post(f"{ONBOARDING}/offers/skip")
        not_json = await client.put(
            f"{ONBOARDING}/offers",
            content=b"skills=SQL",
            headers={**csrf_headers(client, settings), "Content-Type": "text/plain"},
        )
        ok = await client.put(
            f"{ONBOARDING}/offers",
            json={"skills": ["SQL"]},
            headers=csrf_headers(client, settings),
        )

    assert anonymous.status_code == 401
    assert anonymous_skip.status_code == 401
    assert no_csrf.status_code == 403
    assert error_code(no_csrf) == "csrf_failed"
    assert no_csrf_skip.status_code == 403
    assert not_json.status_code == 415
    assert ok.status_code == 200, ok.text


async def test_step_saves_are_rate_limited(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url, ai_llm_enabled=False, profile_update_limit_per_user=2
    )
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        results = [
            await client.post(f"{ONBOARDING}/offers/skip", headers=bearer(token)) for _ in range(3)
        ]

    assert [r.status_code for r in results] == [200, 200, 429]


async def test_step_saves_pause_when_storage_is_nearly_full(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    normal = make_settings(database_url=migrated_database_url, ai_llm_enabled=False)
    async with auth_client(normal, delivery) as client:
        token = await signed_in(client, normal, delivery)

    # Any real database exceeds 90% of a 1 MB limit.
    full = make_settings(
        database_url=migrated_database_url, ai_llm_enabled=False, database_size_limit_mb=1
    )
    async with auth_client(full, delivery) as client:
        saved = await client.put(
            f"{ONBOARDING}/offers", json={"skills": ["SQL"]}, headers=bearer(token)
        )
        skipped = await client.post(f"{ONBOARDING}/offers/skip", headers=bearer(token))
        read = await client.get(ONBOARDING, headers=bearer(token))

    assert saved.status_code == 503
    assert error_code(saved) == "storage_full"
    assert skipped.status_code == 503
    assert read.status_code == 200
