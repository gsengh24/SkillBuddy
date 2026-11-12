"""Onboarding step 5 (ADR 0022): finish, the compose job and complete, against Postgres.

No test calls a real AI provider: the job runs with the AI off (template) or through the
real gateway with a fake provider.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, Source
from app.ai.prompts import load_prompt
from app.ai.providers import FakeProvider
from app.ai.stages import Chips, compose
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.tasks import COMPOSE_PROFILE, EMBED_PROFILE, PARSE_PROFILE
from app.services.profile_compose import compose_profile
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_profile_api import PROFILE, jobs_for, run_jobs, signed_in

ONBOARDING = "/api/v1/me/onboarding"
CHIPS = Chips(
    intents=["build_together"],
    offers=["React", "Figma"],
    wants=["Node.js"],
    interests=["Chess"],
    note="a backend partner, mail me at aarav.s@thapar.edu",
    availability="Weekends · 4-6 h/week",
)
AI_REPLY = {
    "title": "Frontend builder looking for a backend partner",
    "summary": "Builds React apps and designs in Figma; wants a backend partner.",
    "about": "I build React apps and design in Figma. I'm looking for a backend partner.",
}


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


def _fake(*replies: str) -> FakeProvider:
    return FakeProvider(name=f"groq-{uuid.uuid4().hex[:6]}", replies=list(replies))


async def _steps(client: AsyncClient, token: str, *, name: str = "Aarav S.") -> None:
    auth = bearer(token)
    await client.put(f"{ONBOARDING}/intents", json={"intents": ["build_together"]}, headers=auth)
    await client.put(f"{ONBOARDING}/offers", json={"skills": ["React", "Figma"]}, headers=auth)
    await client.put(
        f"{ONBOARDING}/wants",
        json={"skills": ["Node.js"], "interests": ["Chess"], "note": "a backend partner"},
        headers=auth,
    )
    await client.put(
        f"{ONBOARDING}/about",
        json={"available_days": ["sat", "sun"], "weekly_hours": "4_6", "display_name": name},
        headers=auth,
    )


def _profile_row(url: str, user_id: str) -> dict[str, Any]:
    rows = run_sql(
        url,
        "SELECT raw_about_text, parse_status, parse_source, structured, "
        "onboarding_completed_at FROM profiles WHERE user_id = :u",
        u=user_id,
    )
    return rows[0]


# --- the stage -------------------------------------------------------------------------


async def test_compose_uses_the_model_and_sends_no_name_or_contact_details(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    groq = _fake(json.dumps(AI_REPLY))
    gateway = AIGateway(settings, session_factory, [groq], cooling_until={})
    result = await compose(gateway, CHIPS, user_id=str(uuid.uuid4()), name_hints=["Aarav S."])

    assert result.source is Source.LLM
    assert result.value.title == AI_REPLY["title"]
    sent = groq.requests[0]
    assert sent.system.startswith(load_prompt("compose_v1"))
    assert "React" in sent.user
    for leaked in ("Aarav", "aarav.s@thapar.edu"):
        assert leaked not in sent.user


async def test_compose_invalid_output_twice_uses_the_template(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    bad = json.dumps({"title": "x" * 200})
    groq = _fake(bad, bad)
    gateway = AIGateway(settings, session_factory, [groq], cooling_until={})
    result = await compose(gateway, CHIPS, user_id=str(uuid.uuid4()))

    assert result.source is Source.TEMPLATE
    assert len(groq.requests) == 2
    assert result.value.about.startswith("Offers: React, Figma. Wants: Node.js.")
    # The template sees the redacted note too.
    assert "thapar.edu" not in result.value.about


# --- finish ----------------------------------------------------------------------------


async def test_finish_needs_sign_in_step_one_and_consent(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.post(f"{ONBOARDING}/finish", json={"ai_consent": True})
        token = await signed_in(client, settings, delivery)
        no_intents = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )
        await _steps(client, token)
        no_consent = await client.post(f"{ONBOARDING}/finish", json={}, headers=bearer(token))
        bad = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": "yes please"}, headers=bearer(token)
        )

    assert anonymous.status_code == 401
    assert no_intents.status_code == 409
    assert error_code(no_intents) == "onboarding_intents_required"
    assert no_consent.status_code == 400
    assert error_code(no_consent) == "ai_consent_required"
    assert bad.status_code == 422


async def test_finish_returns_the_template_at_once_and_queues_the_ai(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        finished = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )

    assert finished.status_code == 200, finished.text
    profile = finished.json()
    assert profile["parse_status"] == "pending"
    assert profile["parse_source"] == "template"
    assert profile["about_text"] == (
        "Offers: React, Figma. Wants: Node.js. Into: chess. "
        "Looking for: a backend partner. Free: Weekends · 4-6 h/week."
    )
    assert profile["ai_consent_current"] is True
    assert profile["onboarding_completed_at"] is None
    assert jobs_for(migrated_database_url, profile["user_id"], COMPOSE_PROFILE.kind) == [
        {"status": "queued"}
    ]


# --- the job ---------------------------------------------------------------------------


async def test_job_with_ai_off_keeps_the_template_and_waits_to_embed(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        finished = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )
        user_id = finished.json()["user_id"]
        await run_jobs(session_factory, settings, COMPOSE_PROFILE)
        after = await client.get(PROFILE, headers=bearer(token))

    data = after.json()
    assert (data["parse_status"], data["parse_source"]) == ("parsed", "template")
    assert data["about_text"] == finished.json()["about_text"]
    assert data["understanding"]["title"] == "Offers React, wants Node.js"
    assert data["understanding"]["offers"] == ["React", "Figma"]
    assert data["understanding"]["seeks"] == ["Node.js"]
    assert data["understanding"]["availability"] == "Weekends · 4-6 h/week"
    # Not matchable until the person confirms it on step 5.
    assert jobs_for(migrated_database_url, user_id, EMBED_PROFILE.kind) == []


async def test_job_replaces_the_template_with_the_ai_text(
    make_settings: SettingsFactory,
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        finished = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )
    user_id = uuid.UUID(finished.json()["user_id"])
    queued: list[uuid.UUID] = []

    async def after(_: AsyncSession, who: uuid.UUID) -> None:
        queued.append(who)

    ai_settings = make_settings(database_url=migrated_database_url)
    gateway = AIGateway(
        ai_settings, session_factory, [_fake(json.dumps(AI_REPLY))], cooling_until={}
    )
    assert await compose_profile(session_factory, gateway, user_id, after_compose=after)
    # Idempotent: a second run (an expired lease) changes nothing.
    assert not await compose_profile(session_factory, gateway, user_id, after_compose=after)

    row = _profile_row(migrated_database_url, str(user_id))
    assert row["raw_about_text"] == AI_REPLY["about"]
    assert (row["parse_status"], row["parse_source"]) == ("parsed", "llm")
    assert row["structured"]["title"] == AI_REPLY["title"]
    assert row["structured"]["offers"] == ["React", "Figma"]
    assert queued == []


async def test_job_keeps_a_template_the_person_already_confirmed_and_embeds(
    make_settings: SettingsFactory,
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        finished = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )
        template = finished.json()["about_text"]
        done = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": template}, headers=bearer(token)
        )
    assert done.status_code == 200, done.text
    user_id = uuid.UUID(done.json()["user_id"])
    queued: list[uuid.UUID] = []

    async def after(_: AsyncSession, who: uuid.UUID) -> None:
        queued.append(who)

    ai_settings = make_settings(database_url=migrated_database_url)
    gateway = AIGateway(
        ai_settings, session_factory, [_fake(json.dumps(AI_REPLY))], cooling_until={}
    )
    assert await compose_profile(session_factory, gateway, user_id, after_compose=after)

    row = _profile_row(migrated_database_url, str(user_id))
    assert row["raw_about_text"] == template
    assert row["structured"]["title"] == AI_REPLY["title"]
    assert queued == [user_id]


# --- complete --------------------------------------------------------------------------


async def test_complete_needs_a_finished_step_four_and_valid_text(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.post(f"{ONBOARDING}/complete", json={"about_text": "Hi there"})
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        early = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": "Hi there"}, headers=bearer(token)
        )
        await client.post(f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token))
        empty = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": "   "}, headers=bearer(token)
        )
        long = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": "x" * 501}, headers=bearer(token)
        )

    assert anonymous.status_code == 401
    assert early.status_code == 409
    assert error_code(early) == "onboarding_not_finished"
    assert empty.status_code == 422
    assert long.status_code == 422


async def test_complete_with_an_edit_reads_it_again_keeping_the_chips(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    edited = "I build React apps. I love hiking and want someone to build a side project with."
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await _steps(client, token)
        await client.post(f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token))
        done = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": edited}, headers=bearer(token)
        )
        user_id = done.json()["user_id"]
        progress = await client.get(ONBOARDING, headers=bearer(token))
        # The compose job finds the text changed and leaves it; the parse reads it.
        await run_jobs(session_factory, settings, COMPOSE_PROFILE, PARSE_PROFILE)
        again = await client.post(
            f"{ONBOARDING}/complete", json={"about_text": "Something else"}, headers=bearer(token)
        )
        refinish = await client.post(
            f"{ONBOARDING}/finish", json={"ai_consent": True}, headers=bearer(token)
        )

    assert done.status_code == 200, done.text
    assert done.json()["onboarding_completed_at"] is not None
    assert progress.json()["next_step"] is None
    row = _profile_row(migrated_database_url, user_id)
    assert row["raw_about_text"] == edited
    assert row["parse_status"] == "parsed"
    # The chips come first; the parse of the edited text only adds to them.
    assert row["structured"]["offers"][:2] == ["React", "Figma"]
    assert row["structured"]["interests"][0] == "Chess"
    assert jobs_for(migrated_database_url, user_id, EMBED_PROFILE.kind) == [{"status": "queued"}]
    # Finished is finished: confirming again changes nothing; finishing again is refused.
    assert again.json()["about_text"] == edited
    assert refinish.status_code == 409
    assert error_code(refinish) == "onboarding_completed"
