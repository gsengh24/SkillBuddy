"""Blocks between people; an end time on connections.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-04 10:00:00+00:00

One new table (``blocks``) and one new nullable column (``connections.ended_at``; empty
means the connection is open). No existing value is changed or deleted, and nothing is
backfilled.

Retention: a block lasts until the blocker removes it or either account is deleted. An
ended connection lasts until either account is deleted; its messages are purged after 90
days like any others.

Storage: a block is about 0.1 KB plus two index entries; people block rarely (a few per
user at most), so well under 1 KB per user (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("connections", sa.Column("ended_at", sa.DateTime(timezone=True)))
    op.create_table(
        "blocks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("blocker_id", sa.UUID(), nullable=False),
        sa.Column("blocked_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blocks")),
        sa.ForeignKeyConstraint(
            ["blocker_id"],
            ["users.id"],
            name=op.f("fk_blocks_blocker_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["blocked_id"],
            ["users.id"],
            name=op.f("fk_blocks_blocked_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "blocker_id", "blocked_id", name=op.f("uq_blocks_blocker_id_blocked_id")
        ),
        sa.CheckConstraint("blocker_id <> blocked_id", name=op.f("ck_blocks_not_self")),
    )
    op.create_index(op.f("ix_blocks_blocked_id"), "blocks", ["blocked_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_blocks_blocked_id"), table_name="blocks")
    op.drop_table("blocks")
    op.drop_column("connections", "ended_at")
