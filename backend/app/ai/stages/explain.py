"""Stage 4, Explain: pick the best few candidates and say why (ADR 0007; ARCHITECTURE.md §3).

``explain()`` sends the request and up to 15 anonymous candidates (C1 to C15, best-scored
first) to the gateway, maps the model's picks back to users and drops any id it was not
given. When the AI is off or fails, ``explain_template()`` keeps the top candidates by score
and writes a reason from what the two profiles have in common, so matching still works.
The scores themselves come from retrieval and ranking (stages 2 and 3) and are applied in
code, never by the model (ARCHITECTURE.md §7, guardrails).
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

PROMPT_ID: Final = "explain_v1"
DEFAULT_MAX_PICKS: Final = 5
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


class Pick(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[str, StringConstraints(pattern=r"^C\d{1,2}$")]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=240)]


class Selection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    picks: list[Pick] = Field(default_factory=list, max_length=MAX_CANDIDATES)


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
) -> Explanation:
    """Choose and explain up to ``max_picks`` of at most 15 candidates."""
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
        max_tokens=900,
    )
    result = await gateway.complete(
        Task.SELECT, prompt, Selection, user_id=user_id, fallback=Selection
    )
    if result.source is Source.LLM:
        picks: list[Explained] = []
        seen: set[str] = set()
        for pick in result.value.picks:
            if pick.id in aliases and pick.id not in seen:
                seen.add(pick.id)
                picks.append(Explained(aliases[pick.id], pick.reason))
        if picks:
            return Explanation(picks[:max_picks], Source.LLM, PROMPT_ID)
    return Explanation(
        explain_template(request, ranked, max_picks=max_picks), Source.TEMPLATE, None
    )
