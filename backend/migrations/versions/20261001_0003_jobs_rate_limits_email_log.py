"""Background jobs, rate-limit counters and the email send log (ADR 0008).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01 00:00:00+00:00

New tables only; nothing existing changes. They replace Arq and Valkey in later steps.

Retention (storage rules): succeeded jobs after 7 days and dead jobs after 30, expired
rate-limit counters, and email_log rows after 30 days, all purged by an hourly job.
Estimated growth at campus scale: jobs about 300 B per row (under 1 MB), counters a few
KB, email_log about 150 B per sent email (under 2 MB).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
JOB_STATUSES = ("queued", "running", "succeeded", "dead")
EMAIL_PURPOSES = ("login_code", "notification")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("100"), nullable=False),
        sa.Column(
            "run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_jobs_dedupe_key")),
        sa.CheckConstraint(f"status IN ({_in(JOB_STATUSES)})", name=op.f("ck_jobs_status_valid")),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_jobs_attempts_non_negative")),
        sa.CheckConstraint("max_attempts >= 1", name=op.f("ck_jobs_max_attempts_positive")),
        sa.CheckConstraint("priority >= 0", name=op.f("ck_jobs_priority_non_negative")),
        sa.CheckConstraint(
            "status <> 'running' OR locked_until IS NOT NULL",
            name=op.f("ck_jobs_running_has_lease"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded', 'dead') OR finished_at IS NOT NULL",
            name=op.f("ck_jobs_finished_has_time"),
        ),
    )
    op.create_index(
        "ix_jobs_claim",
        "jobs",
        ["priority", "run_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_jobs_lease", "jobs", ["locked_until"], postgresql_where=sa.text("status = 'running'")
    )

    op.create_table(
        "rate_limit_counters",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_counters")),
        sa.UniqueConstraint(
            "key", "window_start", name=op.f("uq_rate_limit_counters_key_window_start")
        ),
        sa.CheckConstraint("count >= 0", name=op.f("ck_rate_limit_counters_count_non_negative")),
    )
    op.create_index(
        op.f("ix_rate_limit_counters_expires_at"), "rate_limit_counters", ["expires_at"]
    )

    op.create_table(
        "email_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("recipient_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_log")),
        sa.CheckConstraint(
            f"purpose IN ({_in(EMAIL_PURPOSES)})", name=op.f("ck_email_log_purpose_valid")
        ),
    )
    op.create_index(op.f("ix_email_log_created_at"), "email_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("email_log")
    op.drop_table("rate_limit_counters")
    op.drop_table("jobs")
