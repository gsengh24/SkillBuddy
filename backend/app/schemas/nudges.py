"""In-context nudges and aggregate demand (ADR 0022, screens 8 and 11). Data only."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import TAG_MAX_LENGTH, NudgeKind
from app.services.demand import MIN_COUNT, WINDOW_DAYS
from app.services.nudges import Nudge


class NudgeOut(BaseModel):
    """One suggestion. `team_skill`: add `skill`, named by the team just joined.
    `availability`: add available days (after a first match)."""

    kind: NudgeKind
    skill: str | None = Field(default=None, description="`team_skill` only.")
    team_id: uuid.UUID | None = Field(default=None, description="`team_skill` only.")
    team_name: str | None = Field(default=None, description="`team_skill` only.")

    @classmethod
    def of(cls, nudge: Nudge) -> NudgeOut:
        return cls(
            kind=nudge.kind, skill=nudge.skill, team_id=nudge.team_id, team_name=nudge.team_name
        )


class CurrentNudgeOut(BaseModel):
    nudge: NudgeOut | None = Field(
        description="Today's nudge, or `null`. Each kind shows on one day at most, one a day."
    )


SkillQuery = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TAG_MAX_LENGTH)
]


class DemandOut(BaseModel):
    """How many people want a skill: a count only, never who."""

    skill: str
    count: int | None = Field(
        description=f"People who wanted it in the last {WINDOW_DAYS} days; `null` below "
        f"{MIN_COUNT}, so small numbers can't point at anyone."
    )
    window_days: int
