"""Indexes for the admin Overview (A4): counts by period.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-08 18:00:00+00:00

Additive only: BRIN indexes on ``created_at`` of match_requests, matches, intros,
connections and messages (append-mostly tables: a BRIN index is a few pages), and a
B-tree index on ``users.last_login_at``. Downgrade drops them.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BRIN_TABLES = ("match_requests", "matches", "intros", "connections", "messages")


def upgrade() -> None:
    for table in BRIN_TABLES:
        op.create_index(
            f"ix_{table}_created_at_brin", table, ["created_at"], postgresql_using="brin"
        )
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"])


def downgrade() -> None:
    op.drop_index("ix_users_last_login_at", table_name="users")
    for table in reversed(BRIN_TABLES):
        op.drop_index(f"ix_{table}_created_at_brin", table_name=table)
