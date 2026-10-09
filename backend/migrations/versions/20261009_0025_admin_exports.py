"""Admin CSV exports (A9).

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-09 18:00:00+00:00

Additive only: ``admin_exports``, one row per CSV export of the Users list or the audit log,
built in the background. The gzipped file is kept in the row for 24 hours after it is ready,
then dropped; the row is deleted 30 days after it was asked for. Downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_exports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("payload", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_exports")),
        sa.CheckConstraint("kind IN ('users', 'audit')", name=op.f("ck_admin_exports_kind_valid")),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed', 'expired')",
            name=op.f("ck_admin_exports_status_valid"),
        ),
    )
    op.create_index(op.f("ix_admin_exports_created_at"), "admin_exports", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_exports_created_at"), table_name="admin_exports")
    op.drop_table("admin_exports")
