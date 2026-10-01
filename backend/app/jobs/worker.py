"""Stand-alone job runner process: ``python -m app.jobs.worker`` (ADR 0008).

On free hosting the runner runs inside the API process instead (``JOBS_RUN_IN_API``,
ADR 0008 step 3). This entry point is for the dev stack, CI, and a paid worker later.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.registry import JobRegistry
from app.jobs.runner import JobRunner

logger = logging.getLogger(__name__)


def build_registry() -> JobRegistry:
    """Every job kind this codebase runs. Arq's jobs move here in ADR 0008 step 3."""
    return JobRegistry()


async def run_worker(settings: Settings, registry: JobRegistry, stop: asyncio.Event) -> None:
    """Run jobs until ``stop`` is set, then shut down cleanly."""
    engine = create_engine(settings)
    try:
        runner = JobRunner(create_session_factory(engine), registry, settings)
        task = asyncio.create_task(runner.run_forever())
        await stop.wait()
        runner.stop()
        await task
    finally:
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
