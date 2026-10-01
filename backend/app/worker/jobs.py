"""Background job functions executed by the Arq worker.

Every job takes Arq's ``ctx`` dict first. Jobs must be idempotent: Arq retries on
failure and may run a job more than once after a worker crash.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.security import mask_email

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any]) -> str:
    """Round-trip check that the queue and worker are wired up."""
    logger.info("ping", extra={"job_id": ctx.get("job_id"), "job_try": ctx.get("job_try")})
    return "pong"


async def send_login_code(ctx: dict[str, Any], email: str, code: str) -> None:
    """Deliver a sign-in code by email. Never logs the code or the full address.

    Email sending (EmailSender, templates) is added in a follow-up; until then the code is
    not delivered and this records that fact.
    """
    del code  # not delivered yet; deliberately never logged
    logger.warning(
        "login_code_not_delivered",
        extra={"email": mask_email(email), "reason": "email sending not configured yet"},
    )
