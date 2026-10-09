"""Anonymous candidate summaries for the selection stage (ADR 0007, section 5).

A provider never sees who a candidate is: each one becomes an alias (C1 to C15) with a
short structured summary whose text has been redacted. The alias map stays on the server
and is used to read the model's answer back.

A summary holds only what the privacy policy says may be sent about a person: skills,
interests, goals and availability. Adding any other field needs the policy changed first.
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
    # The profile's own availability fields (Weekday and WeeklyHours values).
    days: Sequence[str] = ()
    weekly_hours: str = ""
    # Names to strip from this candidate's own text (never sent).
    name_hints: Sequence[str] = field(default=())


def _clean(items: Sequence[str], names: Sequence[str]) -> list[str]:
    cleaned = [redact(" ".join(item.split())[:_MAX_CHARS], names=names) for item in items]
    return [item for item in cleaned if item][:_MAX_ITEMS]


_DAYS: Final = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}
_HOURS: Final = {
    "1_3": "1 to 3 hours a week",
    "4_6": "4 to 6 hours a week",
    "7_10": "7 to 10 hours a week",
    "10_plus": "10 or more hours a week",
}


def _availability(person: CandidateSummary, names: Sequence[str]) -> str:
    """What they said about their time, then their days and weekly hours."""
    days = [_DAYS[day] for day in _DAYS if day in person.days]
    parts = [
        redact(person.availability[:_MAX_CHARS], names=names),
        ", ".join(days),
        _HOURS.get(person.weekly_hours, ""),
    ]
    return "; ".join(part for part in parts if part)


def describe(person: CandidateSummary) -> dict[str, Any]:
    """One person as the model sees them: redacted, capped, and with no id."""
    names = list(person.name_hints)
    return {
        "skills": _clean(person.skills, names),
        "interests": _clean(person.interests, names),
        "goals": _clean(person.goals, names),
        "availability": _availability(person, names),
    }


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
        summaries.append({"id": alias, **describe(candidate)})
    return summaries, aliases
