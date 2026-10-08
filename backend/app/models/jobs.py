"""Background-job queue, rate-limit counters and the email send log (ADR 0008).

These tables replace Arq and Valkey. Retention (storage rules, CLAUDE.md), applied by the
hourly ``purge_job_tables`` job:

- ``jobs``: succeeded rows after ``JOB_SUCCEEDED_RETENTION_DAYS`` (7), dead rows after
  ``JOB_DEAD_RETENTION_DAYS`` (30). Queued and running rows are never purged.
- ``rate_limit_counters``: once their window has expired.
- ``email_log``: after ``EMAIL_LOG_RETENTION_DAYS`` (30).

No personal data is stored: job payloads hold IDs only (a login code stays in process
memory), counter keys and email recipients are keyed hashes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.auth import DIGEST_LENGTH

JOB_KIND_MAX_LENGTH = 64
JOB_DEDUPE_KEY_MAX_LENGTH = 200
JOB_ERROR_MAX_LENGTH = 500
RATE_LIMIT_KEY_MAX_LENGTH = 160


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEAD = "dead"


JOB_STATUSES_SQL = ", ".join(f"'{status.value}'" for status in JobStatus)


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One unit of background work, claimed with ``FOR UPDATE SKIP LOCKED``.

    A failed attempt goes back to ``queued`` with a later ``run_at``; after
    ``max_attempts`` it becomes ``dead``. ``locked_until`` is the lease of a running job:
    once it passes, the job may be claimed again (its process died).
    """

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status IN ({JOB_STATUSES_SQL})", name="status_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        CheckConstraint("priority >= 0", name="priority_non_negative"),
        CheckConstraint(
            "status <> 'running' OR locked_until IS NOT NULL", name="running_has_lease"
        ),
        CheckConstraint(
            "status NOT IN ('succeeded', 'dead') OR finished_at IS NOT NULL",
            name="finished_has_time",
        ),
        # The claim query: next queued job by priority, then due time.
        Index("ix_jobs_claim", "priority", "run_at", postgresql_where=text("status = 'queued'")),
        # Lease recovery: running jobs whose process died.
        Index("ix_jobs_lease", "locked_until", postgresql_where=text("status = 'running'")),
    )

    kind: Mapped[str] = mapped_column(String(JOB_KIND_MAX_LENGTH))
    # IDs and small parameters only; never secrets or raw personal text.
    payload: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(16), default=JobStatus.QUEUED, server_default=text("'queued'")
    )
    # Lower runs first (login-code email before AI work).
    priority: Mapped[int] = mapped_column(SmallInteger, default=100, server_default=text("100"))
    run_at: Mapped[datetime] = mapped_column(server_default=func.now())
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(default=5, server_default=text("5"))
    locked_until: Mapped[datetime | None]
    # Idempotent enqueue, e.g. "hard_delete_accounts:2026-10-01".
    dedupe_key: Mapped[str | None] = mapped_column(String(JOB_DEDUPE_KEY_MAX_LENGTH), unique=True)
    # Truncated; exception type and message only, never personal data.
    last_error: Mapped[str | None] = mapped_column(String(JOB_ERROR_MAX_LENGTH))
    finished_at: Mapped[datetime | None]


class RateLimitCounter(UUIDPrimaryKeyMixin, Base):
    """A fixed-window counter, incremented with ``INSERT ... ON CONFLICT DO UPDATE``."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        UniqueConstraint("key", "window_start"),
        CheckConstraint("count >= 0", name="count_non_negative"),
    )

    # e.g. "otp_request:email:<keyed hash>"; never a raw email address or IP.
    key: Mapped[str] = mapped_column(String(RATE_LIMIT_KEY_MAX_LENGTH))
    window_start: Mapped[datetime]
    count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)


class EmailPurpose(StrEnum):
    LOGIN_CODE = "login_code"
    NOTIFICATION = "notification"
    DATA_EXPORT = "data_export"
    # A warning, suspension or ban, or an appeal's outcome (A3).
    SAFETY_NOTICE = "safety_notice"
    # An approved application's invite (A5).
    INVITE = "invite"


EMAIL_PURPOSES_SQL = ", ".join(f"'{purpose.value}'" for purpose in EmailPurpose)


class EmailLog(UUIDPrimaryKeyMixin, Base):
    """One row per recipient of a sent email: counts sends against the daily cap.

    Metadata only; the address is a keyed hash and no message content is kept.
    """

    __tablename__ = "email_log"
    __table_args__ = (CheckConstraint(f"purpose IN ({EMAIL_PURPOSES_SQL})", name="purpose_valid"),)

    purpose: Mapped[str] = mapped_column(String(32))
    recipient_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH))
    provider: Mapped[str] = mapped_column(String(32))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    # The send time: a row is written once the provider accepted the message.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
