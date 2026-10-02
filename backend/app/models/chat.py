"""Chat messages between connected people (ARCHITECTURE.md §5-6; ADR 0012).

A message belongs to a connection, so contact is only possible after a two-sided accept.
The sender is always one of the connection's two people, stored as ``from_a`` (from
``user_a``) rather than a user id: smaller, and it can never point at an outsider.

Retention (storage rules, CLAUDE.md): messages are purged daily after
``MESSAGE_RETENTION_DAYS`` (90); they go with their connection when either account is
deleted (ON DELETE CASCADE). Read state lives on the connection (``user_a_read_at``,
``user_b_read_at``).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

MESSAGE_MAX_LENGTH = 2000


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MESSAGE_MAX_LENGTH}", name="body_length"
        ),
        # History and polling: one conversation, in time order.
        Index("ix_messages_connection_id_created_at", "connection_id", "created_at", "id"),
        # The daily retention purge (a BRIN index is a few KB for an append-only time column).
        Index("ix_messages_created_at_brin", "created_at", postgresql_using="brin"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE")
    )
    from_a: Mapped[bool]
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
