"""Today's AI status for the moderation page: which provider answered, and how often.

Read from the daily counters the gateway keeps in ``rate_limit_counters`` (provider name and
outcome only). Nothing here touches a key, an account id, a prompt or a user.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import GLOBAL_CALLS_KEY, OUTCOME_PREFIX, PROBE_PREFIX
from app.ai.providers import configured_providers
from app.core.config import Settings
from app.models import RateLimitCounter


@dataclass
class ProviderStatus:
    name: str
    unit: str
    daily_budget: int
    used_today: int = 0
    # outcome -> count today: "ok", "timeout", "rate_limited", "unavailable", "invalid", ...
    calls: dict[str, int] = field(default_factory=dict)
    probes: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AIStatus:
    enabled: bool
    providers: list[ProviderStatus]
    # reason -> count today ("no_provider", "disabled", "user_cap", "global_cap", "privacy")
    fallbacks: dict[str, int]
    global_calls_today: int
    global_cap: int


def _split(rest: str) -> tuple[str, str]:
    """``"<provider>:<model>:<outcome>"`` -> (``"<provider>:<model>"``, outcome)."""
    name, _, outcome = rest.rpartition(":")
    return name, outcome


async def ai_status(db: AsyncSession, settings: Settings, now: datetime | None = None) -> AIStatus:
    today = (
        (now or datetime.now(UTC))
        .astimezone(UTC)
        .replace(hour=0, minute=0, second=0, microsecond=0)
    )
    rows = (
        await db.execute(
            select(RateLimitCounter.key, RateLimitCounter.count).where(
                RateLimitCounter.window_start == today,
                or_(
                    RateLimitCounter.key.startswith(OUTCOME_PREFIX),
                    RateLimitCounter.key.startswith(PROBE_PREFIX),
                    RateLimitCounter.key.startswith("ai:provider:"),
                    RateLimitCounter.key == GLOBAL_CALLS_KEY,
                ),
            )
        )
    ).tuples()
    providers = {
        p.name: ProviderStatus(p.name, p.unit, p.daily_budget)
        for p in configured_providers(settings)
    }
    fallbacks: dict[str, int] = defaultdict(int)
    global_calls = 0

    def status_for(name: str) -> ProviderStatus:
        # A provider that answered earlier today but is no longer configured still shows.
        return providers.setdefault(name, ProviderStatus(name, "", 0))

    for key, count in rows:
        if key == GLOBAL_CALLS_KEY:
            global_calls = count
        elif key.startswith(f"{OUTCOME_PREFIX}template:"):
            fallbacks[key.removeprefix(f"{OUTCOME_PREFIX}template:")] += count
        elif key.startswith(OUTCOME_PREFIX):
            name, outcome = _split(key.removeprefix(OUTCOME_PREFIX))
            status_for(name).calls[outcome] = count
        elif key.startswith(PROBE_PREFIX):
            name, outcome = _split(key.removeprefix(PROBE_PREFIX))
            status_for(name).probes[outcome] = count
        else:  # "ai:provider:<provider>:<model>:<unit>"
            name, _unit = _split(key.removeprefix("ai:provider:"))
            status_for(name).used_today = count
    return AIStatus(
        enabled=settings.ai_llm_enabled,
        providers=list(providers.values()),
        fallbacks=dict(fallbacks),
        global_calls_today=global_calls,
        global_cap=settings.ai_llm_daily_call_cap,
    )
