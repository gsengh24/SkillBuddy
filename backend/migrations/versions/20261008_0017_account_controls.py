"""Account controls (Prompt 12C): pause, signed-in devices, data download.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-08 13:00:00+00:00

Additive only, so the deployed code keeps working while it runs:
- ``users.status`` may also be ``paused``.
- ``email_log.purpose`` may also be ``data_export``; ``auth_events.event_type`` gains
  ``logout_others``, ``session_revoked``, ``account_paused`` and ``account_resumed``.
- New table ``data_exports``. Retention: the file is dropped when its link expires (72
  hours by default); the row is deleted 90 days after the request.

Downgrade resumes paused accounts, deletes the rows that use the new values, restores the
narrower checks and drops ``data_exports``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the allowed values before and after this revision.
STATUSES_BEFORE = ("active", "suspended", "pending_deletion")
STATUSES_AFTER = ("active", "paused", "suspended", "pending_deletion")
PURPOSES_BEFORE = ("login_code", "notification")
PURPOSES_AFTER = (*PURPOSES_BEFORE, "data_export")
EVENTS_BEFORE = (
    "otp_requested",
    "otp_failed",
    "otp_locked",
    "signup",
    "login",
    "login_refused",
    "logout",
    "logout_all",
    "deletion_requested",
    "account_deleted",
)
EVENTS_NEW = ("logout_others", "session_revoked", "account_paused", "account_resumed")
EVENTS_AFTER = (*EVENTS_BEFORE[:8], *EVENTS_NEW, *EVENTS_BEFORE[8:])
EXPORT_STATUSES = ("requested", "ready", "expired", "failed")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _swap(table: str, name: str, column: str, values: Sequence[str]) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"{column} IN ({_in(values)})")


def upgrade() -> None:
    _swap("users", "status_valid", "status", STATUSES_AFTER)
    _swap("email_log", "purpose_valid", "purpose", PURPOSES_AFTER)
    _swap("auth_events", "event_type_valid", "event_type", EVENTS_AFTER)

    op.create_table(
        "data_exports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'requested'"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.LargeBinary(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_exports")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_data_exports_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_data_exports_token_hash")),
        sa.CheckConstraint(
            f"status IN ({_in(EXPORT_STATUSES)})", name=op.f("ck_data_exports_status_valid")
        ),
    )
    op.create_index(op.f("ix_data_exports_user_id"), "data_exports", ["user_id"])
    op.create_index(op.f("ix_data_exports_created_at"), "data_exports", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_data_exports_created_at"), table_name="data_exports")
    op.drop_index(op.f("ix_data_exports_user_id"), table_name="data_exports")
    op.drop_table("data_exports")
    op.execute(f"DELETE FROM auth_events WHERE event_type IN ({_in(EVENTS_NEW)})")  # noqa: S608  # frozen constants above
    _swap("auth_events", "event_type_valid", "event_type", EVENTS_BEFORE)
    op.execute("DELETE FROM email_log WHERE purpose = 'data_export'")
    _swap("email_log", "purpose_valid", "purpose", PURPOSES_BEFORE)
    op.execute("UPDATE users SET status = 'active' WHERE status = 'paused'")
    _swap("users", "status_valid", "status", STATUSES_BEFORE)
