"""Enqueue jobs inside the caller's transaction (ADR 0008).

The job row is inserted with the business write it belongs to and becomes visible only
when the caller commits; if the caller rolls back, no job exists. After the commit, the
runners in this process are woken at once, so nothing has to poll the database.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Final

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.jobs.registry import JobSpec
from app.jobs.secrets import PROCESS_ID, EphemeralSecrets, secret_store
from app.models.jobs import JOB_DEDUPE_KEY_MAX_LENGTH, Job

# Payloads carry IDs and small parameters only, never personal text.
PAYLOAD_MAX_BYTES: Final = 2048
DEFAULT_SECRET_TTL_SECONDS: Final = 15 * 60
# Payload key naming the process that holds a job's secret (set by enqueue, not callers).
RUNNER_KEY: Final = "_runner"

_wake_listeners: set[Callable[[], None]] = set()


def add_wake_listener(listener: Callable[[], None]) -> None:
    _wake_listeners.add(listener)


def remove_wake_listener(listener: Callable[[], None]) -> None:
    _wake_listeners.discard(listener)


def _wake_all(_session: Session) -> None:
    for listener in list(_wake_listeners):
        listener()


class JobPayloadError(ValueError):
    """The payload is not small, flat JSON (or a secret is missing or unexpected)."""


async def enqueue(
    db: AsyncSession,
    spec: JobSpec,
    payload: dict[str, Any] | None = None,
    *,
    run_at: datetime | None = None,
    dedupe_key: str | None = None,
    secret: str | None = None,
    secret_ttl_seconds: float = DEFAULT_SECRET_TTL_SECONDS,
    secrets: EphemeralSecrets = secret_store,
) -> uuid.UUID | None:
    """Add a job to the caller's transaction; the caller commits.

    Returns the job id, or ``None`` when a job with the same ``dedupe_key`` already exists.
    """
    payload = dict(payload or {})
    if RUNNER_KEY in payload:
        raise JobPayloadError(f"{RUNNER_KEY!r} is reserved")
    if spec.needs_secret:
        payload[RUNNER_KEY] = PROCESS_ID
    try:
        encoded = json.dumps(payload, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise JobPayloadError("job payload must be JSON-serialisable") from exc
    if len(encoded.encode()) > PAYLOAD_MAX_BYTES:
        raise JobPayloadError(f"job payload is over {PAYLOAD_MAX_BYTES} bytes")
    if spec.needs_secret != (secret is not None):
        raise JobPayloadError(f"job kind {spec.kind!r} needs_secret={spec.needs_secret}")
    if dedupe_key is not None and not 0 < len(dedupe_key) <= JOB_DEDUPE_KEY_MAX_LENGTH:
        raise JobPayloadError(f"dedupe_key must be 1-{JOB_DEDUPE_KEY_MAX_LENGTH} characters")

    job_id = uuid.uuid4()
    values: dict[str, Any] = {
        "id": job_id,
        "kind": spec.kind,
        "payload": payload,
        "priority": spec.priority,
        "max_attempts": spec.max_attempts,
        "dedupe_key": dedupe_key,
    }
    if run_at is not None:
        values["run_at"] = run_at
    statement = insert(Job).values(**values).on_conflict_do_nothing(index_elements=["dedupe_key"])
    inserted = await db.scalar(statement.returning(Job.id))
    if inserted is None:
        return None
    if secret is not None:
        secrets.put(job_id, secret, ttl_seconds=secret_ttl_seconds)
    # Sessions are short-lived, so a listener left on the session for later commits only
    # causes a harmless extra wake-up.
    if not event.contains(db.sync_session, "after_commit", _wake_all):
        event.listen(db.sync_session, "after_commit", _wake_all)
    return job_id
