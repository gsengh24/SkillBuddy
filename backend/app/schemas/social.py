"""Request and response models for intros, connections and notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import INTRO_NOTE_MAX_LENGTH, Connection, Notification, Profile
from app.services.chat import ConversationSummary
from app.services.intros import IntroView


class IntroIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=INTRO_NOTE_MAX_LENGTH)
    ] = Field(default="", description="A short hello, shown to the other person.")


class IntroResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


class PersonOut(BaseModel):
    """Someone else. ``display_name`` and ``links`` are set only once you're connected."""

    user_id: uuid.UUID
    display_name: str | None
    links: list[str] | None
    summary: str
    offers: list[str]
    seeks: list[str]
    interests: list[str]
    availability: str
    languages: list[str]
    location: str | None = Field(
        description="The city, if the person shares it (their location precision)."
    )

    @classmethod
    def build(cls, user_id: uuid.UUID, profile: Profile | None, *, connected: bool) -> PersonOut:
        data: dict[str, Any] = (profile.structured if profile else None) or {}

        def items(key: str) -> list[str]:
            value = data.get(key)
            return [str(v) for v in value] if isinstance(value, list) else []

        return cls(
            user_id=user_id,
            display_name=(profile.display_name or None) if connected and profile else None,
            links=list(profile.links) if connected and profile else None,
            summary=str(data.get("summary", "")),
            offers=items("offers"),
            seeks=items("seeks"),
            interests=items("interests"),
            availability=str(data.get("availability", "")),
            languages=list(profile.languages) if profile else [],
            location=profile.shown_location() if profile else None,
        )


class IntroOut(BaseModel):
    id: uuid.UUID
    direction: Literal["received", "sent"]
    status: Literal["pending", "accepted", "declined", "withdrawn", "expired"] = Field(
        description="A declined intro shows as `pending` to its sender until it expires."
    )
    note: str
    request_text: str = Field(description="What the sender asked for.")
    reason: str = Field(description="Why the two were matched.")
    person: PersonOut = Field(description="The other person.")
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None

    @classmethod
    def build(cls, view: IntroView) -> IntroOut:
        intro = view.intro
        return cls(
            id=intro.id,
            direction=view.direction.value,
            status=view.status.value,
            note=intro.note,
            request_text=view.request_text,
            reason=view.reason,
            person=PersonOut.build(view.other_id, view.other_profile, connected=view.connected),
            created_at=intro.created_at,
            expires_at=intro.expires_at,
            # The sender never learns when (or that) an intro was declined.
            responded_at=(
                intro.responded_at
                if view.direction.value == "received" or view.status.value == "accepted"
                else None
            ),
        )


class IntroPage(BaseModel):
    items: list[IntroOut]
    next_cursor: str | None


class ConnectionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    person: PersonOut
    unread_messages: int = Field(description="Messages from them you haven't read.")
    last_message_at: datetime | None

    @classmethod
    def build(
        cls,
        connection: Connection,
        other: uuid.UUID,
        profile: Profile | None,
        summary: ConversationSummary | None,
    ) -> ConnectionOut:
        return cls(
            id=connection.id,
            created_at=connection.created_at,
            person=PersonOut.build(other, profile, connected=True),
            unread_messages=summary.unread if summary else 0,
            last_message_at=summary.last_message_at if summary else None,
        )


class ConnectionList(BaseModel):
    items: list[ConnectionOut]


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: Literal[
        "intro_received",
        "intro_accepted",
        "matches_ready",
        "report_reviewed",
        "content_removed",
        "team_invite",
        "team_joined",
        "team_request",
        "team_request_accepted",
    ]
    intro_id: uuid.UUID | None
    request_id: uuid.UUID | None
    team_id: uuid.UUID | None = Field(
        default=None, description="For the `team_*` kinds: the team (ADR 0016)."
    )
    rule: str | None = Field(
        default=None,
        description="For `content_removed`: the content rule the text broke (A7).",
    )
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def build(cls, notification: Notification) -> NotificationOut:
        return cls(
            id=notification.id,
            kind=notification.kind,  # type: ignore[arg-type]  # CHECK-constrained column
            intro_id=notification.intro_id,
            request_id=notification.request_id,
            team_id=notification.team_id,
            rule=notification.rule,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread: int


class UnreadCount(BaseModel):
    unread: int


class MarkReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID] | None = Field(
        default=None, max_length=100, description="Leave out to mark everything read."
    )


class MarkedRead(BaseModel):
    marked: int
