"""Reports and safety (A3): report review status and decisions, appeals, notices.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-08 17:00:00+00:00

Additive only:
- ``reports.status`` may also be ``in_review``; new ``decision`` (dismiss, warn, suspend,
  ban) and ``decided_by``. Existing reports keep their status and have no decision.
- ``notifications.kind`` may also be ``report_reviewed``; ``email_log.purpose`` may also be
  ``safety_notice``.
- ``appeals``: one per suspension or ban, deleted with the account or 180 days after it is
  decided. Up to 1,000 characters each; rare.
Downgrade deletes in-review status (back to open), the new notifications and email log
rows, the appeals table and the new columns, and restores the narrower checks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPORT_STATUSES_BEFORE = ("open", "resolved")
REPORT_STATUSES_AFTER = ("open", "in_review", "resolved")
DECISIONS = ("dismiss", "warn", "suspend", "ban")
KINDS_BEFORE = ("intro_received", "intro_accepted", "matches_ready")
KINDS_AFTER = (*KINDS_BEFORE, "report_reviewed")
PURPOSES_BEFORE = ("login_code", "notification", "data_export")
PURPOSES_AFTER = (*PURPOSES_BEFORE, "safety_notice")
APPEAL_STATUSES = ("open", "upheld", "overturned")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _swap(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    _swap("reports", "status_valid", f"status IN ({_in(REPORT_STATUSES_AFTER)})")
    op.add_column("reports", sa.Column("decision", sa.String(length=16), nullable=True))
    op.add_column("reports", sa.Column("decided_by", sa.UUID(), nullable=True))
    op.create_check_constraint(
        op.f("ck_reports_decision_valid"),
        "reports",
        f"decision IS NULL OR decision IN ({_in(DECISIONS)})",
    )
    _swap("notifications", "kind_valid", f"kind IN ({_in(KINDS_AFTER)})")
    _swap("email_log", "purpose_valid", f"purpose IN ({_in(PURPOSES_AFTER)})")

    op.create_table(
        "appeals",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("against", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeals")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_appeals_user_id_users"), ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            f"status IN ({_in(APPEAL_STATUSES)})", name=op.f("ck_appeals_status_valid")
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 1000", name=op.f("ck_appeals_body_length")
        ),
    )
    op.create_index(op.f("ix_appeals_user_id"), "appeals", ["user_id"])
    op.create_index("ix_appeals_status_created_at", "appeals", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_appeals_status_created_at", table_name="appeals")
    op.drop_index(op.f("ix_appeals_user_id"), table_name="appeals")
    op.drop_table("appeals")
    op.execute("DELETE FROM email_log WHERE purpose = 'safety_notice'")
    _swap("email_log", "purpose_valid", f"purpose IN ({_in(PURPOSES_BEFORE)})")
    op.execute("DELETE FROM notifications WHERE kind = 'report_reviewed'")
    _swap("notifications", "kind_valid", f"kind IN ({_in(KINDS_BEFORE)})")
    op.drop_constraint(op.f("ck_reports_decision_valid"), "reports", type_="check")
    op.drop_column("reports", "decided_by")
    op.drop_column("reports", "decision")
    op.execute("UPDATE reports SET status = 'open' WHERE status = 'in_review'")
    _swap("reports", "status_valid", f"status IN ({_in(REPORT_STATUSES_BEFORE)})")
