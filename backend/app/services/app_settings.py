"""Feature switches and limits set from the admin Settings page (A6).

Stored in ``app_settings`` (``feature:<name>`` and ``limit:<name>``). A missing row means
the default: every feature on (except ``OFF_BY_DEFAULT``), and each limit at today's value
from the server settings.
So with nothing stored, the app behaves exactly as before.

Read through a 60-second in-process cache: a change reaches every process within a minute,
and the process that made it at once (``invalidate``). One small query refreshes it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any, Final

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models import MESSAGE_MAX_LENGTH, AppSetting

CACHE_SECONDS: Final = 60.0
FEATURE_PREFIX: Final = "feature:"
LIMIT_PREFIX: Final = "limit:"
# On/off rows for other admin pages (A7): content rules and AI providers.
RULE_PREFIX: Final = "modrule:"
PROVIDER_PREFIX: Final = "provider:"
_PREFIXES: Final = (FEATURE_PREFIX, LIMIT_PREFIX, RULE_PREFIX, PROVIDER_PREFIX)


class Feature(StrEnum):
    INTRO_REQUESTS = "intro_requests"
    CHATS = "chats"
    AI_MATCHING = "ai_matching"
    PAIR_SPACES = "pair_spaces"
    EMAIL_NOTIFICATIONS = "email_notifications"
    TEAMS = "teams"


# Off until an admin turns them on. Teams stay off until reporting for teams has shipped
# (ADR 0016).
OFF_BY_DEFAULT: Final = frozenset({Feature.TEAMS})


def _default(feature: Feature) -> bool:
    return feature not in OFF_BY_DEFAULT


class Limit(StrEnum):
    MATCH_REQUESTS_PER_DAY = "match_requests_per_day"
    INTROS_PER_DAY = "intros_per_day"
    MAX_PENDING_INTROS = "max_pending_intros"
    MESSAGE_MAX_LENGTH = "message_max_length"


@dataclass(frozen=True)
class LimitSpec:
    minimum: int
    maximum: int
    default: Callable[[Settings], int]


# Bounds match the server settings' own; a message can't pass the column's cap.
LIMITS: Final[dict[Limit, LimitSpec]] = {
    Limit.MATCH_REQUESTS_PER_DAY: LimitSpec(1, 100, lambda s: s.match_requests_per_day),
    Limit.INTROS_PER_DAY: LimitSpec(1, 100, lambda s: s.intros_per_day),
    Limit.MAX_PENDING_INTROS: LimitSpec(1, 200, lambda s: s.max_pending_intros),
    Limit.MESSAGE_MAX_LENGTH: LimitSpec(50, MESSAGE_MAX_LENGTH, lambda s: MESSAGE_MAX_LENGTH),
}

# What a client is told when a switched-off feature is used.
_OFF_MESSAGES: Final[dict[Feature, str]] = {
    Feature.INTRO_REQUESTS: "Sending intros is paused right now. Please try again later.",
    Feature.CHATS: "Chats are paused right now. Please try again later.",
    Feature.AI_MATCHING: "AI matching is paused right now.",
    Feature.PAIR_SPACES: "Pair spaces are paused right now. Please try again later.",
    Feature.EMAIL_NOTIFICATIONS: "Email notifications are paused right now.",
    Feature.TEAMS: "Teams are paused right now. Please try again later.",
}


class FeatureOffError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "feature_off"
    default_message = "This feature is paused right now. Please try again later."

    def __init__(self, feature: Feature) -> None:
        super().__init__(_OFF_MESSAGES[feature], details=[{"feature": feature.value}])


@dataclass(frozen=True)
class Snapshot:
    features: dict[Feature, bool]
    limits: dict[Limit, int]  # only the stored ones
    # Other stored on/off rows by full key ("modrule:...", "provider:...").
    switches: dict[str, bool]


def _parse(rows: list[tuple[str, Any]]) -> Snapshot:
    features: dict[Feature, bool] = {}
    limits: dict[Limit, int] = {}
    switches: dict[str, bool] = {}
    for key, value in rows:
        if key.startswith((RULE_PREFIX, PROVIDER_PREFIX)) and isinstance(value, bool):
            switches[key] = value
            continue
        if key.startswith(FEATURE_PREFIX) and isinstance(value, bool):
            try:
                features[Feature(key.removeprefix(FEATURE_PREFIX))] = value
            except ValueError:
                continue
        elif (
            key.startswith(LIMIT_PREFIX) and isinstance(value, int) and not isinstance(value, bool)
        ):
            try:
                limit = Limit(key.removeprefix(LIMIT_PREFIX))
            except ValueError:
                continue
            spec = LIMITS[limit]
            if spec.minimum <= value <= spec.maximum:
                limits[limit] = value
    return Snapshot(features=features, limits=limits, switches=switches)


class _Cache:
    """One snapshot per process. ``clock`` is replaceable for tests."""

    def __init__(self) -> None:
        self.clock: Callable[[], float] = time.monotonic
        self._snapshot: Snapshot | None = None
        self._loaded_at = 0.0

    def invalidate(self) -> None:
        self._snapshot = None

    async def get(self, db: AsyncSession) -> Snapshot:
        now = self.clock()
        if self._snapshot is None or now - self._loaded_at >= CACHE_SECONDS:
            rows = (
                await db.execute(
                    select(AppSetting.key, AppSetting.value).where(
                        or_(*(AppSetting.key.startswith(prefix) for prefix in _PREFIXES))
                    )
                )
            ).all()
            self._snapshot = _parse([(key, value) for key, value in rows])
            self._loaded_at = now
        return self._snapshot


cache: Final = _Cache()


async def is_on(db: AsyncSession, feature: Feature) -> bool:
    return (await cache.get(db)).features.get(feature, _default(feature))


async def ensure_on(db: AsyncSession, feature: Feature) -> None:
    if not await is_on(db, feature):
        raise FeatureOffError(feature)


async def limit(db: AsyncSession, settings: Settings, which: Limit) -> int:
    stored = (await cache.get(db)).limits.get(which)
    return stored if stored is not None else LIMITS[which].default(settings)


async def all_features(db: AsyncSession) -> dict[Feature, bool]:
    snapshot = await cache.get(db)
    return {feature: snapshot.features.get(feature, _default(feature)) for feature in Feature}


async def all_limits(db: AsyncSession, settings: Settings) -> dict[Limit, int]:
    snapshot = await cache.get(db)
    return {which: snapshot.limits.get(which, LIMITS[which].default(settings)) for which in Limit}


async def switch(db: AsyncSession, key: str, default: bool) -> bool:
    """A stored on/off row by full key (``"modrule:profanity"``), or ``default``."""
    return (await cache.get(db)).switches.get(key, default)
