"""Chat messages; read state on connections (ADR 0012).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03 21:00:00+00:00

One new table (``messages``) and two new nullable columns on ``connections``
(``user_a_read_at``, ``user_b_read_at``; empty means "nothing read yet"). No existing value
is changed or deleted, and nothing is backfilled.

Retention: messages are purged daily after MESSAGE_RETENTION_DAYS (90), and go with their
connection when either account is deleted.

Storage: a message is about 0.3 KB on average (body up to 2,000 characters, typically
short) plus about 60 B of index. At the budgeted 100 messages per user kept at a time,
about 30 KB per user (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the model value at this revision.
MESSAGE_MAX_LENGTH = 2000


def upgrade() -> None:
    op.add_column("connections", sa.Column("user_a_read_at", sa.DateTime(timezone=True)))
    op.add_column("connections", sa.Column("user_b_read_at", sa.DateTime(timezone=True)))

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("from_a", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_messages_connection_id_connections"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MESSAGE_MAX_LENGTH}",
            name=op.f("ck_messages_body_length"),
        ),
    )
    op.create_index(
        "ix_messages_connection_id_created_at",
        "messages",
        ["connection_id", "created_at", "id"],
    )
    op.create_index(
        "ix_messages_created_at_brin", "messages", ["created_at"], postgresql_using="brin"
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind = 'purge_messages'")
    op.drop_index("ix_messages_created_at_brin", table_name="messages")
    op.drop_index("ix_messages_connection_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_column("connections", "user_b_read_at")
    op.drop_column("connections", "user_a_read_at")
