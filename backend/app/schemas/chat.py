"""Request and response models for chat (ADR 0012)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import MESSAGE_MAX_LENGTH, TeamMessage
from app.services.chat import MessageView, Updates


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_LENGTH)
    ]


class MessageOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime

    @classmethod
    def build(cls, view: MessageView) -> MessageOut:
        message = view.message
        return cls(
            id=message.id,
            connection_id=message.connection_id,
            sender_id=view.sender_id,
            body=message.body,
            created_at=message.created_at,
        )


class TeamMessageOut(BaseModel):
    """A message in a team's chat (ADR 0016)."""

    id: uuid.UUID
    team_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime

    @classmethod
    def build(cls, message: TeamMessage) -> TeamMessageOut:
        return cls(
            id=message.id,
            team_id=message.team_id,
            sender_id=message.sender_id,
            body=message.body,
            created_at=message.created_at,
        )


class TeamMessagePage(BaseModel):
    items: list[TeamMessageOut] = Field(description="Newest first.")
    next_cursor: str | None = Field(description="Pass as `before` for older messages.")
    retention_days: int = Field(description="Messages are deleted this many days after sending.")


class MessagePage(BaseModel):
    items: list[MessageOut] = Field(description="Newest first.")
    next_cursor: str | None = Field(description="Pass as `before` for older messages.")
    retention_days: int = Field(description="Messages are deleted this many days after sending.")


class MessageUpdates(BaseModel):
    items: list[MessageOut] = Field(
        description="New messages in all your conversations, oldest first. A recent message "
        "can appear in two polls in a row: de-duplicate by `id`."
    )
    team_items: list[TeamMessageOut] = Field(
        default_factory=list,
        description="New messages in your teams, oldest first; the same cursor covers both "
        "lists. Empty while teams are switched off.",
    )
    cursor: str = Field(description="Pass as `after` on the next poll.")
    has_more: bool = Field(description="More are waiting: poll again right away.")
    poll_after_seconds: int | None = Field(
        description="Set when the shared daily budget is spent: wait at least this long "
        "before the next poll."
    )

    @classmethod
    def build(cls, updates: Updates) -> MessageUpdates:
        return cls(
            items=[MessageOut.build(view) for view in updates.items],
            team_items=[TeamMessageOut.build(message) for message in updates.team_items],
            cursor=updates.cursor,
            has_more=updates.has_more,
            poll_after_seconds=updates.poll_after_seconds,
        )
