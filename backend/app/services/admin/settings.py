"""The admin Settings page (A6): feature switches and limits. Owners and admins only; each
change takes a reason and writes its audit entry in the same transaction."""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import AppSetting
from app.services import app_settings
from app.services.admin.core import AdminIdentity, record
from app.services.app_settings import FEATURE_PREFIX, LIMIT_PREFIX, LIMITS, Feature, Limit


class LimitOutOfRangeError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "limit_out_of_range"
    default_message = "That value is outside the allowed range for this limit."


async def _store(db: AsyncSession, actor: AdminIdentity, key: str, value: Any) -> None:
    await db.execute(
        insert(AppSetting)
        .values(key=key, value=value, updated_by=actor.user.id)
        .on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={"value": value, "updated_by": actor.user.id, "updated_at": datetime.now(UTC)},
        )
    )


async def set_feature(
    db: AsyncSession,
    actor: AdminIdentity,
    feature: Feature,
    on: bool,
    reason: str,
    ip: str | None,
) -> None:
    await _store(db, actor, f"{FEATURE_PREFIX}{feature.value}", on)
    record(
        db,
        actor,
        "settings.feature_on" if on else "settings.feature_off",
        target_type="feature",
        target_id=feature.value,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    # This process sees it at once; others within the cache's 60 seconds.
    app_settings.cache.invalidate()


async def set_limit(
    db: AsyncSession,
    actor: AdminIdentity,
    which: Limit,
    value: int,
    reason: str,
    ip: str | None,
) -> None:
    spec = LIMITS[which]
    if not spec.minimum <= value <= spec.maximum:
        raise LimitOutOfRangeError(
            f"Choose a value from {spec.minimum} to {spec.maximum}.",
            details=[{"minimum": spec.minimum, "maximum": spec.maximum}],
        )
    await _store(db, actor, f"{LIMIT_PREFIX}{which.value}", value)
    record(
        db,
        actor,
        "settings.limit_changed",
        target_type="limit",
        target_id=f"{which.value}={value}"[:64],
        reason=reason,
        ip=ip,
    )
    await db.commit()
    app_settings.cache.invalidate()
