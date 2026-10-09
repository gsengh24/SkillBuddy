"""The Understand and Explain stages through the real gateway, fake providers and Postgres.

No test calls a real AI provider.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.candidates import CandidateSummary
from app.ai.gateway import AIGateway, FallbackReason, Source
from app.ai.prompts import load_prompt
from app.ai.providers import ChatProvider, FakeProvider
from app.ai.stages import Candidate, Intent, Understanding, explain, understand
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from tests.conftest import SettingsFactory
from tests.integration.conftest import run_sql

TEXT = (
    "I'm Aarav Sharma, mail aarav.s@thapar.edu. I can build React apps. "
    "Looking for a designer to build a side project with."
)


@pytest.fixture
async def session_factory(
    integration_settings: Settings, migrated_database_url: str
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    run_sql(migrated_database_url, "DELETE FROM rate_limit_counters WHERE key LIKE 'ai:%'")
    engine = create_engine(integration_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _gateway(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    providers: Sequence[ChatProvider],
) -> AIGateway:
    return AIGateway(settings, session_factory, providers, cooling_until={})


def _fake(*replies: str) -> FakeProvider:
    return FakeProvider(name=f"groq-{uuid.uuid4().hex[:6]}", replies=list(replies))


def _candidates(count: int) -> list[Candidate]:
    return [
        Candidate(
            CandidateSummary(
                user_id=uuid.uuid4(),
                skills=[f"skill {i}", "Figma"] if i == 2 else [f"skill {i}"],
                name_hints=[f"Person{i}"],
            ),
            score=1.0 - i / 100,
        )
        for i in range(count)
    ]


async def test_understand_uses_the_model_and_sends_no_contact_details(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    reply = {
        "intent": "build_together",
        "title": "React developer",
        "summary": "Builds React apps.",
        "offers": ["React"],
    }
    groq = _fake(json.dumps(reply))
    result = await understand(
        _gateway(settings, session_factory, [groq]),
        TEXT,
        user_id=str(uuid.uuid4()),
        name_hints=["Aarav Sharma"],
    )

    assert result.source is Source.LLM
    assert result.value.intent is Intent.BUILD_TOGETHER
    assert result.value.offers == ["React"]
    assert result.value.title == "React developer"
    sent = groq.requests[0]
    assert sent.system.startswith(load_prompt("understand_v2"))
    for leaked in ("Aarav", "Sharma", "aarav.s@thapar.edu"):
        assert leaked not in sent.user


async def test_understand_falls_back_to_the_template_with_ai_off(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_llm_enabled=False)
    groq = _fake("{}")
    result = await understand(
        _gateway(settings, session_factory, [groq]),
        TEXT,
        user_id=str(uuid.uuid4()),
        name_hints=["Aarav Sharma"],
    )

    assert (result.source, result.reason) == (Source.TEMPLATE, FallbackReason.DISABLED)
    assert groq.requests == []
    assert result.value.intent is Intent.BUILD_TOGETHER
    assert result.value.seeks == ["designer to build a side project with"]
    # The template reads redacted text too.
    assert "aarav" not in result.value.summary.lower()


async def test_understand_invalid_output_twice_uses_the_template(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    bad = json.dumps({"intent": "romance"})
    groq = _fake(bad, bad)
    result = await understand(
        _gateway(settings, session_factory, [groq]), TEXT, user_id=str(uuid.uuid4())
    )
    assert result.source is Source.TEMPLATE
    assert len(groq.requests) == 2


async def test_explain_maps_aliases_and_drops_unknown_or_repeated_ids(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    candidates = _candidates(20)
    verdicts = [
        {"id": "C3", "need": 3, "shared": 2, "reason": "Designs in Figma, which you need."},
        {"id": "C99", "need": 3, "shared": 3, "reason": "An id that was never sent."},
        {"id": "C3", "need": 0, "shared": 0, "reason": "The same candidate again."},
        {"id": "C1", "need": 2, "shared": 1, "reason": "Works on similar projects."},
    ]
    groq = _fake(json.dumps({"verdicts": verdicts}))
    result = await explain(
        _gateway(settings, session_factory, [groq]),
        TEXT,
        Understanding(seeks=["designer"]),
        candidates,
        user_id=str(uuid.uuid4()),
        name_hints=["Aarav Sharma"],
    )

    assert result.source is Source.LLM
    assert result.prompt_version == "explain_v2"
    assert [(p.user_id, p.reason) for p in result.picks] == [
        (candidates[2].summary.user_id, "Designs in Figma, which you need."),
        (candidates[0].summary.user_id, "Works on similar projects."),
    ]
    sent = json.loads(groq.requests[0].user)
    assert [c["id"] for c in sent["candidates"]] == [f"C{i}" for i in range(1, 16)]
    body = groq.requests[0].user
    for secret in ("Aarav", "Person2", *(str(c.summary.user_id) for c in candidates)):
        assert secret not in body


async def test_explain_with_no_usable_pick_uses_the_template(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    candidates = _candidates(6)
    groq = _fake(json.dumps({"verdicts": [{"id": "C42", "need": 3, "shared": 3}]}))
    result = await explain(
        _gateway(settings, session_factory, [groq]),
        TEXT,
        Understanding(seeks=["Figma"]),
        candidates,
        user_id=str(uuid.uuid4()),
        max_picks=3,
    )

    assert result.source is Source.TEMPLATE
    assert result.prompt_version is None
    assert [p.user_id for p in result.picks] == [c.summary.user_id for c in candidates[:3]]
    assert result.picks[2].reason == "They offer Figma, which you are looking for."


async def test_explain_keeps_only_candidates_the_judge_rates_well_enough(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    candidates = _candidates(6)  # best-scored first: C1 has the highest score from ranking
    verdicts = [
        # The ranking's favourite, but only loosely related: dropped.
        {"id": "C1", "need": 1, "shared": 1, "reason": "A loose overlap at best."},
        {"id": "C2", "need": 2, "shared": 1},  # good enough, but no reason given
        {"id": "C3", "need": 3, "shared": 3, "reason": "Designs in Figma, which you need."},
        # A perfect fit on paper whose summary contradicts the request: dropped.
        {"id": "C4", "need": 3, "shared": 3, "conflict": True, "reason": "Not taking this on."},
        {"id": "C5", "need": 0, "shared": 0},
        # C6 is not judged at all: dropped.
    ]
    reply = json.dumps({"verdicts": verdicts})
    result = await explain(
        _gateway(settings, session_factory, [_fake(reply)]),
        TEXT,
        Understanding(seeks=["Figma"]),
        candidates,
        user_id=str(uuid.uuid4()),
    )

    assert result.source is Source.LLM
    # Ordered by the judge first, not by the ranking; the template fills a missing reason.
    assert [(p.user_id, p.reason) for p in result.picks] == [
        (candidates[2].summary.user_id, "Designs in Figma, which you need."),
        (candidates[1].summary.user_id, "A close match for what you described."),
    ]

    # At most max_picks. With the floor off everyone judged is kept, bar the conflict.
    result = await explain(
        _gateway(settings, session_factory, [_fake(reply)]),
        TEXT,
        Understanding(seeks=["Figma"]),
        candidates,
        user_id=str(uuid.uuid4()),
        max_picks=1,
    )
    assert [p.user_id for p in result.picks] == [candidates[2].summary.user_id]
    result = await explain(
        _gateway(settings, session_factory, [_fake(reply)]),
        TEXT,
        Understanding(seeks=["Figma"]),
        candidates,
        user_id=str(uuid.uuid4()),
        min_judged=0,
    )
    assert [p.user_id for p in result.picks] == [
        candidates[i].summary.user_id for i in (2, 1, 0, 4)
    ]


async def test_explain_when_the_judge_finds_nobody_good_enough(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    candidates = _candidates(3)
    verdicts = [{"id": f"C{i}", "need": 1, "shared": 0} for i in (1, 2, 3)]
    result = await explain(
        _gateway(settings, session_factory, [_fake(json.dumps({"verdicts": verdicts}))]),
        TEXT,
        Understanding(seeks=["Figma"]),
        candidates,
        user_id=str(uuid.uuid4()),
    )
    # The judge answered and nobody passed: no picks, and no fall back to the template.
    assert (result.picks, result.source, result.prompt_version) == ([], Source.LLM, "explain_v2")


async def test_explain_with_ai_off_and_no_candidates(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=migrated_database_url, ai_llm_enabled=False)
    groq = _fake("{}")
    gateway = _gateway(settings, session_factory, [groq])
    empty = await explain(gateway, TEXT, Understanding(), [], user_id=str(uuid.uuid4()))
    assert (empty.picks, empty.source) == ([], Source.TEMPLATE)

    off = await explain(gateway, TEXT, Understanding(), _candidates(2), user_id=str(uuid.uuid4()))
    assert off.source is Source.TEMPLATE
    assert len(off.picks) == 2
    assert groq.requests == []
