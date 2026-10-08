"""The AI call log (A7): one row per provider call, metadata only.

Never a prompt, a response, a user or a key: provider, kind, outcome, duration and cost.
Rows older than 30 days are removed lazily, at most once an hour per process, as new
calls are logged.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiCall

RETENTION_DAYS: Final = 30
CLEANUP_EVERY_SECONDS: Final = 3600.0

_last_cleanup = 0.0


async def record(
    db: AsyncSession,
    *,
    provider: str,
    kind: str,
    outcome: str,
    duration_ms: int,
    cost_units: int | None = None,
    cost_unit: str | None = None,
) -> None:
    """Log one call (commits)."""
    global _last_cleanup
    db.add(
        AiCall(
            provider=provider[:64],
            kind=kind[:32],
            outcome=outcome[:32],
            duration_ms=max(0, duration_ms),
            cost_units=cost_units,
            cost_unit=cost_unit,
        )
    )
    if time.monotonic() - _last_cleanup >= CLEANUP_EVERY_SECONDS:
        _last_cleanup = time.monotonic()
        cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        await db.execute(delete(AiCall).where(AiCall.created_at < cutoff))
    await db.commit()
