"""Teams: groups of up to six people (ADR 0016).

Unlike a pair space, a team has rows of its own: a name, an owner, and members who come and
go. A person joins only by their own action (here: accepting the owner's invite).

Retention (storage rules, CLAUDE.md): a closed team is hidden at once and deleted
``TEAM_RETENTION_DAYS`` (90) later with everything in it; pending invites expire after
``TEAM_INVITE_TTL_DAYS`` and answered or expired ones are deleted after the same 90 days; a
membership row is deleted when the person leaves or is removed. Account deletion removes a
person's memberships and invites (ON DELETE CASCADE); a team they owned passes to its
longest-standing member.

Team chat (``team_messages``): messages are purged daily after ``MESSAGE_RETENTION_DAYS``
(90), like one-to-one chat; they go with the team, and a person's own messages go with
their account. Read state is ``team_members.read_at``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.chat import MESSAGE_MAX_LENGTH

TEAM_NAME_MAX_LENGTH = 60
TEAM_DESCRIPTION_MAX_LENGTH = 300
TEAM_LOOKING_FOR_MAX_LENGTH = 200
TEAM_REQUEST_NOTE_MAX_LENGTH = 300
MAX_TEAM_MEMBERS = 6
MAX_TEAMS_PER_PERSON = 5
MAX_TEAMS_OWNED = 3
MAX_PENDING_PER_TEAM = 20
TEAM_INVITE_TTL_DAYS = 14
TEAM_LINK_TTL_DAYS = 7


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class TeamPurpose(StrEnum):
    HACKATHON = "hackathon"
    PROJECT = "project"
    STUDY = "study"
    OTHER = "other"


class TeamInviteKind(StrEnum):
    # The owner invited someone they are connected with.
    INVITE = "invite"
    # Someone asked to join a listed team; the owner answers.
    REQUEST = "request"
    # A later route (ADR 0016): the matcher suggested them.
    SUGGESTED = "suggested"


class TeamInviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    # Never shown to the owner: a declined invite looks pending until it expires.
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class Team(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {TEAM_NAME_MAX_LENGTH}", name="name_length"
        ),
        CheckConstraint(
            f"char_length(description) <= {TEAM_DESCRIPTION_MAX_LENGTH}", name="description_length"
        ),
        CheckConstraint(f"purpose IN ({_in(tuple(TeamPurpose))})", name="purpose_valid"),
        CheckConstraint(
            f"char_length(looking_for) <= {TEAM_LOOKING_FOR_MAX_LENGTH}", name="looking_for_length"
        ),
        # Browsing listed teams, newest first.
        Index(
            "ix_teams_listed_created_at",
            "created_at",
            "id",
            postgresql_where=text("listed AND closed_at IS NULL"),
        ),
        # The daily purge of teams closed long enough ago.
        Index("ix_teams_closed_at", "closed_at", postgresql_where=text("closed_at IS NOT NULL")),
    )

    name: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # Empty only between an owner's account being deleted and the daily job passing the team
    # to its longest-standing member.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # A closed team is hidden from everyone at once and deleted 90 days later.
    closed_at: Mapped[datetime | None]
    # The invite link: only a keyed hash of its code is stored, like sign-in codes. Making
    # a new link replaces the old one.
    invite_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    invite_expires_at: Mapped[datetime | None]
    # A listed team can be found by any signed-in person, who may ask to join. The
    # "looking for" line is shown with it.
    listed: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    looking_for: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))


class TeamMember(UUIDPrimaryKeyMixin, Base):
    """One person in one team. ``created_at`` is when they joined."""

    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Team chat: this person has read every message up to this time.
    read_at: Mapped[datetime | None]


class TeamInvite(UUIDPrimaryKeyMixin, Base):
    """Someone who may join a team once they (or, for a request, the owner) say yes."""

    __tablename__ = "team_invites"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in(tuple(TeamInviteKind))})", name="kind_valid"),
        CheckConstraint(f"status IN ({_in(tuple(TeamInviteStatus))})", name="status_valid"),
        CheckConstraint(f"char_length(note) <= {TEAM_REQUEST_NOTE_MAX_LENGTH}", name="note_length"),
        # One open invite per team and person.
        Index(
            "uq_team_invites_pending",
            "team_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_team_invites_user_id_status", "user_id", "status"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default=TeamInviteStatus.PENDING, server_default=text("'pending'")
    )
    # What someone asking to join wrote to the owner; empty for invites.
    note: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    responded_at: Mapped[datetime | None]
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TeamMessage(UUIDPrimaryKeyMixin, Base):
    """One message in a team's chat. The sender is a user id: a team has more than two
    people, so the ``from_a`` flag of one-to-one chat cannot be used."""

    __tablename__ = "team_messages"
    __table_args__ = (
        CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MESSAGE_MAX_LENGTH}", name="body_length"
        ),
        # History and polling: one team, in time order.
        Index("ix_team_messages_team_id_created_at", "team_id", "created_at", "id"),
        # The daily retention purge (a BRIN index is a few KB for an append-only time column).
        Index("ix_team_messages_created_at_brin", "created_at", postgresql_using="brin"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
