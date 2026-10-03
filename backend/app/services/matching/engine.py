"""The matcher for one request: understand, retrieve, rank, explain (ARCHITECTURE.md §3).

Runs in the ``match_request`` job, never in a request handler. Every stage works with the
AI off: the Understand and Explain stages fall back to their templates, and retrieval and
ranking never use an LLM.

- **Retrieve:** the request is embedded once (as a query) and compared with one facet of
  every matchable profile, chosen by intent (``SEARCH``). Hard filters: not yourself, only
  active accounts, only profiles that are "matchable", only current-model vectors.
- **Rank:** in code, never by the model (ARCHITECTURE.md §7, guardrails):
  ``score = w_fit*fit + w_recip*min(fit, reciprocity) + w_act*activity + w_new*novelty
  - w_over*overexposure``, with hand-set weights per intent. "Explore" then picks a
  diverse set with maximal marginal relevance.
- **Explain:** the best 15 go, anonymised, to ``explain()``, which picks and explains up
  to ``MATCHES_PER_REQUEST``.
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


@dataclass(frozen=True)
class Search:
    """Which request text to embed, which candidate facet to compare it with."""

    query: str  # "seeks", "interests" or "all"
    facet: EmbeddingFacet
    # Score the other side too: their "seek" against my "offer".
    reciprocal: bool


SEARCH: Final[dict[Intent, Search]] = {
    Intent.BUILD_TOGETHER: Search("seeks", EmbeddingFacet.OFFER, reciprocal=True),
    Intent.SKILL_EXCHANGE: Search("seeks", EmbeddingFacet.OFFER, reciprocal=True),
    Intent.MENTOR: Search("seeks", EmbeddingFacet.OFFER, reciprocal=False),
    Intent.INTEREST_BUDDY: Search("interests", EmbeddingFacet.INTEREST, reciprocal=False),
    Intent.ACCOUNTABILITY: Search("all", EmbeddingFacet.IDENTITY, reciprocal=False),
    Intent.EXPLORE: Search("all", EmbeddingFacet.IDENTITY, reciprocal=False),
}


@dataclass(frozen=True)
class Weights:
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


@dataclass(frozen=True)
class Ranked:
    candidate: Retrieved
    score: float


def query_text(raw_text: str, understanding: Understanding, search: Search) -> str:
    """The request text, with the phrases that matter for this intent repeated first."""
    if search.query == "seeks" and understanding.seeks:
        return f"{'; '.join(understanding.seeks)}. {raw_text}"
    if search.query == "interests" and understanding.interests:
        return f"{'; '.join(understanding.interests)}. {raw_text}"
    return raw_text


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"


async def retrieve(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
    query_vector: Sequence[float],
    search: Search,
    model_version: str,
    with_vectors: bool,
    limit: int = RETRIEVE_LIMIT,
) -> list[Retrieved]:
    """Nearest profiles on one facet, with the hard filters applied in SQL."""
    reciprocity = (
        "(SELECT 1 - (their_seek.embedding <=> my_offer.embedding) "
        " FROM profile_embeddings their_seek, profile_embeddings my_offer "
        " WHERE their_seek.user_id = pe.user_id AND their_seek.facet = 'seek' "
        "   AND my_offer.user_id = :me AND my_offer.facet = 'offer')"
        if search.reciprocal
        else "NULL"
    )
    vector_column = ", pe.embedding::text AS vector" if with_vectors else ""
    rows = await db.execute(
        text(
            f"SELECT pe.user_id, 1 - (pe.embedding <=> CAST(:q AS vector)) AS fit, "  # noqa: S608  # fixed fragments, values are bound
            f"{reciprocity} AS reciprocity, u.last_login_at, p.structured, p.display_name"
            f"{vector_column} "
            "FROM profile_embeddings pe "
            "JOIN profiles p ON p.user_id = pe.user_id "
            "JOIN users u ON u.id = pe.user_id "
            "WHERE pe.facet = :facet AND pe.model_version = :model AND pe.user_id <> :me "
            "AND u.status = 'active' AND p.visibility = 'matchable' "
            # Blocks work both ways (app/services/blocks.py).
            "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE "
            "(b.blocker_id = :me AND b.blocked_id = pe.user_id) OR "
            "(b.blocker_id = pe.user_id AND b.blocked_id = :me)) "
            "ORDER BY pe.embedding <=> CAST(:q AS vector) "
            "LIMIT :limit"
        ),
        {
            "q": _vector_literal(query_vector),
            "facet": search.facet.value,
            "model": model_version,
            "me": requester_id,
            "limit": limit,
        },
    )
    found: list[Retrieved] = []
    for row in rows.mappings():
        found.append(
            Retrieved(
                user_id=row["user_id"],
                fit=float(row["fit"]),
                reciprocity=None if row["reciprocity"] is None else float(row["reciprocity"]),
                last_login_at=row["last_login_at"],
                structured=dict(row["structured"] or {}),
                display_name=row["display_name"] or "",
                vector=json.loads(row["vector"]) if with_vectors else None,
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


def score(
    candidate: Retrieved,
    weights: Weights,
    *,
    now: datetime,
    seen_before: bool,
    recent_suggestions: int,
) -> float:
    two_sided = (
        min(candidate.fit, candidate.reciprocity)
        if candidate.reciprocity is not None
        else candidate.fit
    )
    overexposure = min(1.0, recent_suggestions / OVEREXPOSURE_SATURATION)
    return (
        weights.fit * candidate.fit
        + weights.reciprocity * two_sided
        + weights.activity * activity(candidate.last_login_at, now)
        + weights.novelty * (0.0 if seen_before else 1.0)
        - weights.overexposure * overexposure
    )


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
            search=search,
            model_version=embedder.model_version,
            with_vectors=intent is Intent.EXPLORE,
        )
        seen, counts = await _history(db, requester_id, request_id, [c.user_id for c in found])

    # --- 3. rank ---------------------------------------------------------------------------
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
            )
            for c in found
        ),
        key=lambda item: item.score,
        reverse=True,
    )
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
            "matches": len(explanation.picks),
            "explanation_source": explanation.source.value,
        },
    )
    return True
