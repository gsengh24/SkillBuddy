"""Profile endpoints and the parse jobs, against real PostgreSQL. No AI provider is called."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobRegistry, JobRunner
from app.jobs.tasks import EMBED_PROFILE, PARSE_PENDING_PROFILES, PARSE_PROFILE
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code, new_email, sign_in
from tests.integration.test_auth_sessions import bearer

PROFILE = "/api/v1/me/profile"
UNDERSTANDING = "/api/v1/me/profile/understanding"
ABOUT = (
    "I can build React apps and write Python. Looking for a designer, a backend dev. "
    "I love hiking and chess. Free 4-6 hours a week, mostly weekends."
)


def body(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "display_name": "Asha",
        "about_text": ABOUT,
        "links": ["https://github.com/example"],
        "timezone": "Asia/Kolkata",
        "languages": ["en", "hi"],
        "ai_consent": True,
    }
    return data | overrides


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


async def signed_in(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> str:
    """Signs in and returns a bearer token (the non-browser path: no cookies, no CSRF)."""
    await sign_in(client, delivery, new_email())
    token = client.cookies[settings.session_cookie_name]
    client.cookies.clear()
    return token


def jobs_for(url: str, user_id: str, kind: str) -> list[dict[str, Any]]:
    return run_sql(
        url,
        "SELECT status FROM jobs WHERE kind = :k AND payload->>'user_id' = :u",
        k=kind,
        u=user_id,
    )


async def run_jobs(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, *specs: Any
) -> None:
    await JobRunner(session_factory, JobRegistry(list(specs)), settings).run_until_idle()


# --- reading ---------------------------------------------------------------------------


async def test_profile_needs_sign_in_and_is_404_before_it_exists(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.get(PROFILE)
        token = await signed_in(client, settings, delivery)
        missing = await client.get(PROFILE, headers=bearer(token))
        patch = await client.patch(PROFILE, json={"visibility": "paused"}, headers=bearer(token))

    assert anonymous.status_code == 401
    assert error_code(anonymous) == "authentication_required"
    assert missing.status_code == 404
    assert error_code(missing) == "profile_not_found"
    assert patch.status_code == 404


# --- saving ----------------------------------------------------------------------------


async def test_save_requires_ai_consent_then_queues_a_parse(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        refused = await client.put(PROFILE, json=body(ai_consent=False), headers=bearer(token))
        saved = await client.put(PROFILE, json=body(), headers=bearer(token))
        fetched = await client.get(PROFILE, headers=bearer(token))

    assert refused.status_code == 400
    assert error_code(refused) == "ai_consent_required"
    assert saved.status_code == 200, saved.text
    profile = saved.json()
    assert profile["parse_status"] == "pending"
    assert profile["understanding"] is None
    assert profile["display_name"] == "Asha"
    assert profile["visibility"] == "matchable"
    assert profile["ai_consent_version"] == settings.ai_consent_version
    assert profile["ai_consent_current"] is True
    assert fetched.json() == profile
    assert jobs_for(migrated_database_url, profile["user_id"], "parse_profile") == [
        {"status": "queued"}
    ]


async def test_only_a_changed_text_is_parsed_again(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        first = await client.put(PROFILE, json=body(), headers=bearer(token))
        # Consent is remembered; same text with different spacing is not a change.
        same = await client.put(
            PROFILE,
            json=body(about_text="  " + ABOUT.replace(". ", ".  "), ai_consent=False),
            headers=bearer(token),
        )
        changed = await client.put(
            PROFILE,
            json=body(about_text=ABOUT + " Also chess.", ai_consent=False),
            headers=bearer(token),
        )

    user_id = first.json()["user_id"]
    assert (same.status_code, changed.status_code) == (200, 200)
    assert len(jobs_for(migrated_database_url, user_id, "parse_profile")) == 2


async def test_a_new_consent_version_asks_again(
    make_settings: SettingsFactory,
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put(PROFILE, json=body(), headers=bearer(token))
    newer = make_settings(
        database_url=migrated_database_url, ai_llm_enabled=False, ai_consent_version="2027-01-01"
    )
    async with auth_client(newer, delivery) as client:
        stale = await client.get(PROFILE, headers=bearer(token))
        refused = await client.put(PROFILE, json=body(ai_consent=False), headers=bearer(token))
        agreed = await client.put(PROFILE, json=body(), headers=bearer(token))

    assert stale.json()["ai_consent_current"] is False
    assert error_code(refused) == "ai_consent_required"
    assert agreed.json()["ai_consent_version"] == "2027-01-01"


@pytest.mark.parametrize(
    "overrides",
    [
        {"about_text": "too short"},
        {"about_text": "x" * 2001},
        {"display_name": ""},
        {"display_name": "n" * 61},
        {"links": ["http://example.com"]},
        {"links": ["javascript:alert(1)"]},
        {"links": [f"https://example.com/{i}" for i in range(4)]},
        {"timezone": "Not a zone!"},
        {"languages": ["english language"]},
        {"visibility": "public"},
        {"email": "someone@example.com"},
        # The You page fields change only through PATCH.
        {"city": "Bengaluru"},
    ],
)
async def test_save_validation(
    settings: Settings, delivery: CapturingDelivery, overrides: dict[str, Any]
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        response = await client.put(PROFILE, json=body(**overrides), headers=bearer(token))

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_non_json_bodies_are_refused(settings: Settings, delivery: CapturingDelivery) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        response = await client.put(
            PROFILE,
            content=b"display_name=x",
            headers=bearer(token) | {"content-type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 415


async def test_saves_are_rate_limited(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url, ai_llm_enabled=False, profile_update_limit_per_user=2
    )
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        codes = [
            (await client.put(PROFILE, json=body(), headers=bearer(token))).status_code
            for _ in range(3)
        ]
    assert codes == [200, 200, 429]


# --- settings --------------------------------------------------------------------------


async def test_settings_change_without_touching_the_text(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        saved = await client.put(PROFILE, json=body(), headers=bearer(token))
        patched = await client.patch(
            PROFILE,
            json={"visibility": "paused", "timezone": None, "links": []},
            headers=bearer(token),
        )
        about = await client.patch(PROFILE, json={"about_text": "new"}, headers=bearer(token))

    assert patched.status_code == 200
    result = patched.json()
    assert (result["visibility"], result["timezone"], result["links"]) == ("paused", None, [])
    assert result["display_name"] == "Asha"
    assert result["about_text"] == ABOUT
    assert about.status_code == 422
    user_id = saved.json()["user_id"]
    assert len(jobs_for(migrated_database_url, user_id, "parse_profile")) == 1


YOU_PAGE_DEFAULTS: dict[str, Any] = {
    "city": "",
    "headline": "",
    "experience_level": None,
    "intents": [],
    "goal": "",
    "working_style": None,
    "weekly_hours": None,
    "available_days": [],
    "available_from": None,
    "available_until": None,
    "location_precision": "city",
    "show_last_active": True,
    "intros_only_from_strong_matches": False,
    "email_notifications": True,
    "email_daily_digest": False,
    "email_match_suggestions": False,
    "email_product_updates": False,
}

YOU_PAGE_VALUES: dict[str, Any] = {
    "city": "  Bengaluru ",
    "headline": "Product designer learning to code",
    "experience_level": "1_3_years",
    "intents": ["build_together", "skill_exchange", "build_together"],
    "goal": "Ship a small habit-tracking app by December.",
    "working_style": "mix",
    "weekly_hours": "4_6",
    "available_days": ["sat", "sun", "sat"],
    "available_from": "18:00",
    "available_until": "22:30",
    "location_precision": "hidden",
    "show_last_active": False,
    "intros_only_from_strong_matches": True,
    "email_notifications": False,
    "email_daily_digest": True,
    "email_match_suggestions": True,
    "email_product_updates": True,
}


async def test_you_page_fields_default_to_todays_behaviour(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        saved = await client.put(PROFILE, json=body(), headers=bearer(token))

    assert saved.status_code == 200
    result = saved.json()
    assert {key: result[key] for key in YOU_PAGE_DEFAULTS} == YOU_PAGE_DEFAULTS
    assert result["visibility"] == "matchable"


async def test_an_email_code_account_has_no_picture_to_show(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        saved = await client.put(PROFILE, json=body(), headers=bearer(token))
        refused = await client.patch(PROFILE, json={"show_photo": True}, headers=bearer(token))
        off = await client.patch(PROFILE, json={"show_photo": False}, headers=bearer(token))
        not_a_switch = await client.patch(
            PROFILE, json={"photo_url": "https://example.com/me.png"}, headers=bearer(token)
        )

    assert (saved.json()["photo_url"], saved.json()["photo_available"]) == (None, False)
    assert refused.status_code == 409
    assert error_code(refused) == "photo_unavailable"
    assert off.status_code == 200
    assert off.json()["photo_url"] is None
    # Nobody can point the picture at an address of their own choosing.
    assert not_a_switch.status_code == 422


async def test_you_page_fields_save_clear_and_survive_a_full_save(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put(PROFILE, json=body(), headers=bearer(token))
        patched = await client.patch(PROFILE, json=YOU_PAGE_VALUES, headers=bearer(token))
        # The profile form of today's web app sends PUT without these fields.
        resaved = await client.put(PROFILE, json=body(), headers=bearer(token))
        cleared = await client.patch(
            PROFILE,
            json={
                "experience_level": None,
                "working_style": None,
                "weekly_hours": None,
                "available_from": None,
                "available_until": None,
                # Null leaves these alone; an empty value clears them.
                "city": None,
                "intents": None,
                "headline": "",
                "available_days": [],
            },
            headers=bearer(token),
        )
        after_intro = await client.patch(
            PROFILE, json={"visibility": "after_intro"}, headers=bearer(token)
        )

    assert patched.status_code == 200
    result = patched.json()
    assert {key: result[key] for key in YOU_PAGE_VALUES} == YOU_PAGE_VALUES | {
        "city": "Bengaluru",
        "intents": ["build_together", "skill_exchange"],
        "available_days": ["sat", "sun"],
        "available_from": "18:00:00",
        "available_until": "22:30:00",
    }
    assert resaved.json()["goal"] == YOU_PAGE_VALUES["goal"]
    assert resaved.json()["email_daily_digest"] is True
    result = cleared.json()
    assert (
        result["experience_level"],
        result["working_style"],
        result["weekly_hours"],
        result["available_from"],
        result["available_until"],
    ) == (None, None, None, None, None)
    assert (result["city"], result["intents"]) == (
        "Bengaluru",
        ["build_together", "skill_exchange"],
    )
    assert (result["headline"], result["available_days"]) == ("", [])
    assert result["goal"] == YOU_PAGE_VALUES["goal"]
    assert after_intro.json()["visibility"] == "after_intro"


@pytest.mark.parametrize(
    "change",
    [
        {"city": "c" * 81},
        {"headline": "h" * 81},
        {"goal": "g" * 301},
        {"experience_level": "expert"},
        {"intents": ["dating"]},
        {"working_style": "remote"},
        {"weekly_hours": "20"},
        {"available_days": ["monday"]},
        {"available_from": "25:00"},
        {"location_precision": "street"},
        {"show_last_active": "sometimes"},
        {"links": ["http://example.com"]},
        {"links": ["ftp://example.com/file"]},
    ],
)
async def test_you_page_field_validation(
    settings: Settings, delivery: CapturingDelivery, change: dict[str, Any]
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put(PROFILE, json=body(), headers=bearer(token))
        response = await client.patch(PROFILE, json=change, headers=bearer(token))

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_settings_need_a_profile_and_sign_in(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.patch(PROFILE, json={"city": "Pune"})
        token = await signed_in(client, settings, delivery)
        missing = await client.patch(PROFILE, json={"city": "Pune"}, headers=bearer(token))

    assert anonymous.status_code == 401
    assert missing.status_code == 404
    assert error_code(missing) == "profile_not_found"


# --- parsing and embedding jobs --------------------------------------------------------


async def test_parse_job_uses_the_template_with_ai_off_then_embeds(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        user_id = (await client.put(PROFILE, json=body(), headers=bearer(token))).json()["user_id"]
        await run_jobs(session_factory, settings, PARSE_PROFILE, EMBED_PROFILE)
        parsed = (await client.get(PROFILE, headers=bearer(token))).json()

    assert parsed["parse_status"] == "parsed"
    assert parsed["parse_source"] == "template"
    understanding = parsed["understanding"]
    assert understanding["offers"] == ["build React apps", "write Python"]
    assert understanding["seeks"] == ["designer", "backend dev"]
    assert understanding["availability"] == "4-6 hours a week"
    facets = run_sql(
        migrated_database_url,
        "SELECT facet FROM profile_embeddings WHERE user_id = :u ORDER BY facet",
        u=user_id,
    )
    assert [row["facet"] for row in facets] == ["identity", "interest", "offer", "seek"]
    row = run_sql(
        migrated_database_url,
        "SELECT parsed_text_hash, parse_prompt_version FROM profiles WHERE user_id = :u",
        u=user_id,
    )[0]
    assert len(row["parsed_text_hash"]) == 64
    assert row["parse_prompt_version"] is None


async def test_a_users_correction_wins_over_a_queued_parse(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    correction = {
        "summary": "Frontend developer.",
        "offers": ["React", "TypeScript"],
        "seeks": ["UI designer"],
        "interests": ["chess"],
        "availability": "weekends",
    }
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put(PROFILE, json=body(), headers=bearer(token))
        corrected = await client.put(UNDERSTANDING, json=correction, headers=bearer(token))
        await run_jobs(session_factory, settings, PARSE_PROFILE, EMBED_PROFILE)
        after = (await client.get(PROFILE, headers=bearer(token))).json()
        invalid = await client.put(
            UNDERSTANDING, json=correction | {"offers": ["x" * 61]}, headers=bearer(token)
        )

    assert corrected.status_code == 200
    assert corrected.json()["parse_source"] == "user"
    assert after["understanding"] == correction
    assert after["parse_source"] == "user"
    assert invalid.status_code == 422
    embedded = run_sql(
        migrated_database_url,
        "SELECT count(*) AS n FROM profile_embeddings WHERE user_id = :u",
        u=after["user_id"],
    )
    assert embedded[0]["n"] == 4


async def test_correction_needs_a_profile_with_text(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        missing = await client.put(UNDERSTANDING, json={}, headers=bearer(token))
        user_id = (await client.put(PROFILE, json=body(), headers=bearer(token))).json()["user_id"]
        run_sql(
            migrated_database_url,
            "UPDATE profiles SET raw_about_text = '' WHERE user_id = :u",
            u=user_id,
        )
        empty = await client.put(UNDERSTANDING, json={}, headers=bearer(token))

    assert missing.status_code == 404
    assert empty.status_code == 409
    assert error_code(empty) == "profile_text_required"


async def test_parse_skips_a_text_that_changed_after_it_was_read(
    settings: Settings,
    delivery: CapturingDelivery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put(PROFILE, json=body(), headers=bearer(token))
        await client.put(
            PROFILE,
            json=body(about_text="I enjoy chess and long hikes on weekends."),
            headers=bearer(token),
        )
        await run_jobs(session_factory, settings, PARSE_PROFILE, EMBED_PROFILE)
        parsed = (await client.get(PROFILE, headers=bearer(token))).json()

    # Both jobs ran; the result matches the latest text, whichever ran first.
    assert parsed["parse_status"] == "parsed"
    assert parsed["understanding"]["interests"] == ["chess", "long hikes on weekends"]


async def test_backfill_queues_a_parse_for_every_pending_profile(
    settings: Settings,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    users = []
    for _ in range(3):
        user = run_sql(
            migrated_database_url,
            "INSERT INTO users (email) VALUES (:e) RETURNING id",
            e=f"backfill-{uuid.uuid4().hex[:12]}@example.com",
        )[0]["id"]
        run_sql(
            migrated_database_url,
            "INSERT INTO profiles (user_id, raw_about_text, parse_status) "
            "VALUES (:u, 'I like chess and hiking.', 'pending')",
            u=user,
        )
        users.append(str(user))
    run_sql(migrated_database_url, "DELETE FROM jobs WHERE kind = 'parse_pending_profiles'")
    run_sql(
        migrated_database_url,
        "INSERT INTO jobs (kind, priority) VALUES ('parse_pending_profiles', 300)",
    )

    await run_jobs(session_factory, settings, PARSE_PENDING_PROFILES)
    # A second run (e.g. the migration re-applied) does not queue duplicates.
    run_sql(
        migrated_database_url,
        "INSERT INTO jobs (kind, priority) VALUES ('parse_pending_profiles', 300)",
    )
    await run_jobs(session_factory, settings, PARSE_PENDING_PROFILES)

    for user in users:
        assert len(jobs_for(migrated_database_url, user, "parse_profile")) == 1
