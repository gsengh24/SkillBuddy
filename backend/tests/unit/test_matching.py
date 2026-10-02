"""Ranking maths, diversity and cursors for the matcher (no database)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.stages import Intent, Understanding
from app.models import MatchRequest
from app.services.matching.engine import (
    SEARCH,
    WEIGHTS,
    Ranked,
    Retrieved,
    activity,
    diversify,
    query_text,
    score,
)
from app.services.matching.requests import InvalidCursorError, decode_cursor, encode_cursor

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def candidate(
    fit: float,
    *,
    reciprocity: float | None = None,
    days_ago: float | None = 1,
    vector: list[float] | None = None,
) -> Retrieved:
    return Retrieved(
        user_id=uuid.uuid4(),
        fit=fit,
        reciprocity=reciprocity,
        last_login_at=None if days_ago is None else NOW - timedelta(days=days_ago),
        structured={},
        display_name="",
        vector=vector,
    )


def test_every_intent_has_a_search_and_weights() -> None:
    assert set(SEARCH) == set(Intent) == set(WEIGHTS)


def test_activity_decays_after_a_week_and_is_zero_for_never() -> None:
    assert activity(NOW - timedelta(days=3), NOW) == 1.0
    assert 0 < activity(NOW - timedelta(days=30), NOW) < 1
    assert activity(NOW - timedelta(days=90), NOW) == 0.0
    assert activity(None, NOW) == 0.0


def test_reciprocity_uses_the_weaker_side() -> None:
    weights = WEIGHTS[Intent.SKILL_EXCHANGE]
    one_sided = candidate(0.9, reciprocity=0.1)
    two_sided = candidate(0.8, reciprocity=0.8)
    better = score(two_sided, weights, now=NOW, seen_before=False, recent_suggestions=0)
    worse = score(one_sided, weights, now=NOW, seen_before=False, recent_suggestions=0)
    assert better > worse


def test_novelty_and_overexposure_move_the_score() -> None:
    weights = WEIGHTS[Intent.BUILD_TOGETHER]
    c = candidate(0.7)
    fresh = score(c, weights, now=NOW, seen_before=False, recent_suggestions=0)
    seen = score(c, weights, now=NOW, seen_before=True, recent_suggestions=0)
    flooded = score(c, weights, now=NOW, seen_before=False, recent_suggestions=40)
    assert fresh > seen
    assert fresh > flooded


def test_diversify_skips_near_copies() -> None:
    a = Ranked(candidate(0.9, vector=[1.0, 0.0]), 0.90)
    a_copy = Ranked(candidate(0.9, vector=[0.999, 0.01]), 0.89)
    different = Ranked(candidate(0.6, vector=[0.0, 1.0]), 0.80)
    chosen = diversify([a, a_copy, different], 2)
    assert chosen == [a, different]


def test_query_text_leads_with_the_phrases_for_the_intent() -> None:
    understood = Understanding(seeks=["a designer"], interests=["chess"])
    assert query_text("Hi", understood, SEARCH[Intent.BUILD_TOGETHER]).startswith("a designer")
    assert query_text("Hi", understood, SEARCH[Intent.INTEREST_BUDDY]).startswith("chess")
    assert query_text("Hi", understood, SEARCH[Intent.EXPLORE]) == "Hi"


def test_cursor_round_trip_and_rejects_garbage() -> None:
    request = MatchRequest(id=uuid.uuid4(), created_at=NOW)
    assert decode_cursor(encode_cursor(request)) == (NOW, request.id)
    for bad in ("not-a-cursor", "!!!", encode_cursor(request)[:-6]):
        with pytest.raises(InvalidCursorError):
            decode_cursor(bad)
