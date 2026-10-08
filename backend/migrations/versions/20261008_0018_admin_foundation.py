"""Admin portal foundation (ADR 0015): roles and two-step login, admin sessions, audit log.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-08 14:00:00+00:00

Additive only: four new tables, nothing else changes.
- ``admin_accounts``: a role (admin, moderator, readonly; owners come from
  ADMIN_OWNER_EMAILS) and the encrypted TOTP secret. One row per admin; deleted with the
  account.
- ``admin_recovery_codes``: hashed single-use codes, about 10 per admin.
- ``admin_sessions``: the short second session; expired rows are purged daily.
- ``admin_audit_log``: append-only. A trigger refuses UPDATE and DELETE, so entries can't
  be edited or removed. About 1 KB per admin action, kept without a time limit.
Downgrade drops the trigger, its function and the four tables.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("admin", "moderator", "readonly")


def _id() -> sa.Column[Any]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column[Any]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _user(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], name=op.f(f"fk_{table}_user_id_users"), ondelete="CASCADE"
    )


def upgrade() -> None:
    op.create_table(
        "admin_accounts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=True),
        sa.Column("granted_by", sa.UUID(), nullable=True),
        _created(),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column("two_step_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_totp_step", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_admin_accounts")),
        _user("admin_accounts"),
        sa.CheckConstraint(
            "role IS NULL OR role IN (" + ", ".join(f"'{r}'" for r in ROLES) + ")",
            name=op.f("ck_admin_accounts_role_valid"),
        ),
    )

    op.create_table(
        "admin_recovery_codes",
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        _created(),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_recovery_codes")),
        _user("admin_recovery_codes"),
        sa.UniqueConstraint("code_hash", name=op.f("uq_admin_recovery_codes_code_hash")),
    )
    op.create_index(op.f("ix_admin_recovery_codes_user_id"), "admin_recovery_codes", ["user_id"])

    op.create_table(
        "admin_sessions",
        _id(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _created(),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_sessions")),
        _user("admin_sessions"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_admin_sessions_token_hash")),
    )
    op.create_index(op.f("ix_admin_sessions_user_id"), "admin_sessions", ["user_id"])
    op.create_index(op.f("ix_admin_sessions_expires_at"), "admin_sessions", ["expires_at"])

    op.create_table(
        "admin_audit_log",
        _id(),
        _created(),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit_log")),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) BETWEEN 10 AND 500",
            name=op.f("ck_admin_audit_log_reason_length"),
        ),
    )
    for column in ("created_at", "actor_id", "action", "target_id"):
        op.create_index(op.f(f"ix_admin_audit_log_{column}"), "admin_audit_log", [column])

    # Append-only, enforced by the database: no role can edit or remove an entry.
    op.execute(
        """
        CREATE FUNCTION admin_audit_log_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'admin_audit_log is append-only (% refused)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER admin_audit_log_append_only
        BEFORE UPDATE OR DELETE ON admin_audit_log
        FOR EACH ROW EXECUTE FUNCTION admin_audit_log_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER admin_audit_log_no_truncate
        BEFORE TRUNCATE ON admin_audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION admin_audit_log_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS admin_audit_log_no_truncate ON admin_audit_log")
    op.execute("DROP TRIGGER IF EXISTS admin_audit_log_append_only ON admin_audit_log")
    op.execute("DROP FUNCTION IF EXISTS admin_audit_log_append_only()")
    for column in ("target_id", "action", "actor_id", "created_at"):
        op.drop_index(op.f(f"ix_admin_audit_log_{column}"), table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_index(op.f("ix_admin_sessions_expires_at"), table_name="admin_sessions")
    op.drop_index(op.f("ix_admin_sessions_user_id"), table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index(op.f("ix_admin_recovery_codes_user_id"), table_name="admin_recovery_codes")
    op.drop_table("admin_recovery_codes")
    op.drop_table("admin_accounts")
