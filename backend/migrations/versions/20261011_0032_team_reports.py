"""Reports and content flags for teams (ADR 0016).

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-11 15:00:00+00:00

``reports.target`` may also be ``team`` or ``team_message``; ``content_flags.item_type`` may
also be ``team``. Only the two CHECK constraints change; no row is changed.

Retention: unchanged. Team reports follow the rules for every report (their frozen copy is
deleted REPORT_RETENTION_DAYS after resolving); team flags follow the rules for every flag.

Downgrade deletes reports and flags of the new kinds, then restores the narrower checks.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGETS_BEFORE = ("message", "intro", "profile", "goal", "progress_log")
TARGETS_AFTER = (*TARGETS_BEFORE, "team", "team_message")
ITEMS_BEFORE = ("request", "profile", "intro")
ITEMS_AFTER = (*ITEMS_BEFORE, "team")


def _swap(table: str, name: str, column: str, values: Sequence[str]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"{column} IN ({allowed})")


def upgrade() -> None:
    _swap("reports", "target_valid", "target", TARGETS_AFTER)
    _swap("content_flags", "item_type_valid", "item_type", ITEMS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM reports WHERE target IN ('team', 'team_message')")
    op.execute("DELETE FROM content_flags WHERE item_type = 'team'")
    _swap("content_flags", "item_type_valid", "item_type", ITEMS_BEFORE)
    _swap("reports", "target_valid", "target", TARGETS_BEFORE)
