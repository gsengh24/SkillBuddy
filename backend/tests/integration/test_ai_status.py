"""The AI status view and the provider health check (fake providers, real PostgreSQL).

No test calls a real AI provider, and no key ever appears in what the API returns.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, Prompt, Source, Task
from app.ai.providers import (
    CostModel,
    FakeProvider,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.ai.status import ai_status
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code, new_email
from tests.integration.test_moderation import as_person

GROQ_KEY = "gsk_test_only_not_a_real_key_0000000000"  # test value
CF_TOKEN = "cf_test_only_not_a_real_token_000000000"  # test value
CF_ACCOUNT = "0123456789abcdef0123456789abcdef"


class Answer(BaseModel):
    answer: str


def template() -> Answer:
    return Answer(answer="template")


PROMPT = Prompt(version="test-v1", system="Answer.", data={"text": "synthetic"})


@pytest.fixture
def make(make_settings: SettingsFactory, migrated_database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {"database_url": migrated_database_url}
        return make_settings(**(values | overrides))

    return build


@pytest.fixture
async def session_factory(
    make: Callable[..., Settings], migrated_database_url: str
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # AI counters are per UTC day and shared by the whole test database: start clean.
    run_sql(migrated_database_url, "DELETE FROM rate_limit_counters WHERE key LIKE 'ai:%'")
    engine = create_engine(make())
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def gateway(
    settings: Settings, factory: async_sessionmaker[AsyncSession], *providers: FakeProvider
) -> AIGateway:
    return AIGateway(settings, factory, list(providers), cooling_until={})


async def test_status_shows_which_provider_answered_and_why_templates_ran(
    make: Callable[..., Settings], session_factory: async_sessionmaker[AsyncSession]
) -> None:
    settings = make()
    groq = FakeProvider("groq:test", replies=[ProviderUnavailableError("down")])
    cloudflare = FakeProvider(
        "cloudflare:test",
        replies=[json.dumps({"answer": "yes"})],
        cost=CostModel("neurons", 1, 1, 1e9),
    )
    result = await gateway(settings, session_factory, groq, cloudflare).complete(
        Task.UNDERSTAND, PROMPT, Answer, user_id="u1", fallback=template
    )
    nobody = FakeProvider("groq:test", replies=[ProviderUnavailableError("down")])
    fallback = await gateway(settings, session_factory, nobody).complete(
        Task.UNDERSTAND, PROMPT, Answer, user_id="u2", fallback=template
    )
    off = await gateway(make(ai_llm_enabled=False), session_factory, groq).complete(
        Task.UNDERSTAND, PROMPT, Answer, user_id="u3", fallback=template
    )

    async with session_factory() as db:
        status = await ai_status(db, settings)

    assert result.source is Source.LLM
    assert result.provider == "cloudflare:test"
    assert fallback.source is Source.TEMPLATE
    assert off.source is Source.TEMPLATE
    by_name = {p.name: p for p in status.providers}
    assert by_name["groq:test"].calls == {"unavailable": 2}
    assert by_name["cloudflare:test"].calls == {"ok": 1}
    assert by_name["cloudflare:test"].used_today > 0
    assert status.fallbacks == {"no_provider": 1, "disabled": 1}
    assert status.global_calls_today == 3


async def test_the_health_check_tries_every_provider_on_its_own(
    make: Callable[..., Settings], session_factory: async_sessionmaker[AsyncSession]
) -> None:
    settings = make()
    groq = FakeProvider("groq:test", replies=[json.dumps({"ok": True})])
    cloudflare = FakeProvider("cloudflare:test", replies=[ProviderRateLimitedError(30)])

    results = await gateway(settings, session_factory, groq, cloudflare).probe()
    disabled = await gateway(make(ai_llm_enabled=False), session_factory, groq).probe()
    async with session_factory() as db:
        status = await ai_status(db, settings)

    # Both were asked, even though the first one answered (unlike real calls).
    assert results == {"groq:test": "ok", "cloudflare:test": "rate_limited"}
    assert len(groq.requests) == 1
    assert len(cloudflare.requests) == 1
    assert "synthetic" not in groq.requests[0].user  # fixed text, no user data
    by_name = {p.name: p for p in status.providers}
    assert by_name["groq:test"].probes == {"ok": 1}
    assert by_name["cloudflare:test"].probes == {"rate_limited": 1}
    assert by_name["groq:test"].calls == {}  # health checks are counted apart
    assert disabled == {"all": "disabled"}


# --- the moderation endpoints --------------------------------------------------------------


async def test_moderators_see_provider_names_never_keys(
    make: Callable[..., Settings],
    delivery: CapturingDelivery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    mod_email = new_email()
    settings = make(
        moderator_emails=[mod_email],
        groq_api_key=GROQ_KEY,
        groq_models=["openai/gpt-oss-120b"],
        cloudflare_api_token=CF_TOKEN,
        cloudflare_account_id=CF_ACCOUNT,
        ai_probes_per_day=1,
    )
    async with auth_client(settings, delivery) as client:
        mod = await as_person(client, settings, delivery, mod_email)
        someone = await as_person(client, settings, delivery, new_email())
        status = await client.get("/api/v1/moderation/ai", headers=mod.headers)
        refused = await client.get("/api/v1/moderation/ai", headers=someone.headers)
        probe = await client.post("/api/v1/moderation/ai/probe", headers=mod.headers)
        again = await client.post("/api/v1/moderation/ai/probe", headers=mod.headers)
        refused_probe = await client.post("/api/v1/moderation/ai/probe", headers=someone.headers)

    assert status.status_code == 200, status.text
    body = status.json()
    assert [p["name"] for p in body["providers"]] == [
        "groq:openai/gpt-oss-120b",
        "cloudflare:@cf/openai/gpt-oss-20b",
    ]
    assert body["enabled"] is True
    for secret in (GROQ_KEY, CF_TOKEN, CF_ACCOUNT):
        assert secret not in status.text
    assert refused.status_code == 403
    assert error_code(refused) == "moderator_only"
    assert probe.status_code == 202
    assert again.status_code == 429  # AI_PROBES_PER_DAY = 1
    assert refused_probe.status_code == 403
    queued = run_sql(
        settings.database_url.unicode_string(),
        "SELECT count(*) AS n FROM jobs WHERE kind = 'ai_probe'",
    )[0]["n"]
    assert queued >= 1
