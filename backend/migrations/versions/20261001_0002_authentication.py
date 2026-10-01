"""Authentication: identities, one-time codes, sessions, audit log; account lifecycle columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01 00:00:00+00:00

Moves the sign-in method from ``users.auth_provider`` to ``auth_identities`` so that Google
sign-in can be added later as another identity (ADR 0006).

Retention (storage rules): otp_codes and sessions are purged after expiry, auth_events
after a fixed number of days, and users with their rows (ON DELETE CASCADE) by the
hard-delete job after the deletion grace period.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
AUTH_EVENT_TYPES = (
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


def _uuid_pk() -> sa.Column[Any]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created_at() -> sa.Column[Any]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], name=op.f(f"fk_{table}_user_id_users"), ondelete="CASCADE"
    )


def upgrade() -> None:
    # --- users: the sign-in method moves to auth_identities -----------------------------
    op.drop_constraint(op.f("ck_users_auth_provider_valid"), "users", type_="check")
    op.drop_column("users", "auth_provider")
    op.drop_constraint(op.f("ck_users_status_valid"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_status_valid"),
        "users",
        "status IN ('active', 'suspended', 'pending_deletion')",
    )
    op.create_check_constraint(op.f("ck_users_email_length"), "users", "char_length(email) <= 254")
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.add_column(
        "users", sa.Column("deletion_scheduled_for", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(op.f("ix_users_deletion_scheduled_for"), "users", ["deletion_scheduled_for"])

    # --- auth_identities --------------------------------------------------------------
    op.create_table(
        "auth_identities",
        _uuid_pk(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_identities")),
        _user_fk("auth_identities"),
        sa.UniqueConstraint(
            "provider", "subject", name=op.f("uq_auth_identities_provider_subject")
        ),
        sa.CheckConstraint(
            "provider IN ('email', 'google')", name=op.f("ck_auth_identities_provider_valid")
        ),
    )
    op.create_index(op.f("ix_auth_identities_user_id"), "auth_identities", ["user_id"])

    # --- otp_codes --------------------------------------------------------------------
    op.create_table(
        "otp_codes",
        _uuid_pk(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        _created_at(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", sa.String(length=45), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_codes")),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_otp_codes_attempts_non_negative")),
    )
    op.create_index(op.f("ix_otp_codes_email"), "otp_codes", ["email"])
    op.create_index(op.f("ix_otp_codes_expires_at"), "otp_codes", ["expires_at"])

    # --- sessions ---------------------------------------------------------------------
    op.create_table(
        "sessions",
        _uuid_pk(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _created_at(),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        _user_fk("sessions"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"])
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"])

    # --- auth_events (append-only) ----------------------------------------------------
    event_types = ", ".join(f"'{event}'" for event in AUTH_EVENT_TYPES)
    op.create_table(
        "auth_events",
        _uuid_pk(),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_events")),
        _user_fk("auth_events"),
        sa.CheckConstraint(
            f"event_type IN ({event_types})", name=op.f("ck_auth_events_event_type_valid")
        ),
    )
    op.create_index(op.f("ix_auth_events_user_id"), "auth_events", ["user_id"])
    op.create_index(op.f("ix_auth_events_created_at"), "auth_events", ["created_at"])
    op.execute(
        """
        CREATE FUNCTION auth_events_reject_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'auth_events is append-only';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER auth_events_append_only BEFORE UPDATE ON auth_events "
        "FOR EACH ROW EXECUTE FUNCTION auth_events_reject_update()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS auth_events_append_only ON auth_events")
    op.execute("DROP FUNCTION IF EXISTS auth_events_reject_update()")
    op.drop_table("auth_events")
    op.drop_table("sessions")
    op.drop_table("otp_codes")
    op.drop_table("auth_identities")

    op.drop_index(op.f("ix_users_deletion_scheduled_for"), table_name="users")
    for column in (
        "deletion_scheduled_for",
        "terms_version",
        "terms_accepted_at",
        "age_confirmed_at",
        "last_login_at",
    ):
        op.drop_column("users", column)
    op.drop_constraint(op.f("ck_users_email_length"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_status_valid"), "users", type_="check")
    op.execute("UPDATE users SET status = 'deleted' WHERE status = 'pending_deletion'")
    op.create_check_constraint(
        op.f("ck_users_status_valid"), "users", "status IN ('active', 'suspended', 'deleted')"
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider", sa.String(length=32), server_default=sa.text("'email'"), nullable=False
        ),
    )
    op.alter_column("users", "auth_provider", server_default=None)
    op.create_check_constraint(
        op.f("ck_users_auth_provider_valid"), "users", "auth_provider IN ('email', 'google')"
    )
