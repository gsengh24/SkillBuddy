"""Reports of pair-space goals and progress notes (ADR 0013).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-05 09:00:00+00:00

Widens the ``reports.target`` check to allow ``goal`` and ``progress_log``. No existing
value is changed. Downgrade deletes reports of those two kinds (they can't exist before
this revision) and restores the narrower check.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the allowed values before and after this revision.
BEFORE = ("message", "intro", "profile")
AFTER = (*BEFORE, "goal", "progress_log")


def _check(values: Sequence[str]) -> str:
    return "target IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_reports_target_valid"), "reports", type_="check")
    op.create_check_constraint(op.f("ck_reports_target_valid"), "reports", _check(AFTER))


def downgrade() -> None:
    op.execute("DELETE FROM reports WHERE target IN ('goal', 'progress_log')")
    op.drop_constraint(op.f("ck_reports_target_valid"), "reports", type_="check")
    op.create_check_constraint(op.f("ck_reports_target_valid"), "reports", _check(BEFORE))
