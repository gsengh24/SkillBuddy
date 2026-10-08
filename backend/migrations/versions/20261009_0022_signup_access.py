"""Signup and access (A5): signup mode, email domains, applications and invite codes.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-09 09:00:00+00:00

Additive only, and the defaults keep today's behaviour: with no rows, signups are open to
any domain and no invite is needed.
- ``app_settings``: admin-set values by key (``signup_mode``). One row per key; tiny.
- ``signup_domains``: allowed and blocked domains for new accounts. Admin-entered; tiny.
- ``signup_applications``: one per address while signups are invite only. Deleted 90 days
  after a decision, or 180 days after applying if never decided.
- ``invite_codes``: shareable codes (admin-made; deleted 180 days after they expire or are
  revoked) and one-use codes for approved applications (deleted with the application).
- ``oauth_states.invite_code`` (nullable): the code typed before "Continue with Google".
- ``email_log.purpose`` may also be ``invite``.
Downgrade drops the tables and the column, deletes invite email log rows and restores the
narrower check.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES_BEFORE = ("login_code", "notification", "data_export", "safety_notice")
PURPOSES_AFTER = (*PURPOSES_BEFORE, "invite")
DOMAIN_KINDS = ("allowed", "blocked")
APPLICATION_STATUSES = ("pending", "approved", "rejected")
APPLICATION_SOURCES = ("friend", "college", "social_media", "search", "event", "other")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _swap(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )

    op.create_table(
        "signup_domains",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        _created_at(),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signup_domains")),
        sa.UniqueConstraint("kind", "domain", name=op.f("uq_signup_domains_kind_domain")),
        sa.CheckConstraint(
            f"kind IN ({_in(DOMAIN_KINDS)})", name=op.f("ck_signup_domains_kind_valid")
        ),
        sa.CheckConstraint(
            "char_length(domain) BETWEEN 3 AND 253 AND domain = lower(domain)",
            name=op.f("ck_signup_domains_domain_valid"),
        ),
    )

    op.create_table(
        "signup_applications",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        _created_at(),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signup_applications")),
        sa.UniqueConstraint("email", name=op.f("uq_signup_applications_email")),
        sa.CheckConstraint(
            f"status IN ({_in(APPLICATION_STATUSES)})",
            name=op.f("ck_signup_applications_status_valid"),
        ),
        sa.CheckConstraint(
            f"source IN ({_in(APPLICATION_SOURCES)})",
            name=op.f("ck_signup_applications_source_valid"),
        ),
        sa.CheckConstraint(
            "char_length(email) <= 254", name=op.f("ck_signup_applications_email_length")
        ),
    )
    op.create_index(
        "ix_signup_applications_status_created_at",
        "signup_applications",
        ["status", "created_at", "id"],
    )

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_invite_codes_code")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["signup_applications.id"],
            name=op.f("fk_invite_codes_application_id_signup_applications"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "max_uses BETWEEN 1 AND 10000 AND uses >= 0 AND uses <= max_uses",
            name=op.f("ck_invite_codes_uses_valid"),
        ),
        sa.CheckConstraint(
            "char_length(code) BETWEEN 4 AND 32 AND code = upper(code)",
            name=op.f("ck_invite_codes_code_valid"),
        ),
    )
    op.create_index("ix_invite_codes_created_at_id", "invite_codes", ["created_at", "id"])
    op.create_index(op.f("ix_invite_codes_application_id"), "invite_codes", ["application_id"])

    op.add_column("oauth_states", sa.Column("invite_code", sa.String(length=32), nullable=True))
    _swap("email_log", "purpose_valid", f"purpose IN ({_in(PURPOSES_AFTER)})")


def downgrade() -> None:
    op.execute("DELETE FROM email_log WHERE purpose = 'invite'")
    _swap("email_log", "purpose_valid", f"purpose IN ({_in(PURPOSES_BEFORE)})")
    op.drop_column("oauth_states", "invite_code")
    op.drop_index(op.f("ix_invite_codes_application_id"), table_name="invite_codes")
    op.drop_index("ix_invite_codes_created_at_id", table_name="invite_codes")
    op.drop_table("invite_codes")
    op.drop_index("ix_signup_applications_status_created_at", table_name="signup_applications")
    op.drop_table("signup_applications")
    op.drop_table("signup_domains")
    op.drop_table("app_settings")
