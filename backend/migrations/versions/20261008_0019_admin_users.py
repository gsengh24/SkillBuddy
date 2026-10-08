"""Admin Users page (A2): more account statuses, suspension end, notes, search indexes.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-08 16:00:00+00:00

Additive only:
- ``users.status`` may also be ``pending`` or ``banned``; ``users.suspended_until`` (null:
  a suspension lasts until lifted). Everyone stays as they are (active by default).
- ``admin_notes``: private notes on a user, deleted with the account. A few hundred bytes
  each; admins write them rarely.
- Search and filter indexes: the ``pg_trgm`` extension (part of PostgreSQL, available on
  Neon) with trigram indexes on lower(email) and lower(display name); a GIN index on
  ``profiles.intents``; a partial index on open reports per reported user.
Downgrade reactivates pending and banned accounts, drops the indexes, the notes table and
the column. The extension stays (harmless, and other things may use it).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES_BEFORE = ("active", "paused", "suspended", "pending_deletion")
STATUSES_AFTER = ("active", "paused", "pending", "suspended", "banned", "pending_deletion")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _statuses(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_users_status_valid"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_status_valid"), "users", f"status IN ({_in(values)})")


def upgrade() -> None:
    _statuses(STATUSES_AFTER)
    op.add_column("users", sa.Column("suspended_until", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "admin_notes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_notes")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_admin_notes_user_id_users"), ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 1000", name=op.f("ck_admin_notes_body_length")
        ),
    )
    op.create_index(op.f("ix_admin_notes_user_id"), "admin_notes", ["user_id"])

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Expression indexes (case-insensitive substring search); Alembic doesn't compare these.
    op.execute(
        "CREATE INDEX ix_users_email_trgm ON users USING gin (lower(email::text) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_profiles_display_name_trgm ON profiles "
        "USING gin (lower(display_name) gin_trgm_ops)"
    )
    op.create_index("ix_users_created_at_id", "users", ["created_at", "id"])
    op.create_index("ix_profiles_intents", "profiles", ["intents"], postgresql_using="gin")
    op.create_index(
        "ix_reports_reported_id_open",
        "reports",
        ["reported_id"],
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("ix_reports_reported_id_open", table_name="reports")
    op.drop_index("ix_profiles_intents", table_name="profiles")
    op.drop_index("ix_users_created_at_id", table_name="users")
    op.execute("DROP INDEX IF EXISTS ix_profiles_display_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    op.drop_index(op.f("ix_admin_notes_user_id"), table_name="admin_notes")
    op.drop_table("admin_notes")
    op.drop_column("users", "suspended_until")
    op.execute("UPDATE users SET status = 'active' WHERE status IN ('pending', 'banned')")
    _statuses(STATUSES_BEFORE)
