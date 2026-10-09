"""The matcher for one request: understand, retrieve, rank, explain (ARCHITECTURE.md §3).

Runs in the ``match_request`` job, never in a request handler. Every stage works with the
AI off: the Understand and Explain stages fall back to their templates, and retrieval and
ranking never use an LLM.

- **Retrieve (hybrid):** the request is embedded once (as a query) and compared with one
  facet of every matchable profile, chosen by intent (``SEARCH``). A second, keyword search
  finds people whose words for that facet share word stems with the request, so an exact
  skill is not lost when its vector is not among the nearest. Hard filters: not yourself,
  only active accounts, only profiles that are "matchable", only current-model vectors.
- **Rank:** in code, never by the model (ARCHITECTURE.md §7, guardrails):
  ``relevance = rescaled two-sided fit + KEYWORD_WEIGHT * keyword`` and
  ``score = relevance * (1 - penalties)``, where the penalties (inactive, seen before,
  overexposed) only take a share of the relevance away: they order close candidates and
  never lift a poor fit over a good one. Hand-set weights per intent. "Explore" then picks
  a diverse set with maximal marginal relevance.
- **Gate:** a candidate whose relevance is under ``MATCH_MIN_RELEVANCE`` is not suggested.
  Too few good people means fewer matches, or none, never weak ones.
- **Explain:** the best 15 go, anonymised, to ``explain()``. With the AI on, the model
  judges each one on a rubric and code keeps up to ``MATCHES_PER_REQUEST`` of those at or
  above ``MATCH_MIN_JUDGE_SCORE``; with it off, the template keeps the top of the ranking.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.candidates import MAX_CANDIDATES, CandidateSummary
from app.ai.embeddings import Embedder
from app.ai.gateway import AIGateway
from app.ai.stages import Candidate, Intent, Understanding, explain, understand
from app.core.config import Settings
from app.models import (
    EmbeddingFacet,
    Match,
    MatchRequest,
    MatchStatus,
    NotificationKind,
    Profile,
    RequestStatus,
)
from app.services.notifications import add_notification

logger = logging.getLogger(__name__)

RETRIEVE_LIMIT: Final = 60
OVEREXPOSURE_DAYS: Final = 7
# Suggested this many times in a week counts as fully overexposed.
OVEREXPOSURE_SATURATION: Final = 15
ACTIVITY_HORIZON_DAYS: Final = 60
MMR_LAMBDA: Final = 0.7
# Cosines of this embedding model sit in a narrow band (evals/README.md: poor pairs average
# 0.52, good ones 0.61), so fit is rescaled: FIT_FLOOR and below count 0, FIT_CEILING and
# above count 1.
FIT_FLOOR: Final = 0.45
FIT_CEILING: Final = 0.75
# What full keyword overlap adds to relevance.
KEYWORD_WEIGHT: Final = 0.25


@dataclass(frozen=True)
class Search:
    """Which request text to embed, which candidate facet to compare it with."""

    query: str  # "seeks", "interests" or "all"
    facet: EmbeddingFacet
    # Score the other side too: their "seek" against my "offer".
    reciprocal: bool
    # The key of ``profiles.structured`` the keyword search reads (None: all of it). Goes
    # into the SQL as written, so only ever a constant from ``SEARCH``.
    keyword_source: str | None = None


SEARCH: Final[dict[Intent, Search]] = {
    Intent.BUILD_TOGETHER: Search(
        "seeks", EmbeddingFacet.OFFER, reciprocal=True, keyword_source="offers"
    ),
    Intent.SKILL_EXCHANGE: Search(
        "seeks", EmbeddingFacet.OFFER, reciprocal=True, keyword_source="offers"
    ),
    Intent.MENTOR: Search("seeks", EmbeddingFacet.OFFER, reciprocal=False, keyword_source="offers"),
    Intent.INTEREST_BUDDY: Search(
        "interests", EmbeddingFacet.INTEREST, reciprocal=False, keyword_source="interests"
    ),
    Intent.ACCOUNTABILITY: Search("all", EmbeddingFacet.IDENTITY, reciprocal=False),
    Intent.EXPLORE: Search("all", EmbeddingFacet.IDENTITY, reciprocal=False),
}


@dataclass(frozen=True)
class Weights:
    """``fit`` and ``reciprocity`` blend the two sides of the fit; the other three are the
    largest share of the relevance each penalty can take away."""

    fit: float
    reciprocity: float
    activity: float
    novelty: float
    overexposure: float


WEIGHTS: Final[dict[Intent, Weights]] = {
    Intent.BUILD_TOGETHER: Weights(0.55, 0.25, 0.10, 0.10, 0.15),
    Intent.SKILL_EXCHANGE: Weights(0.40, 0.40, 0.10, 0.10, 0.15),
    Intent.MENTOR: Weights(0.70, 0.00, 0.15, 0.15, 0.20),
    Intent.INTEREST_BUDDY: Weights(0.70, 0.00, 0.15, 0.15, 0.15),
    Intent.ACCOUNTABILITY: Weights(0.60, 0.00, 0.25, 0.15, 0.15),
    Intent.EXPLORE: Weights(0.50, 0.00, 0.15, 0.35, 0.15),
}


@dataclass(frozen=True)
class Retrieved:
    user_id: uuid.UUID
    fit: float
    reciprocity: float | None
    last_login_at: datetime | None
    structured: dict[str, Any]
    display_name: str
    vector: list[float] | None
    # The share of the request's word stems found in their text for this facet (0 to 1).
    keyword: float = 0.0


@dataclass(frozen=True)
class Ranked:
    candidate: Retrieved
    score: float
    # The fit alone, before the penalties: what the gate reads.
    relevance: float = 1.0


def query_text(raw_text: str, understanding: Understanding, search: Search) -> str:
    """The request text, with the phrases that matter for this intent repeated first."""
    if search.query == "seeks" and understanding.seeks:
        return f"{'; '.join(understanding.seeks)}. {raw_text}"
    if search.query == "interests" and understanding.interests:
        return f"{'; '.join(understanding.interests)}. {raw_text}"
    return raw_text


def keyword_text(raw_text: str, understanding: Understanding, search: Search) -> str:
    """The words the keyword search looks for: the phrases for this intent, else the request."""
    if search.query == "seeks" and understanding.seeks:
        return " ".join(understanding.seeks)
    if search.query == "interests" and understanding.interests:
        return " ".join(understanding.interests)
    return raw_text


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"


def _keyword_document(search: Search) -> str:
    """SQL for the word stems of a profile's text for this facet.

    Like the facet embeddings (``facet_texts``), a profile without parsed text for the
    facet falls back to its own words.
    """
    source = (
        "p.structured"
        if search.keyword_source is None
        else f"p.structured->'{search.keyword_source}'"
    )
    return (
        f"COALESCE(NULLIF(jsonb_to_tsvector(CAST('english' AS regconfig), {source}, "
        """CAST('["string"]' AS jsonb)), CAST('' AS tsvector)), """
        "to_tsvector(CAST('english' AS regconfig), p.raw_about_text))"
    )


async def retrieve(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
    query_vector: Sequence[float],
    keywords: str,
    search: Search,
    model_version: str,
    with_vectors: bool,
    limit: int = RETRIEVE_LIMIT,
) -> list[Retrieved]:
    """Hybrid retrieval on one facet: the nearest vectors, plus the best keyword overlaps.

    Both searches apply the hard filters in SQL and score every row the same way, so a
    person found by both is one candidate.
    """
    found: dict[uuid.UUID, Retrieved] = {}
    for by_keyword in (False, True):
        for candidate in await _search(
            db,
            requester_id=requester_id,
            query_vector=query_vector,
            keywords=keywords,
            search=search,
            model_version=model_version,
            with_vectors=with_vectors,
            limit=limit,
            by_keyword=by_keyword,
        ):
            found.setdefault(candidate.user_id, candidate)
    return list(found.values())


async def _search(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
    query_vector: Sequence[float],
    keywords: str,
    search: Search,
    model_version: str,
    with_vectors: bool,
    limit: int,
    by_keyword: bool,
) -> list[Retrieved]:
    """One leg of retrieval: ordered by vector distance, or by keyword overlap."""
    reciprocity = (
        "(SELECT 1 - (their_seek.embedding <=> my_offer.embedding) "
        " FROM profile_embeddings their_seek, profile_embeddings my_offer "
        " WHERE their_seek.user_id = pe.user_id AND their_seek.facet = 'seek' "
        "   AND my_offer.user_id = :me AND my_offer.facet = 'offer')"
        if search.reciprocal
        else "NULL"
    )
    vector_column = ", pe.embedding::text AS vector" if with_vectors else ""
    request_stems = (
        "tsvector_to_array(to_tsvector(CAST('english' AS regconfig), CAST(:keywords AS text)))"
    )
    candidates = (
        f"SELECT pe.user_id, 1 - (pe.embedding <=> CAST(:q AS vector)) AS fit, "  # noqa: S608  # fixed fragments, values are bound
        f"{reciprocity} AS reciprocity, u.last_login_at, p.structured, p.display_name"
        f"{vector_column}, "
        f"(SELECT count(*) FROM unnest(tsvector_to_array({_keyword_document(search)})) AS stem "
        f" WHERE stem = ANY({request_stems})) AS stems_shared, "
        f"cardinality({request_stems}) AS stems_asked "
        "FROM profile_embeddings pe "
        "JOIN profiles p ON p.user_id = pe.user_id "
        "JOIN users u ON u.id = pe.user_id "
        "WHERE pe.facet = :facet AND pe.model_version = :model AND pe.user_id <> :me "
        "AND u.status = 'active' AND p.visibility = 'matchable' "
        # Blocks work both ways (app/services/blocks.py).
        "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE "
        "(b.blocker_id = :me AND b.blocked_id = pe.user_id) OR "
        "(b.blocker_id = pe.user_id AND b.blocked_id = :me)) "
    )
    statement = (
        f"SELECT * FROM ({candidates}) AS found WHERE stems_shared > 0 "  # noqa: S608  # fixed fragments, values are bound
        "ORDER BY stems_shared DESC, fit DESC LIMIT :limit"
        if by_keyword
        else f"{candidates} ORDER BY pe.embedding <=> CAST(:q AS vector) LIMIT :limit"
    )
    parameters: dict[str, Any] = {
        "q": _vector_literal(query_vector),
        "keywords": keywords,
        "facet": search.facet.value,
        "model": model_version,
        "me": requester_id,
        "limit": limit,
    }
    rows = await db.execute(text(statement), parameters)
    found: list[Retrieved] = []
    for row in rows.mappings():
        stems_asked = int(row["stems_asked"] or 0)
        found.append(
            Retrieved(
                user_id=row["user_id"],
                fit=float(row["fit"]),
                reciprocity=None if row["reciprocity"] is None else float(row["reciprocity"]),
                last_login_at=row["last_login_at"],
                structured=dict(row["structured"] or {}),
                display_name=row["display_name"] or "",
                vector=json.loads(row["vector"]) if with_vectors else None,
                keyword=int(row["stems_shared"]) / stems_asked if stems_asked else 0.0,
            )
        )
    return found


def activity(last_login_at: datetime | None, now: datetime) -> float:
    """1 if seen this week, falling to 0 at ACTIVITY_HORIZON_DAYS; 0 if never."""
    if last_login_at is None:
        return 0.0
    days = max(0.0, (now - last_login_at).total_seconds() / 86_400)
    if days <= 7:
        return 1.0
    return max(0.0, 1.0 - (days - 7) / (ACTIVITY_HORIZON_DAYS - 7))


def relevance(candidate: Retrieved, weights: Weights) -> float:
    """How well they fit the request, 0 to 1: the rescaled two-sided fit plus keyword overlap."""
    two_sided = (
        min(candidate.fit, candidate.reciprocity)
        if candidate.reciprocity is not None
        else candidate.fit
    )
    two_sided_share = weights.reciprocity / (weights.fit + weights.reciprocity)
    blended = candidate.fit + two_sided_share * (two_sided - candidate.fit)
    semantic = min(1.0, max(0.0, (blended - FIT_FLOOR) / (FIT_CEILING - FIT_FLOOR)))
    return min(1.0, semantic + KEYWORD_WEIGHT * candidate.keyword)


def score(
    candidate: Retrieved,
    weights: Weights,
    *,
    now: datetime,
    seen_before: bool,
    recent_suggestions: int,
) -> float:
    """Relevance, less a share for being inactive, seen before or suggested a lot lately."""
    overexposure = min(1.0, recent_suggestions / OVEREXPOSURE_SATURATION)
    penalties = (
        weights.activity * (1.0 - activity(candidate.last_login_at, now))
        + weights.novelty * (1.0 if seen_before else 0.0)
        + weights.overexposure * overexposure
    )
    return relevance(candidate, weights) * (1.0 - penalties)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def diversify(ranked: list[Ranked], count: int, *, lam: float = MMR_LAMBDA) -> list[Ranked]:
    """Maximal marginal relevance: good matches that are not near-copies of each other."""
    pool = [item for item in ranked if item.candidate.vector is not None]
    chosen: list[Ranked] = []
    while pool and len(chosen) < count:

        def gain(item: Ranked) -> float:
            if not chosen:
                return item.score
            similarity = max(
                _cosine(item.candidate.vector or [], other.candidate.vector or [])
                for other in chosen
            )
            return lam * item.score - (1 - lam) * similarity

        best = max(pool, key=gain)
        chosen.append(best)
        pool.remove(best)
    return chosen


async def _history(
    db: AsyncSession, requester_id: uuid.UUID, request_id: uuid.UUID, ids: list[uuid.UUID]
) -> tuple[set[uuid.UUID], dict[uuid.UUID, int]]:
    """Who this person was shown before, and how often each candidate was shown lately."""
    if not ids:
        return set(), {}
    seen = set(
        await db.scalars(
            select(Match.candidate_id)
            .join(MatchRequest, MatchRequest.id == Match.request_id)
            .where(
                MatchRequest.user_id == requester_id,
                MatchRequest.id != request_id,
                Match.candidate_id.in_(ids),
            )
        )
    )
    since = func.now() - text(f"interval '{OVEREXPOSURE_DAYS} days'")
    counts: dict[uuid.UUID, int] = {
        key: int(value)
        for key, value in (
            await db.execute(
                select(Match.candidate_id, func.count())
                .where(Match.candidate_id.in_(ids), Match.created_at > since)
                .group_by(Match.candidate_id)
            )
        )
        .tuples()
        .all()
    }
    return seen, counts


def _summary(candidate: Retrieved) -> CandidateSummary:
    data = candidate.structured

    def items(key: str) -> list[str]:
        value = data.get(key)
        return [str(v) for v in value] if isinstance(value, list) else []

    return CandidateSummary(
        user_id=candidate.user_id,
        skills=items("offers"),
        interests=items("interests"),
        goals=items("seeks"),
        availability=str(data.get("availability", "")),
        name_hints=[candidate.display_name] if candidate.display_name else [],
    )


async def run_match_request(
    session_factory: async_sessionmaker[AsyncSession],
    gateway: AIGateway,
    embedder: Embedder,
    settings: Settings,
    request_id: uuid.UUID,
) -> bool:
    """Find, rank, explain and store matches for one pending request. Idempotent.

    Returns False when there was nothing to do (already done, closed or deleted).
    """
    async with session_factory() as db:
        request = await db.get(MatchRequest, request_id)
        if request is None or request.status != RequestStatus.PENDING:
            return False
        profile = await db.get(Profile, request.user_id)
        raw_text = request.raw_text
        requester_id = request.user_id
        requested_intent = request.requested_intent
        names = [profile.display_name] if profile and profile.display_name.strip() else []

    # --- 1. understand (AI, or the template) -----------------------------------------------
    understood = await understand(gateway, raw_text, user_id=str(requester_id), name_hints=names)
    understanding = understood.value
    intent = (
        Intent(requested_intent) if requested_intent else understanding.intent or Intent.EXPLORE
    )
    search = SEARCH[intent]

    # --- 2. retrieve -----------------------------------------------------------------------
    [query_vector] = await embedder.embed(
        [query_text(raw_text, understanding, search)], kind="query"
    )
    now = datetime.now(UTC)
    async with session_factory() as db:
        found = await retrieve(
            db,
            requester_id=requester_id,
            query_vector=query_vector,
            keywords=keyword_text(raw_text, understanding, search),
            search=search,
            model_version=embedder.model_version,
            with_vectors=intent is Intent.EXPLORE,
        )
        seen, counts = await _history(db, requester_id, request_id, [c.user_id for c in found])

    # --- 3. rank, and drop anyone who is not a good enough fit -----------------------------
    weights = WEIGHTS[intent]
    ranked = sorted(
        (
            Ranked(
                c,
                score(
                    c,
                    weights,
                    now=now,
                    seen_before=c.user_id in seen,
                    recent_suggestions=counts.get(c.user_id, 0),
                ),
                relevance(c, weights),
            )
            for c in found
        ),
        # Fits above FIT_CEILING all count the same, so the raw fit settles ties.
        key=lambda item: (item.score, item.candidate.fit),
        reverse=True,
    )
    ranked = [item for item in ranked if item.relevance >= settings.match_min_relevance]
    if intent is Intent.EXPLORE:
        ranked = diversify(ranked, MAX_CANDIDATES)
    shortlist = ranked[:MAX_CANDIDATES]

    # --- 4. explain (AI, or the template) ----------------------------------------------------
    explanation = await explain(
        gateway,
        raw_text,
        understanding,
        [Candidate(_summary(item.candidate), item.score) for item in shortlist],
        user_id=str(requester_id),
        name_hints=names,
        max_picks=settings.matches_per_request,
        min_judged=settings.match_min_judge_score,
    )
    scores = {item.candidate.user_id: item.score for item in shortlist}

    async with session_factory() as db:
        request = await db.get(MatchRequest, request_id, with_for_update=True)
        if request is None or request.status != RequestStatus.PENDING:
            return False  # closed or deleted while we worked
        # A retried job replaces anything a failed attempt left behind.
        await db.execute(delete(Match).where(Match.request_id == request_id))
        for rank, pick in enumerate(explanation.picks, start=1):
            db.add(
                Match(
                    request_id=request_id,
                    candidate_id=pick.user_id,
                    rank=rank,
                    score=round(scores.get(pick.user_id, 0.0), 6),
                    reason=pick.reason[:300],
                    status=MatchStatus.SHOWN,
                )
            )
        request.intent = intent.value
        request.structured = {
            **understanding.facets(),
            "availability": understanding.availability,
        }
        request.explanation_source = explanation.source.value
        request.prompt_version = explanation.prompt_version
        request.matched_at = datetime.now(UTC)
        request.status = RequestStatus.READY
        if explanation.picks:
            add_notification(
                db, request.user_id, NotificationKind.MATCHES_READY, request_id=request_id
            )
        await db.commit()
    logger.info(
        "matches_made",
        extra={
            "intent": intent.value,
            "retrieved": len(found),
            "good_enough": len(ranked),
            "matches": len(explanation.picks),
            "explanation_source": explanation.source.value,
        },
    )
    return True
