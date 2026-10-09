"""Stage 4, Explain: judge the candidates, keep the best few and say why (ADR 0007;
ARCHITECTURE.md §3).

``explain()`` sends the request and up to 15 anonymous candidates (C1 to C15, best-scored
first) to the gateway. The model is a judge, not a ranker: for every candidate it fills in
a small rubric (``Verdict``), and code turns the rubric into a score, drops anyone under
``min_judged`` or with a conflict, and orders the rest (ARCHITECTURE.md §7, guardrails:
weights are applied in code, never by the model). A candidate the model did not judge, or
an id it was not given, is dropped. So the AI path can end with fewer picks than asked for,
or none.

When the AI is off or fails, ``explain_template()`` keeps the top candidates by the score
from retrieval and ranking (stages 2 and 3) and writes a reason from what the two profiles
have in common, so matching still works.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.ai.candidates import MAX_CANDIDATES, CandidateSummary, anonymise
from app.ai.gateway import AIGateway, Prompt, Source, Task
from app.ai.prompts import load_prompt
from app.ai.stages.understand import Understanding

PROMPT_ID: Final = "explain_v2"
DEFAULT_MAX_PICKS: Final = 5
# The judged score: how much each rubric value counts (they add up to 1).
NEED_WEIGHT: Final = 0.65
SHARED_WEIGHT: Final = 0.35
RUBRIC_MAX: Final = 3
# Under this judged score (0 to 1) a candidate is not suggested. "Mostly what they asked
# for" alone passes (0.43); "loosely related, a little in common" does not (0.33).
DEFAULT_MIN_JUDGED: Final = 0.4
# The final order: the judged score, with the score from stages 2 and 3 for the rest.
JUDGED_WEIGHT: Final = 0.7
# A shorter reason than this is treated as missing (the template writes one instead).
MIN_REASON_CHARS: Final = 10
_WORD: Final = re.compile(r"[a-z0-9+#.]+")
_STOP: Final = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "have",
        "i",
        "in",
        "into",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "so",
        "some",
        "someone",
        "that",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "want",
        "we",
        "who",
        "with",
        "you",
        "your",
    ]
)


class Verdict(BaseModel):
    """The model's rubric for one candidate. Code, not the model, turns it into a score."""

    model_config = ConfigDict(extra="ignore")

    id: Annotated[str, StringConstraints(pattern=r"^C\d{1,2}$")]
    # How well they are what the request asks for, and what else the two have in common.
    need: int = Field(ge=0, le=RUBRIC_MAX)
    shared: int = Field(ge=0, le=RUBRIC_MAX)
    # Their summary contradicts the request (say, a mentor who is not taking mentees).
    conflict: bool = False
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)] = ""


class Judgement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdicts: list[Verdict] = Field(default_factory=list, max_length=MAX_CANDIDATES)


def judged_score(verdict: Verdict) -> float:
    """The rubric as one number, 0 to 1; a conflict is always 0."""
    if verdict.conflict:
        return 0.0
    return (NEED_WEIGHT * verdict.need + SHARED_WEIGHT * verdict.shared) / RUBRIC_MAX


@dataclass(frozen=True)
class Candidate:
    """A retrieved, ranked candidate: their anonymous summary and their score in code."""

    summary: CandidateSummary
    score: float


@dataclass(frozen=True)
class Explained:
    user_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class Explanation:
    """The chosen candidates in order, and whether an AI or the template chose them."""

    picks: list[Explained]
    source: Source
    prompt_version: str | None


def _words(items: Sequence[str]) -> set[str]:
    return {w for item in items for w in _WORD.findall(item.lower()) if w not in _STOP}


def _shared(mine: Sequence[str], theirs: Sequence[str]) -> list[str]:
    """Their phrases that share a word with mine, in their order."""
    wanted = _words(mine)
    return [t for t in theirs if _words([t]) & wanted]


def template_reason(request: Understanding, candidate: CandidateSummary) -> str:
    offers_wanted = _shared(request.seeks, [*candidate.skills, *candidate.goals])
    interests = _shared(
        [*request.interests, *request.seeks, *request.offers, request.summary],
        [*candidate.interests, *candidate.skills, *candidate.goals],
    )
    if offers_wanted:
        return f"They offer {', '.join(offers_wanted[:2])}, which you are looking for."
    if interests:
        return f"You both mention {', '.join(interests[:2])}."
    if candidate.availability and request.availability:
        return f"A close match for your request; they are available {candidate.availability}."
    return "A close match for what you described."


def explain_template(
    request: Understanding,
    candidates: Sequence[Candidate],
    *,
    max_picks: int = DEFAULT_MAX_PICKS,
) -> list[Explained]:
    """The top candidates by score, each with a reason built from overlapping fields."""
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)[:max_picks]
    return [Explained(c.summary.user_id, template_reason(request, c.summary)) for c in ranked]


async def explain(
    gateway: AIGateway,
    request_text: str,
    request: Understanding,
    candidates: Sequence[Candidate],
    *,
    user_id: str,
    name_hints: Sequence[str] = (),
    max_picks: int = DEFAULT_MAX_PICKS,
    min_judged: float = DEFAULT_MIN_JUDGED,
) -> Explanation:
    """Judge at most 15 candidates; keep and explain up to ``max_picks`` good enough ones."""
    if not candidates:
        return Explanation(picks=[], source=Source.TEMPLATE, prompt_version=None)
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)[:MAX_CANDIDATES]
    summaries, aliases = anonymise([c.summary for c in ranked])
    prompt = Prompt(
        version=PROMPT_ID,
        system=load_prompt(PROMPT_ID),
        data={
            "request": request_text,
            "request_summary": request.model_dump(mode="json"),
            "max_picks": max_picks,
            "candidates": summaries,
        },
        name_hints=name_hints,
        # A verdict for each of 15 candidates, and a reason for a few of them.
        max_tokens=1200,
    )
    result = await gateway.complete(
        Task.SELECT, prompt, Judgement, user_id=user_id, fallback=Judgement
    )
    if result.source is Source.LLM:
        # The first verdict for each candidate that was really sent.
        verdicts: dict[uuid.UUID, Verdict] = {}
        for verdict in result.value.verdicts:
            if verdict.id in aliases:
                verdicts.setdefault(aliases[verdict.id], verdict)
        # No usable verdict at all is a failed answer, not "nobody fits": use the template.
        if verdicts:
            kept: list[tuple[float, Candidate, Verdict]] = []
            for candidate in ranked:
                found = verdicts.get(candidate.summary.user_id)
                # A conflict rules them out even with the floor off.
                if found is None or found.conflict:
                    continue
                judged = judged_score(found)
                if judged < min_judged:
                    continue
                final = JUDGED_WEIGHT * judged + (1 - JUDGED_WEIGHT) * candidate.score
                kept.append((final, candidate, found))
            kept.sort(key=lambda item: item[0], reverse=True)
            return Explanation(
                [
                    Explained(
                        candidate.summary.user_id,
                        found.reason
                        if len(found.reason) >= MIN_REASON_CHARS
                        else template_reason(request, candidate.summary),
                    )
                    for _, candidate, found in kept[:max_picks]
                ],
                Source.LLM,
                PROMPT_ID,
            )
    return Explanation(
        explain_template(request, ranked, max_picks=max_picks), Source.TEMPLATE, None
    )
