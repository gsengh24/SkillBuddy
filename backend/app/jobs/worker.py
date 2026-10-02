"""Stand-alone job runner process: ``python -m app.jobs.worker`` (ADR 0008).

On free hosting every job runs inside the API process instead (``JOBS_RUN_IN_API=true``).
This entry point is for the dev stack, CI, and a paid worker later. It never runs jobs
with a secret (login codes): those run in the API process that enqueued them.

With ``JOBS_HEARTBEAT_FILE`` set, the process touches that file every few seconds while
its event loop is alive; the container healthcheck checks how recent it is.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from pathlib import Path
from typing import Final

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.registry import JobRegistry
from app.jobs.runner import JobRunner
from app.jobs.tasks import build_registry as build_full_registry

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS: Final = 10.0


def build_registry() -> JobRegistry:
    """The job kinds a separate worker process runs: all except those with a secret."""
    return build_full_registry().subset(lambda spec: not spec.needs_secret)


async def _heartbeat(path: Path, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.to_thread(path.touch)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), HEARTBEAT_INTERVAL_SECONDS)


async def run_worker(settings: Settings, registry: JobRegistry, stop: asyncio.Event) -> None:
    """Run jobs until ``stop`` is set, then shut down cleanly."""
    engine = create_engine(settings)
    heartbeat: asyncio.Task[None] | None = None
    try:
        runner = JobRunner(create_session_factory(engine), registry, settings)
        task = asyncio.create_task(runner.run_forever())
        if settings.jobs_heartbeat_file:
            heartbeat = asyncio.create_task(_heartbeat(Path(settings.jobs_heartbeat_file), stop))
        await stop.wait()
        runner.stop()
        await task
    finally:
        if heartbeat is not None:
            await heartbeat
        await engine.dispose()


async def _main(settings: Settings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # not available on Windows
            loop.add_signal_handler(sig, stop.set)
    await run_worker(settings, build_registry(), stop)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)
    asyncio.run(_main(settings))


if __name__ == "__main__":
    main()
