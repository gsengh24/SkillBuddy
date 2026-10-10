"""Team chat: messages and each member's read time (ADR 0016).

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-10 20:00:00+00:00

Additive only: ``team_messages``, and a nullable ``team_members.read_at``. No existing value
is changed or deleted.

Retention: team messages are deleted 90 days after sending (MESSAGE_RETENTION_DAYS) by the
daily chat purge; they go with the team, and a person's own messages go with their account.

Storage: a message is about 0.3 KB plus about 60 B of index, stored once however many
members read it. About 60 kept per person at a time: about 20 KB per person
(docs/storage-budget.md).

Downgrade drops the table and the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of the model value at this revision.
MESSAGE_MAX_LENGTH = 2000


def upgrade() -> None:
    op.create_table(
        "team_messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_messages")),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_team_messages_team_id_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_team_messages_sender_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"char_length(body) BETWEEN 1 AND {MESSAGE_MAX_LENGTH}",
            name=op.f("ck_team_messages_body_length"),
        ),
    )
    op.create_index(
        "ix_team_messages_team_id_created_at", "team_messages", ["team_id", "created_at", "id"]
    )
    op.create_index(
        "ix_team_messages_created_at_brin",
        "team_messages",
        ["created_at"],
        postgresql_using="brin",
    )
    op.add_column("team_members", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("team_members", "read_at")
    op.drop_index("ix_team_messages_created_at_brin", table_name="team_messages")
    op.drop_index("ix_team_messages_team_id_created_at", table_name="team_messages")
    op.drop_table("team_messages")
