"""Process-local storage for job secrets (ADR 0008).

A login code must never be written to the jobs table, so it is kept here, keyed by job id,
until the job has run. Entries expire, so a job that never runs (its transaction rolled
back, or it was claimed by another process) cannot leave a secret behind for long. A
restart loses every entry; the job then fails as ``SecretUnavailable``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable


class EphemeralSecrets:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[uuid.UUID, tuple[str, float]] = {}

    def put(self, job_id: uuid.UUID, secret: str, *, ttl_seconds: float) -> None:
        self._purge_expired()
        self._entries[job_id] = (secret, self._clock() + ttl_seconds)

    def get(self, job_id: uuid.UUID) -> str | None:
        self._purge_expired()
        entry = self._entries.get(job_id)
        return None if entry is None else entry[0]

    def discard(self, job_id: uuid.UUID) -> None:
        self._entries.pop(job_id, None)

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._entries)

    def _purge_expired(self) -> None:
        now = self._clock()
        for job_id in [k for k, (_, expires) in self._entries.items() if expires <= now]:
            del self._entries[job_id]


# One store per process, shared by enqueue() and the runner in that process.
secret_store = EphemeralSecrets()
