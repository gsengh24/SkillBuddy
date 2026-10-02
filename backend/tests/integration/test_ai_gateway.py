"""Contract tests for the AI gateway with fake providers and real PostgreSQL counters.

No test calls a real AI provider.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import budget
from app.ai import gateway as gateway_module
from app.ai.gateway import AIGateway, FallbackReason, Prompt, Source, Task
from app.ai.providers import (
    GROQ_BASE_URL,
    ChatProvider,
    CostModel,
    FakeProvider,
    OpenAICompatibleProvider,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from tests.conftest import SettingsFactory
from tests.integration.conftest import run_sql

OK = json.dumps({"answer": "yes"})
PERSONAL = {
    "about": (
        "I'm Aarav Sharma. Mail aarav.s@thapar.edu, call +91 98765 43210, "
        "see github.com/aaravs or https://aarav.dev, insta @aarav.codes"
    ),
    "skills": ["Python", "ping me at 9876543210"],
}
STRIPPED = [
    "Aarav",
    "Sharma",
    "aarav.s@thapar.edu",
    "98765",
    "9876543210",
    "github.com",
    "aarav.dev",
    "@aarav.codes",
]


class Answer(BaseModel):
    answer: str


def template() -> Answer:
    return Answer(answer="template")


@pytest.fixture
async def session_factory(
    integration_settings: Settings, migrated_database_url: str
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # AI counters are per UTC day and shared by the whole test database: start clean.
    run_sql(migrated_database_url, "DELETE FROM rate_limit_counters WHERE key LIKE 'ai:%'")
    engine = create_engine(integration_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url)


def _gateway(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    providers: Sequence[ChatProvider],
) -> AIGateway:
    return AIGateway(settings, session_factory, providers, cooling_until={})


def _fake(name: str, *replies: Any, **kwargs: Any) -> FakeProvider:
    return FakeProvider(name=f"{name}-{uuid.uuid4().hex[:6]}", replies=list(replies), **kwargs)


async def _ask(gateway: AIGateway, user: str | None = None, data: Any = None) -> Any:
    return await gateway.complete(
        Task.SELECT,
        Prompt(
            version="test-v1", system="Pick.", data=data or {"q": "hi"}, name_hints=["Aarav Sharma"]
        ),
        Answer,
        user_id=user or str(uuid.uuid4()),
        fallback=template,
    )


# --- happy path and privacy ------------------------------------------------------------


async def test_first_provider_answers_with_schema_validated_output(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    groq = _fake("groq", OK)
    result = await _ask(_gateway(settings, session_factory, [groq, _fake("cloudflare", OK)]))

    assert result.value == Answer(answer="yes")
    assert (result.source, result.provider, result.reason) == (Source.LLM, groq.name, None)


async def test_stripped_data_never_appears_in_the_outgoing_request(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Checked on the exact HTTP bytes a real provider client would send."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": OK}}]})

    key = "gsk_contract_" + "x" * 32
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            provider="groq",
            base_url=GROQ_BASE_URL,
            api_key=SecretStr(key),
            model="openai/gpt-oss-120b",
            cost=CostModel("tokens", 1, 1, 1e9),
            client=client,
        )
        result = await _ask(_gateway(settings, session_factory, [provider]), data=PERSONAL)

    assert result.source is Source.LLM
    body = captured[0].content.decode()
    for value in STRIPPED:
        assert value.lower() not in body.lower(), value
    for token in ("[name]", "[email]", "[phone]", "[link]", "[handle]"):
        assert token in body
    assert key not in body
    # Untrusted text travels as quoted JSON data, never as instructions.
    user_message = json.loads(body)["messages"][1]["content"]
    assert json.loads(user_message)["skills"][0] == "Python"


async def test_nothing_is_sent_if_stripping_ever_misses(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_module, "redact", lambda text, names=(): text)  # broken redaction
    groq = _fake("groq", OK)
    result = await _ask(_gateway(settings, session_factory, [groq]), data=PERSONAL)

    assert (result.source, result.reason) == (Source.TEMPLATE, FallbackReason.PRIVACY)
    assert groq.requests == []


# --- fallback order -------------------------------------------------------------------


async def test_rate_limited_groq_falls_back_to_cloudflare_and_cools_down(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    groq = _fake("groq", ProviderRateLimitedError(30), OK)
    cloudflare = _fake("cloudflare", OK, OK)
    gateway = _gateway(settings, session_factory, [groq, cloudflare])

    first = await _ask(gateway)
    second = await _ask(gateway)

    assert first.provider == cloudflare.name
    assert second.provider == cloudflare.name
    assert len(groq.requests) == 1  # skipped while cooling down after the 429


async def test_timeout_moves_to_the_next_provider(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_llm_timeout_seconds=0.1)
    slow = _fake("groq", OK, delay_seconds=2)
    cloudflare = _fake("cloudflare", OK)

    started = asyncio.get_running_loop().time()
    result = await _ask(_gateway(settings, session_factory, [slow, cloudflare]))

    assert result.provider == cloudflare.name
    assert asyncio.get_running_loop().time() - started < 1.5


def test_default_timeout_is_twenty_seconds(settings: Settings) -> None:
    assert settings.ai_llm_timeout_seconds == 20


async def test_all_providers_failing_uses_the_template(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    groq = _fake("groq", ProviderUnavailableError("HTTP 503"))
    cloudflare = _fake("cloudflare", ProviderUnavailableError("HTTP 500"))
    result = await _ask(_gateway(settings, session_factory, [groq, cloudflare]))

    assert result.value == template()
    assert (result.source, result.reason) == (Source.TEMPLATE, FallbackReason.NO_PROVIDER)


async def test_no_configured_provider_uses_the_template(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    result = await _ask(_gateway(settings, session_factory, []))
    assert result.reason is FallbackReason.NO_PROVIDER


async def test_invalid_output_gets_one_retry_then_the_next_provider(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    groq = _fake("groq", "not json", '{"wrong": 1}')
    cloudflare = _fake("cloudflare", OK)
    with caplog.at_level(logging.WARNING, logger="app.ai.gateway"):
        result = await _ask(_gateway(settings, session_factory, [groq, cloudflare]))

    assert len(groq.requests) == 2
    assert result.provider == cloudflare.name
    assert any(r.levelno == logging.ERROR for r in caplog.records)  # fails loudly


# --- kill switch and caps -------------------------------------------------------------


async def test_kill_switch_sends_nothing(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_llm_enabled=False)
    groq = _fake("groq", OK)
    result = await _ask(_gateway(settings, session_factory, [groq]))

    assert (result.source, result.reason) == (Source.TEMPLATE, FallbackReason.DISABLED)
    assert groq.requests == []


async def test_per_user_daily_cap(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_user_daily_match_requests=2)
    gateway = _gateway(settings, session_factory, [_fake("groq", OK, OK, OK, OK)])
    user = str(uuid.uuid4())

    results = [await _ask(gateway, user) for _ in range(3)]
    other_user = await _ask(gateway)

    assert [r.source for r in results] == [Source.LLM, Source.LLM, Source.TEMPLATE]
    assert results[2].reason is FallbackReason.USER_CAP
    assert other_user.source is Source.LLM


async def test_overall_daily_cap(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_llm_daily_call_cap=1)
    groq = _fake("groq", OK, OK)
    gateway = _gateway(settings, session_factory, [groq])

    first, second = await _ask(gateway), await _ask(gateway)

    assert first.source is Source.LLM
    assert (second.source, second.reason) == (Source.TEMPLATE, FallbackReason.GLOBAL_CAP)
    assert len(groq.requests) == 1


async def test_per_provider_daily_budget_moves_on_to_the_next(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    small = CostModel("tokens", 1, 1, daily_budget=100)
    groq = _fake("groq", OK, OK, cost=small, tokens=(100, 50))  # one call uses 150 tokens
    cloudflare = _fake("cloudflare", OK)
    gateway = _gateway(settings, session_factory, [groq, cloudflare])

    first, second = await _ask(gateway), await _ask(gateway)

    assert first.provider == groq.name
    assert second.provider == cloudflare.name
    assert len(groq.requests) == 1


# --- counters in PostgreSQL ------------------------------------------------------------


async def test_counters_are_postgres_rows_per_utc_day(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
) -> None:
    groq = _fake("groq", OK)
    await _ask(_gateway(settings, session_factory, [groq]))

    rows = run_sql(
        migrated_database_url,
        "SELECT key, count, window_start, expires_at FROM rate_limit_counters "
        "WHERE key LIKE 'ai:%' ORDER BY key",
    )
    keys = {row["key"]: row for row in rows}
    assert keys["ai:global:calls"]["count"] == 1
    assert keys[f"ai:provider:{groq.name}:tokens"]["count"] == 150
    assert any(key.startswith("ai:user:select:") for key in keys)
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    for row in rows:
        assert row["window_start"] == today
        assert row["expires_at"] == today + timedelta(days=1)


async def test_cap_is_never_exceeded_under_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = f"ai:test:{uuid.uuid4().hex}"

    async def one() -> bool:
        async with session_factory() as db:
            return await budget.try_consume(db, key, limit=5)

    results = await asyncio.gather(*(one() for _ in range(12)))

    assert sum(results) == 5
    async with session_factory() as db:
        assert await budget.used(db, key) == 5


async def test_counters_reset_each_utc_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = f"ai:test:{uuid.uuid4().hex}"
    day1 = datetime(2026, 10, 2, 23, 59, tzinfo=UTC)
    async with session_factory() as db:
        assert await budget.try_consume(db, key, limit=1, now=day1)
        assert not await budget.try_consume(db, key, limit=1, now=day1)
        assert await budget.try_consume(db, key, limit=1, now=day1 + timedelta(minutes=2))
