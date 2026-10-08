"""Banners and the email send log (A8).

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-09 15:00:00+00:00

Additive only:
- ``banners``: a message (at most 160 characters, plain text) shown at the top of the app
  until it ends. Deleted 90 days after it ends. A few a month.
- ``email_sends``: one row per email the app tries to send (address, template, delivered
  or failed, a short error summary, and the job to retry it with; never the body). Kept 30
  days, removed lazily as new emails are logged.
Downgrade drops both tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "banners",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_banners")),
        sa.CheckConstraint(
            "kind IN ('info', 'warning', 'maintenance')", name=op.f("ck_banners_kind_valid")
        ),
        sa.CheckConstraint(
            "char_length(message) BETWEEN 1 AND 160", name=op.f("ck_banners_message_length")
        ),
    )
    op.create_index(op.f("ix_banners_created_at"), "banners", ["created_at"])

    op.create_table(
        "email_sends",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("to_email", sa.String(length=254), nullable=False),
        sa.Column("template", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.String(length=200), nullable=True),
        sa.Column("retry_kind", sa.String(length=64), nullable=True),
        sa.Column("retry_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retried_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_sends")),
        sa.CheckConstraint(
            "status IN ('delivered', 'failed')", name=op.f("ck_email_sends_status_valid")
        ),
    )
    op.create_index(op.f("ix_email_sends_created_at"), "email_sends", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_sends_created_at"), table_name="email_sends")
    op.drop_table("email_sends")
    op.drop_index(op.f("ix_banners_created_at"), table_name="banners")
    op.drop_table("banners")
