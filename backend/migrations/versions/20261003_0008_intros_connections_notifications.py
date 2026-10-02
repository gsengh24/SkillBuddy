"""Intros, connections, notifications; an email-notifications switch on profiles.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03 15:00:00+00:00

New tables, plus one new column with a default (``profiles.email_notifications``, true).
No existing value is changed or deleted.

Retention: intros are deleted with the match they came from (90 days after the match
request); connections last until either account is deleted; notifications are purged
daily after NOTIFICATION_RETENTION_DAYS (90).

Storage: an intro is about 0.8 KB (note up to 500 characters), a notification about
0.2 KB, a connection about 0.15 KB. At a few intros and 20 notifications per active user
per 90 days, about 6 KB per user (docs/storage-budget.md).
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
INTRO_STATUSES = ("pending", "accepted", "declined", "withdrawn", "expired")
NOTIFICATION_KINDS = ("intro_received", "intro_accepted", "matches_ready")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _uuid_pk() -> sa.Column[Any]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column[Any]:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "email_notifications", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )

    op.create_table(
        "intros",
        _uuid_pk(),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intros")),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name=op.f("fk_intros_match_id_matches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], name=op.f("fk_intros_sender_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_intros_recipient_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("match_id", name=op.f("uq_intros_match_id")),
        sa.CheckConstraint(
            f"status IN ({_in(INTRO_STATUSES)})", name=op.f("ck_intros_status_valid")
        ),
        sa.CheckConstraint("char_length(note) <= 500", name=op.f("ck_intros_note_length")),
        sa.CheckConstraint("sender_id <> recipient_id", name=op.f("ck_intros_not_self")),
    )
    op.create_index(op.f("ix_intros_sender_id"), "intros", ["sender_id"])
    op.create_index(op.f("ix_intros_expires_at"), "intros", ["expires_at"])
    op.create_index("ix_intros_recipient_id_status", "intros", ["recipient_id", "status"])

    op.create_table(
        "connections",
        _uuid_pk(),
        sa.Column("user_a", sa.UUID(), nullable=False),
        sa.Column("user_b", sa.UUID(), nullable=False),
        sa.Column("intro_id", sa.UUID(), nullable=True),
        _now("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
        sa.ForeignKeyConstraint(
            ["user_a"], ["users.id"], name=op.f("fk_connections_user_a_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_b"], ["users.id"], name=op.f("fk_connections_user_b_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["intro_id"],
            ["intros.id"],
            name=op.f("fk_connections_intro_id_intros"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_a", "user_b", name=op.f("uq_connections_user_a_user_b")),
        sa.CheckConstraint("user_a < user_b", name=op.f("ck_connections_ordered_pair")),
    )
    op.create_index(op.f("ix_connections_user_b"), "connections", ["user_b"])

    op.create_table(
        "notifications",
        _uuid_pk(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("intro_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        _now("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["intro_id"],
            ["intros.id"],
            name=op.f("fk_notifications_intro_id_intros"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["match_requests.id"],
            name=op.f("fk_notifications_request_id_match_requests"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"kind IN ({_in(NOTIFICATION_KINDS)})", name=op.f("ck_notifications_kind_valid")
        ),
    )
    op.create_index(
        "ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind = 'send_notification_email'")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_connections_user_b"), table_name="connections")
    op.drop_table("connections")
    op.drop_index("ix_intros_recipient_id_status", table_name="intros")
    op.drop_index(op.f("ix_intros_expires_at"), table_name="intros")
    op.drop_index(op.f("ix_intros_sender_id"), table_name="intros")
    op.drop_table("intros")
    op.drop_column("profiles", "email_notifications")
