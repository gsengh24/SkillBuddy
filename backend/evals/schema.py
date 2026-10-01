"""Schema for the matcher's offline evaluation set (ARCHITECTURE.md, sections 3 and 7).

A labelled pair is directional: ``profile_a`` is the person making the request (their
``request_intent`` is the pair's intent) and ``profile_b`` is the candidate being judged.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ProfileId = Annotated[str, StringConstraints(pattern=r"^p\d{2}$")]
PairId = Annotated[str, StringConstraints(pattern=r"^pair-\d{3}$")]
# ISO 639 language codes, matching profiles.languages in the database schema.
LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}$")]

_STRICT = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Intent(StrEnum):
    BUILD_TOGETHER = "build_together"
    SKILL_EXCHANGE = "skill_exchange"
    INTEREST_BUDDY = "interest_buddy"
    ACCOUNTABILITY = "accountability"
    MENTOR = "mentor"
    EXPLORE = "explore"


class Label(StrEnum):
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"


class SyntheticProfile(BaseModel):
    """A fictional person: free-text "about me" plus the request they would make."""

    model_config = _STRICT

    id: ProfileId
    name: str = Field(min_length=1, max_length=80)
    # A plausibility bound for synthetic data, not an age requirement (minors may join; ADR 0009).
    age: int = Field(ge=1, le=100, description="Age in years.")
    city: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=80)
    timezone: str = Field(description="IANA timezone name, e.g. Asia/Kolkata.")
    languages: list[LanguageCode] = Field(min_length=1)
    # Same 2,000-character cap the product will enforce on profile and request text.
    about: str = Field(min_length=100, max_length=2000)
    request: str = Field(min_length=10, max_length=2000)
    request_intent: Intent

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {value!r}") from exc
        return value


class LabelledPair(BaseModel):
    """A requester (A) and a candidate (B), with a proposed or reviewed match label."""

    model_config = _STRICT

    id: PairId
    profile_a: ProfileId
    profile_b: ProfileId
    intent: Intent
    label: Label
    rationale: str = Field(min_length=20, max_length=500)
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _distinct_profiles(self) -> Self:
        if self.profile_a == self.profile_b:
            raise ValueError("profile_a and profile_b must be different profiles")
        return self


class EvalSet(BaseModel):
    """The whole dataset, with cross-record checks that single records cannot do."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profiles: list[SyntheticProfile]
    pairs: list[LabelledPair]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _require_unique("profile id", [p.id for p in self.profiles])
        _require_unique("pair id", [p.id for p in self.pairs])
        by_id = {p.id: p for p in self.profiles}

        seen: set[tuple[frozenset[str], Intent]] = set()
        for pair in self.pairs:
            for ref in (pair.profile_a, pair.profile_b):
                if ref not in by_id:
                    raise ValueError(f"{pair.id}: unknown profile {ref!r}")
            requester_intent = by_id[pair.profile_a].request_intent
            if pair.intent is not requester_intent:
                raise ValueError(
                    f"{pair.id}: intent {pair.intent.value!r} does not match "
                    f"{pair.profile_a}'s request intent {requester_intent.value!r}"
                )
            key = (frozenset((pair.profile_a, pair.profile_b)), pair.intent)
            if key in seen:
                raise ValueError(
                    f"{pair.id}: {pair.profile_a}/{pair.profile_b} already labelled "
                    f"for {pair.intent.value!r}"
                )
            seen.add(key)
        return self


def _require_unique(what: str, values: list[str]) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {what}(s): {', '.join(duplicates)}")
