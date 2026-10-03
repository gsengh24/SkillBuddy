"""Reports of intros and profiles, not only messages.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-04 14:00:00+00:00

``reports.message_id`` is renamed ``target_id`` and a ``target`` column is added
(message, intro or profile; existing reports get "message" from the column default). The
one-report-per-message rule becomes one report per reporter, target and id. No existing id,
copy, reason or status changes.

Downgrade: intro and profile reports cannot be represented before this revision, so they
are deleted; message reports are kept.

Storage: unchanged per report (one short column); intro and profile copies are smaller
than message copies (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the model values at this revision.
TARGETS = ("message", "intro", "profile")


def upgrade() -> None:
    op.drop_constraint("uq_reports_reporter_id_message_id", "reports", type_="unique")
    op.alter_column("reports", "message_id", new_column_name="target_id")
    op.add_column(
        "reports",
        sa.Column(
            "target", sa.String(length=16), server_default=sa.text("'message'"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_reports_target_valid"),
        "reports",
        "target IN (" + ", ".join(f"'{t}'" for t in TARGETS) + ")",
    )
    op.create_unique_constraint(
        op.f("uq_reports_reporter_id_target_target_id"),
        "reports",
        ["reporter_id", "target", "target_id"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM reports WHERE target <> 'message'")
    op.drop_constraint(op.f("uq_reports_reporter_id_target_target_id"), "reports", type_="unique")
    op.drop_constraint(op.f("ck_reports_target_valid"), "reports", type_="check")
    op.drop_column("reports", "target")
    op.alter_column("reports", "target_id", new_column_name="message_id")
    op.create_unique_constraint(
        "uq_reports_reporter_id_message_id", "reports", ["reporter_id", "message_id"]
    )
