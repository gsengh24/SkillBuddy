"""Request and response models for match requests and matches."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import (
    REQUEST_TEXT_MAX_LENGTH,
    REQUEST_TEXT_MIN_LENGTH,
    Match,
    MatchRequest,
    MatchStatus,
    Profile,
    RequestStatus,
)

Intent = Literal[
    "build_together",
    "skill_exchange",
    "interest_buddy",
    "accountability",
    "mentor",
    "explore",
]


class MatchRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=REQUEST_TEXT_MIN_LENGTH,
            max_length=REQUEST_TEXT_MAX_LENGTH,
        ),
    ] = Field(description="What the person is looking for, in their own words.")
    intent: Intent | None = Field(
        default=None,
        description="The intent the person picked. Without it the matcher works it out.",
    )


class MatchRequestOut(BaseModel):
    id: uuid.UUID
    text: str
    requested_intent: Intent | None
    intent: Intent | None = Field(description="The intent the matcher used, once matched.")
    status: RequestStatus = Field(
        description="`pending` while matches are being found (poll until `ready`)."
    )
    match_count: int
    created_at: datetime
    matched_at: datetime | None
    expires_at: datetime

    @classmethod
    def build(cls, request: MatchRequest, match_count: int) -> MatchRequestOut:
        return cls(
            id=request.id,
            text=request.raw_text,
            requested_intent=request.requested_intent,  # type: ignore[arg-type]  # CHECK-constrained column
            intent=request.intent,  # type: ignore[arg-type]  # CHECK-constrained column
            status=RequestStatus(request.status),
            match_count=match_count,
            created_at=request.created_at,
            matched_at=request.matched_at,
            expires_at=request.expires_at,
        )


class MatchRequestPage(BaseModel):
    items: list[MatchRequestOut]
    next_cursor: str | None = Field(description="Pass as `cursor` for the next page.")


class MatchCandidateOut(BaseModel):
    """What a match shows about the other person before any introduction: the parsed
    profile only. No name, links or contact details (they come with an accepted intro)."""

    user_id: uuid.UUID
    summary: str
    offers: list[str]
    seeks: list[str]
    interests: list[str]
    availability: str
    languages: list[str]


class MatchOut(BaseModel):
    id: uuid.UUID
    rank: int
    reason: str
    status: MatchStatus
    candidate: MatchCandidateOut

    @classmethod
    def build(cls, match: Match, profile: Profile | None) -> MatchOut:
        data: dict[str, Any] = (profile.structured if profile else None) or {}

        def items(key: str) -> list[str]:
            value = data.get(key)
            return [str(v) for v in value] if isinstance(value, list) else []

        return cls(
            id=match.id,
            rank=match.rank,
            reason=match.reason,
            status=MatchStatus(match.status),
            candidate=MatchCandidateOut(
                user_id=match.candidate_id,
                summary=str(data.get("summary", "")),
                offers=items("offers"),
                seeks=items("seeks"),
                interests=items("interests"),
                availability=str(data.get("availability", "")),
                languages=list(profile.languages) if profile else [],
            ),
        )


class MatchList(BaseModel):
    items: list[MatchOut]
