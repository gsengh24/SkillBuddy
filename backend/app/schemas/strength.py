"""Profile strength as the API returns it (ADR 0022)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.profile_strength import Strength, StrengthItem


class StrengthOut(BaseModel):
    """How complete the profile is. Computed by the API only; clients show it."""

    percent: int = Field(ge=0, le=100)
    done: int = Field(ge=0)
    total: int = Field(ge=1)
    missing: list[StrengthItem] = Field(
        description="What is not done yet, in the order to suggest it."
    )

    @classmethod
    def of(cls, strength: Strength) -> StrengthOut:
        return cls(
            percent=strength.percent,
            done=strength.done,
            total=strength.total,
            missing=list(strength.missing),
        )
