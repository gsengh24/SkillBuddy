"""Onboarding progress and step validation (ADR 0022), without a database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import Profile
from app.schemas.onboarding import NextStep, OffersStepIn, StepState, WantsStepIn
from app.services.onboarding import progress


def profile(**fields: object) -> Profile:
    defaults: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "display_name": "",
        "intents": [],
        "offer_skills": [],
        "want_skills": [],
        "interest_tags": [],
        "want_note": "",
        "available_days": [],
        "onboarding_saved": [],
        "onboarding_skipped": [],
    }
    return Profile(**(defaults | fields))


def test_no_profile_starts_at_step_one() -> None:
    result = progress(None)
    assert result.next_step is NextStep.INTENTS
    assert {step.state for step in result.steps} == {StepState.TODO}


def test_next_step_is_the_first_neither_saved_nor_skipped() -> None:
    result = progress(profile(onboarding_saved=["intents", "wants"], onboarding_skipped=["offers"]))
    assert result.next_step is NextStep.ABOUT
    assert [step.state for step in result.steps] == [
        StepState.SAVED,
        StepState.SKIPPED,
        StepState.SAVED,
        StepState.TODO,
    ]


def test_review_when_every_step_is_done_and_nothing_once_finished() -> None:
    every = ["intents", "offers", "wants", "about"]
    assert progress(profile(onboarding_saved=every)).next_step is NextStep.REVIEW
    finished = profile(onboarding_completed_at=datetime.now(UTC))
    assert progress(finished).next_step is None


def test_tags_drop_repeats_ignoring_case_and_keep_the_first_spelling() -> None:
    assert OffersStepIn(skills=["React", "react ", " REACT", "Go"]).skills == ["React", "Go"]


@pytest.mark.parametrize(
    "payload",
    [
        {"skills": ["x" * 61]},
        {"skills": [""]},
        {"note": "x" * 141},
        {"interests": [" "]},
    ],
)
def test_wants_limits(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WantsStepIn.model_validate(payload)
