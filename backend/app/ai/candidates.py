"""Anonymous candidate summaries for the selection stage (ADR 0007, section 5).

A provider never sees who a candidate is: each one becomes an alias (C1 to C15) with a
short structured summary whose text has been redacted. The alias map stays on the server
and is used to read the model's answer back.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from app.ai.privacy import redact

MAX_CANDIDATES: Final = 15
# Per-field caps keep a summary at about 110 tokens (ADR 0007, section 4).
_MAX_ITEMS: Final = 8
_MAX_CHARS: Final = 160


@dataclass(frozen=True)
class CandidateSummary:
    """What the selection model may know about one candidate. No ids, names or contacts."""

    user_id: uuid.UUID
    skills: Sequence[str] = ()
    interests: Sequence[str] = ()
    goals: Sequence[str] = ()
    availability: str = ""
    # Names to strip from this candidate's own text (never sent).
    name_hints: Sequence[str] = field(default=())


def _clean(items: Sequence[str], names: Sequence[str]) -> list[str]:
    cleaned = [redact(" ".join(item.split())[:_MAX_CHARS], names=names) for item in items]
    return [item for item in cleaned if item][:_MAX_ITEMS]


def anonymise(
    candidates: Sequence[CandidateSummary],
) -> tuple[list[dict[str, Any]], dict[str, uuid.UUID]]:
    """Aliased, redacted summaries (C1, C2, ...) and the alias-to-user map."""
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"at most {MAX_CANDIDATES} candidates go to the model")
    summaries: list[dict[str, Any]] = []
    aliases: dict[str, uuid.UUID] = {}
    for index, candidate in enumerate(candidates, start=1):
        alias = f"C{index}"
        aliases[alias] = candidate.user_id
        names = list(candidate.name_hints)
        summaries.append(
            {
                "id": alias,
                "skills": _clean(candidate.skills, names),
                "interests": _clean(candidate.interests, names),
                "goals": _clean(candidate.goals, names),
                "availability": redact(candidate.availability[:_MAX_CHARS], names=names),
            }
        )
    return summaries, aliases
