"""Match requests and the matches made for them (ARCHITECTURE.md §5; ADR 0007 stages 2-4).

Retention (storage rules, CLAUDE.md): a request is open for REQUEST_TTL_DAYS, then
expires; the daily purge deletes requests (and their matches, ON DELETE CASCADE) once they
are older than ``match_request_retention_days``. Account deletion removes both.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

REQUEST_TEXT_MIN_LENGTH = 10
REQUEST_TEXT_MAX_LENGTH = 1000
REASON_MAX_LENGTH = 300


class RequestStatus(StrEnum):
    # Saved; the match_request job will read it and find matches.
    PENDING = "pending"
    # Matches are ready (possibly none yet: "waiting for a match").
    READY = "ready"
    # Closed by the user, or past expires_at.
    CLOSED = "closed"
    EXPIRED = "expired"


class MatchStatus(StrEnum):
    SHOWN = "shown"
    VIEWED = "viewed"
    INTRO_SENT = "intro_sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


INTENTS = (
    "build_together",
    "skill_exchange",
    "interest_buddy",
    "accountability",
    "mentor",
    "explore",
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class MatchRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What someone asked for, in their own words, plus what the matcher understood."""

    __tablename__ = "match_requests"
    __table_args__ = (
        Index("ix_match_requests_created_at_brin", "created_at", postgresql_using="brin"),
        CheckConstraint(f"status IN ({_in(tuple(RequestStatus))})", name="status_valid"),
        CheckConstraint(f"intent IS NULL OR intent IN ({_in(INTENTS)})", name="intent_valid"),
        CheckConstraint(
            f"requested_intent IS NULL OR requested_intent IN ({_in(INTENTS)})",
            name="requested_intent_valid",
        ),
        CheckConstraint(
            f"char_length(raw_text) <= {REQUEST_TEXT_MAX_LENGTH}", name="raw_text_length"
        ),
        CheckConstraint(
            "explanation_source IS NULL OR explanation_source IN ('llm', 'template')",
            name="explanation_source_valid",
        ),
        Index("ix_match_requests_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(Text)
    # Set when a team's owner is looking for a teammate (ADR 0016): the team's members
    # are left out of the matches, and a match can be invited to the team.
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    # The intent chip the user picked, if any; ``intent`` is what the matcher used.
    requested_intent: Mapped[str | None] = mapped_column(String(32))
    intent: Mapped[str | None] = mapped_column(String(32))
    structured: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(16), default=RequestStatus.PENDING, server_default=text("'pending'")
    )
    # Who chose and explained the matches, and with which prompt (ADR 0007, section 5).
    explanation_source: Mapped[str | None] = mapped_column(String(16))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    matched_at: Mapped[datetime | None]
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Match(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One suggested person for one request, with the reason shown to both sides."""

    __tablename__ = "matches"
    __table_args__ = (
        # Admin Overview counts by period (A4); BRIN suits an append-mostly table.
        Index("ix_matches_created_at_brin", "created_at", postgresql_using="brin"),
        UniqueConstraint("request_id", "candidate_id"),
        CheckConstraint(f"status IN ({_in(tuple(MatchStatus))})", name="status_valid"),
        CheckConstraint("rank >= 1", name="rank_positive"),
        CheckConstraint(f"char_length(reason) <= {REASON_MAX_LENGTH}", name="reason_length"),
        Index("ix_matches_candidate_id_created_at", "candidate_id", "created_at"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_requests.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rank: Mapped[int]
    score: Mapped[float]
    reason: Mapped[str] = mapped_column(String(REASON_MAX_LENGTH))
    status: Mapped[str] = mapped_column(
        String(16), default=MatchStatus.SHOWN, server_default=text("'shown'")
    )
