"""Reports of chat messages, with a frozen copy for the moderator.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-03 23:00:00+00:00

One new table (``reports``). No existing value is changed or deleted.

Retention: open reports are kept until resolved; resolved reports are deleted daily
REPORT_RETENTION_DAYS (180) after they were resolved. Deleting an account sets its id on
a report to NULL and keeps the copy (evidence for the moderator).

Storage: a report is about 0.5 KB plus its copy of up to 11 messages (typically a few
KB; at most about 22 KB with 2,000-character messages). Reports are rare (well under one
per user); budgeted at 5 MB in docs/storage-budget.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
REASONS = ("harassment", "spam", "scam", "inappropriate", "safety", "other")
STATUSES = ("open", "resolved")
DETAILS_MAX_LENGTH = 500
NOTE_MAX_LENGTH = 500


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=True),
        sa.Column("reported_id", sa.UUID(), nullable=True),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("details", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("resolution_note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            name=op.f("fk_reports_reporter_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reported_id"],
            ["users.id"],
            name=op.f("fk_reports_reported_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_reports_connection_id_connections"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "reporter_id", "message_id", name=op.f("uq_reports_reporter_id_message_id")
        ),
        sa.CheckConstraint(f"reason IN ({_in(REASONS)})", name=op.f("ck_reports_reason_valid")),
        sa.CheckConstraint(f"status IN ({_in(STATUSES)})", name=op.f("ck_reports_status_valid")),
        sa.CheckConstraint(
            f"char_length(details) <= {DETAILS_MAX_LENGTH}", name=op.f("ck_reports_details_length")
        ),
        sa.CheckConstraint(
            f"char_length(resolution_note) <= {NOTE_MAX_LENGTH}",
            name=op.f("ck_reports_note_length"),
        ),
    )
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind IN ('report_alerts', 'purge_reports')")
    op.drop_index("ix_reports_status_created_at", table_name="reports")
    op.drop_table("reports")
