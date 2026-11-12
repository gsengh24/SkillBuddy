"""Request and response models for onboarding (ADR 0022): one save per step, and progress."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.ai.stages.understand import Intent
from app.models import (
    MAX_PICKED_TAGS,
    TAG_MAX_LENGTH,
    WANT_NOTE_MAX_LENGTH,
    Branch,
    OnboardingStep,
    StudyYear,
    Weekday,
    WeeklyHours,
)
from app.schemas.profile import Days, DisplayName

_REQUEST = ConfigDict(extra="forbid")


def _unique_tags(values: list[str]) -> list[str]:
    """Drops repeats, ignoring case, keeping the first spelling of each."""
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            kept.append(value)
    return kept


def _unique_intents(values: list[Intent]) -> list[Intent]:
    return list(dict.fromkeys(values))


Tag = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TAG_MAX_LENGTH)
]
Tags = Annotated[list[Tag], Field(max_length=MAX_PICKED_TAGS), AfterValidator(_unique_tags)]
WantNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=WANT_NOTE_MAX_LENGTH)]


class IntentsStepIn(BaseModel):
    """Step 1: what the person is here for. At least one; this step can't be skipped."""

    model_config = _REQUEST

    intents: Annotated[
        list[Intent],
        Field(min_length=1, max_length=len(Intent)),
        AfterValidator(_unique_intents),
    ]


class OffersStepIn(BaseModel):
    """Step 2: skills the person can offer. Replaces the saved list."""

    model_config = _REQUEST

    skills: Tags = Field(description="Plain skill names; repeats (ignoring case) are dropped.")


class WantsStepIn(BaseModel):
    """Step 3: skills the person wants, interests, and an optional note. Replaces all three."""

    model_config = _REQUEST

    skills: Tags = Field(default_factory=list)
    interests: Tags = Field(default_factory=list)
    note: WantNote = Field(default="", description="Optional; an empty string clears it.")


class AboutStepIn(BaseModel):
    """Step 4: a few details, all optional. Omitted fields stay as they are."""

    model_config = _REQUEST

    study_year: StudyYear | None = Field(default=None, description="`null` clears it.")
    branch: Branch | None = Field(default=None, description="`null` clears it.")
    available_days: Days | None = None
    weekly_hours: WeeklyHours | None = Field(default=None, description="`null` clears it.")
    display_name: DisplayName | None = Field(
        default=None,
        description="Shown to people who receive an intro. Never sent to an AI provider.",
    )


class SkippableStep(StrEnum):
    OFFERS = OnboardingStep.OFFERS.value
    WANTS = OnboardingStep.WANTS.value
    ABOUT = OnboardingStep.ABOUT.value


class StepState(StrEnum):
    SAVED = "saved"
    SKIPPED = "skipped"
    TODO = "todo"


class NextStep(StrEnum):
    INTENTS = OnboardingStep.INTENTS.value
    OFFERS = OnboardingStep.OFFERS.value
    WANTS = OnboardingStep.WANTS.value
    ABOUT = OnboardingStep.ABOUT.value
    # Every step was saved or skipped; what's left is checking the result.
    REVIEW = "review"


class StepOut(BaseModel):
    step: OnboardingStep
    state: StepState


class OnboardingOut(BaseModel):
    """Where the person is in onboarding, and what they have picked so far."""

    completed_at: datetime | None = Field(description="`null` until onboarding is finished.")
    next_step: NextStep | None = Field(
        description=(
            "The first step neither saved nor skipped, `review` when only checking the result "
            "is left, or `null` once onboarding is finished."
        )
    )
    steps: list[StepOut] = Field(description="Every saved step, in order, with its state.")
    intents: list[Intent]
    offer_skills: list[str]
    want_skills: list[str]
    interest_tags: list[str]
    want_note: str
    study_year: StudyYear | None
    branch: Branch | None
    available_days: list[Weekday]
    weekly_hours: WeeklyHours | None
    display_name: str
