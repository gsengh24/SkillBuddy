"""Job kinds: what a job is called, how it runs, and its limits."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models.jobs import JOB_KIND_MAX_LENGTH


class JobGroup(StrEnum):
    """Concurrency group. AI jobs run one at a time to protect RAM (ADR 0008)."""

    AI = "ai"
    IO = "io"


@dataclass(frozen=True)
class JobContext:
    """What a handler gets. ``secret`` is set only for kinds with ``needs_secret``."""

    job_id: uuid.UUID
    kind: str
    attempt: int
    payload: dict[str, Any]
    secret: str | None
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]


JobHandler = Callable[[JobContext], Awaitable[None]]


@dataclass(frozen=True)
class JobSpec:
    """A job kind. Handlers must be idempotent: a job can run more than once.

    ``needs_secret``: the job gets a value that is kept only in this process's memory
    (e.g. a login code), never in the jobs table. If the process restarts first, the job
    cannot run and is marked dead instead.
    """

    kind: str
    handler: JobHandler
    group: JobGroup = JobGroup.IO
    priority: int = 100
    max_attempts: int = 5
    timeout_seconds: float = 60.0
    needs_secret: bool = False

    def __post_init__(self) -> None:
        if not 0 < len(self.kind) <= JOB_KIND_MAX_LENGTH:
            raise ValueError(f"job kind must be 1-{JOB_KIND_MAX_LENGTH} characters")
        if self.priority < 0:
            raise ValueError("priority must not be negative")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class JobRegistry:
    """The job kinds one process can run."""

    def __init__(self, specs: list[JobSpec] | None = None) -> None:
        self._specs: dict[str, JobSpec] = {}
        for spec in specs or []:
            self.add(spec)

    def add(self, spec: JobSpec) -> JobSpec:
        if spec.kind in self._specs:
            raise ValueError(f"job kind {spec.kind!r} is already registered")
        self._specs[spec.kind] = spec
        return spec

    def subset(self, include: Callable[[JobSpec], bool]) -> JobRegistry:
        return JobRegistry([spec for spec in self._specs.values() if include(spec)])

    def get(self, kind: str) -> JobSpec | None:
        return self._specs.get(kind)

    def kinds(self, group: JobGroup | None = None) -> list[str]:
        return [s.kind for s in self._specs.values() if group is None or s.group is group]

    def __iter__(self) -> Iterator[JobSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)
