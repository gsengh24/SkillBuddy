"""Responses for the admin Users page (A2). User-written text is plain data."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import NOTE_MAX_LENGTH, AdminNote

Status = Literal["active", "paused", "pending", "suspended", "banned", "pending_deletion"]


class UserRow(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = Field(description="Their display name, if they made a profile.")
    status: Status
    intents: list[str]
    flagged: bool = Field(description="Open reports against them.")
    open_reports: int = Field(description="How many open reports there are against them.")
    matches: int = Field(
        description="Matches made for their requests, plus times they were suggested to someone."
    )
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_row(cls, row: Any) -> UserRow:
        return cls(
            id=row["id"],
            email=row["email"],
            name=row["display_name"] or None,
            status=row["status"],
            intents=list(row["intents"] or []),
            flagged=bool(row["flagged"]),
            open_reports=int(row["open_reports"] or 0),
            matches=int(row["matches"] or 0),
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )


class UserPage(BaseModel):
    items: list[UserRow]
    next_cursor: str | None
    total: int = Field(description="All that match the filters (cached up to a minute).")


class ProfileSummary(BaseModel):
    display_name: str
    headline: str
    city: str
    about_text: str = Field(description="Plain text written by the user.")
    intents: list[str]
    visibility: str
    parse_status: str
    skills: list[str] = Field(description="What they can give, as read from the about text.")
    seeks: list[str] = Field(description="What they are looking for, read the same way.")
    interests: list[str]


class MatchPerson(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None


class UserMatch(BaseModel):
    id: uuid.UUID
    role: Literal["requester", "candidate"] = Field(
        description="requester: made for this user's request. candidate: this user was "
        "suggested to the other person."
    )
    other: MatchPerson
    intent: str | None = Field(description="The request's intent, once the matcher set it.")
    rank: int
    status: str
    created_at: datetime


class TimelineItem(BaseModel):
    at: datetime
    event: str


class NoteOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID | None
    body: str = Field(description="Plain text.")
    created_at: datetime

    @classmethod
    def from_note(cls, note: AdminNote) -> NoteOut:
        return cls(id=note.id, author_id=note.author_id, body=note.body, created_at=note.created_at)


class UserDetail(BaseModel):
    id: uuid.UUID
    email: str
    status: Status
    suspended_until: datetime | None
    deletion_scheduled_for: datetime | None
    created_at: datetime
    last_login_at: datetime | None
    email_verified_at: datetime | None
    sign_in_methods: list[str] = Field(description='e.g. ["email", "google"].')
    profile: ProfileSummary | None
    counts: dict[str, int] = Field(
        description="requests, matches_for_requests, matched_as_candidate, connections, "
        "reports_against, open_reports_against."
    )
    matches: list[UserMatch] = Field(description="Newest first, both roles; at most 20.")
    timeline: list[TimelineItem] = Field(description="Newest first: sign-ins and admin actions.")
    notes: list[NoteOut]


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_MAX_LENGTH)
    ]
