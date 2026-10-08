"""Content moderation flags and the AI call log (A7).

Flags only mark something for a moderator to look at; they never block or change what a
user sees. The call log keeps metadata only: never a prompt, a response or a user.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


def _in(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class ContentRule(StrEnum):
    PROFANITY = "profanity"
    LINKS_IN_BIOS = "links_in_bios"
    CONTACT_DETAILS = "contact_details"
    REPEATED_INTROS = "repeated_intros"
    PROMPT_INJECTION = "prompt_injection"


class FlaggedItem(StrEnum):
    REQUEST = "request"
    PROFILE = "profile"
    INTRO = "intro"


class FlagStatus(StrEnum):
    OPEN = "open"
    KEPT = "kept"
    REMOVED = "removed"


class ContentFlag(UUIDPrimaryKeyMixin, Base):
    """One rule matched one saved text. Deleted with the account; decided flags 90 days
    after the decision, open ones after 180 days."""

    __tablename__ = "content_flags"
    __table_args__ = (
        CheckConstraint(f"rule IN ({_in(ContentRule)})", name="rule_valid"),
        CheckConstraint(f"item_type IN ({_in(FlaggedItem)})", name="item_type_valid"),
        CheckConstraint(f"status IN ({_in(FlagStatus)})", name="status_valid"),
        # The queue: open flags, oldest first.
        Index("ix_content_flags_status_created_at", "status", "created_at"),
        # One open flag per rule and item, however often it is saved.
        Index(
            "uq_content_flags_open_item_rule",
            "item_type",
            "item_id",
            "rule",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(16))
    # A request or intro id; for a profile, the user's id.
    item_id: Mapped[uuid.UUID]
    rule: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16), default=FlagStatus.OPEN, server_default=text("'open'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[uuid.UUID | None]


class AiCall(UUIDPrimaryKeyMixin, Base):
    """One call to an AI provider: who, what kind, how long, how it went, what it cost.
    No prompt or response text, no user. Kept 30 days, removed lazily as calls are logged."""

    __tablename__ = "ai_calls"

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    # The gateway task ("understand", "select", ...) or "probe".
    kind: Mapped[str] = mapped_column(String(32))
    # "ok", "invalid", "timeout", "rate_limited", "unavailable", ...
    outcome: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int]
    cost_units: Mapped[int | None]
    cost_unit: Mapped[str | None] = mapped_column(String(16))
