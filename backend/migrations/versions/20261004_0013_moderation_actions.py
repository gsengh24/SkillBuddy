"""Audit log of moderator actions.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-04 18:00:00+00:00

One new table (``moderation_actions``). No existing value is changed or deleted.

Retention: rows are deleted daily after MODERATION_LOG_RETENTION_DAYS (365). Ids are set
to NULL when the moderator, the account or the report is deleted.

Storage: about 0.2 KB per action (note up to 500 characters, usually short). A few actions
a day at campus scale: well under 5 MB a year (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
ACTIONS = ("resolve_report", "suspend_user", "unsuspend_user")
NOTE_MAX_LENGTH = 500


def upgrade() -> None:
    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("moderator_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("report_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_moderation_actions")),
        sa.ForeignKeyConstraint(
            ["moderator_id"],
            ["users.id"],
            name=op.f("fk_moderation_actions_moderator_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["users.id"],
            name=op.f("fk_moderation_actions_subject_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_moderation_actions_report_id_reports"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "action IN (" + ", ".join(f"'{a}'" for a in ACTIONS) + ")",
            name=op.f("ck_moderation_actions_action_valid"),
        ),
        sa.CheckConstraint(
            f"char_length(note) <= {NOTE_MAX_LENGTH}",
            name=op.f("ck_moderation_actions_note_length"),
        ),
    )
    op.create_index(
        "ix_moderation_actions_created_at_brin",
        "moderation_actions",
        ["created_at"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind = 'purge_moderation_log'")
    op.drop_index("ix_moderation_actions_created_at_brin", table_name="moderation_actions")
    op.drop_table("moderation_actions")
