"""Content moderation flags and the AI call log (A7).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-09 12:00:00+00:00

Additive only:
- ``content_flags``: one row per rule matched by a saved request, bio or intro note (rule
  name and item id, never the text). Deleted with the account; decided flags 90 days after
  the decision, open ones after 180 days.
- ``ai_calls``: one row per AI provider call (provider, kind, outcome, duration, cost); no
  prompt, response or user. Kept 30 days.
- ``notifications.kind`` may also be ``content_removed``, with a nullable ``rule`` column.
Downgrade drops the tables and the column, deletes content_removed notifications and
restores the narrower check.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = ("intro_received", "intro_accepted", "matches_ready", "report_reviewed")
KINDS_AFTER = (*KINDS_BEFORE, "content_removed")
RULES = ("profanity", "links_in_bios", "contact_details", "repeated_intros", "prompt_injection")
ITEMS = ("request", "profile", "intro")
STATUSES = ("open", "kept", "removed")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _swap(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.create_table(
        "content_flags",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("rule", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_flags")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_content_flags_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(f"rule IN ({_in(RULES)})", name=op.f("ck_content_flags_rule_valid")),
        sa.CheckConstraint(
            f"item_type IN ({_in(ITEMS)})", name=op.f("ck_content_flags_item_type_valid")
        ),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_content_flags_status_valid")
        ),
    )
    op.create_index(op.f("ix_content_flags_user_id"), "content_flags", ["user_id"])
    op.create_index("ix_content_flags_status_created_at", "content_flags", ["status", "created_at"])
    op.create_index(
        "uq_content_flags_open_item_rule",
        "content_flags",
        ["item_type", "item_id", "rule"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "ai_calls",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("cost_units", sa.Integer(), nullable=True),
        sa.Column("cost_unit", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_calls")),
    )
    op.create_index(op.f("ix_ai_calls_created_at"), "ai_calls", ["created_at"])

    op.add_column("notifications", sa.Column("rule", sa.String(length=32), nullable=True))
    _swap("notifications", "kind_valid", f"kind IN ({_in(KINDS_AFTER)})")


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE kind = 'content_removed'")
    _swap("notifications", "kind_valid", f"kind IN ({_in(KINDS_BEFORE)})")
    op.drop_column("notifications", "rule")
    op.drop_index(op.f("ix_ai_calls_created_at"), table_name="ai_calls")
    op.drop_table("ai_calls")
    op.drop_index("uq_content_flags_open_item_rule", table_name="content_flags")
    op.drop_index("ix_content_flags_status_created_at", table_name="content_flags")
    op.drop_index(op.f("ix_content_flags_user_id"), table_name="content_flags")
    op.drop_table("content_flags")
