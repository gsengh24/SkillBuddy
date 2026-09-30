"""Background job functions executed by the Arq worker.

Every job takes Arq's ``ctx`` dict first. Jobs must be idempotent: Arq retries on
failure and may run a job more than once after a worker crash.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any]) -> str:
    """Round-trip check that the queue and worker are wired up."""
    logger.info("ping", extra={"job_id": ctx.get("job_id"), "job_try": ctx.get("job_try")})
    return "pong"
