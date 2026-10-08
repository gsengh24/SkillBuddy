"""The admin Overview and health (A4). Every admin role may view them."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import AfterValidator

from app.api.admin_deps import AdminContext, DbDep, require_admin
from app.api.deps import SettingsDep
from app.schemas.admin_overview import (
    DayCount,
    FunnelStep,
    HealthCheck,
    HealthOut,
    KpiOut,
    OverviewOut,
)
from app.schemas.admin_portal import AuditEntryOut
from app.schemas.errors import ErrorResponse
from app.services.admin import overview
from app.services.admin.permissions import Permission

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
}

router = APIRouter(prefix="/admin", tags=["admin"], responses=_ERRORS)

Viewer = Annotated[AdminContext, Depends(require_admin(Permission.VIEW_DASHBOARDS))]

_RANGES = (7, 30, 90)


def _known_range(days: int) -> int:
    if days not in _RANGES:
        raise ValueError(f"days must be one of {_RANGES}")
    return days


# An int checked against _RANGES, not Literal[7, 30, 90]: the query string "30" is not
# coerced into an int literal, so a Literal turned away every value with 422.
Range = Annotated[
    int, AfterValidator(_known_range), Query(json_schema_extra={"enum": list(_RANGES)})
]


@router.get("/overview", summary="The admin Overview")
async def get_overview(
    _: Viewer,
    db: DbDep,
    settings: SettingsDep,
    days: Range = 7,
) -> OverviewOut:
    """KPIs against the previous period, sign-ups by day, the funnel, what needs attention
    and recent admin activity. Counts only; cached for 60 seconds per range."""
    found = await overview.cached(db, settings, days)
    return OverviewOut(
        days=found.days,
        generated_at=found.generated_at,
        kpis=[KpiOut(key=k.key, value=k.value, previous=k.previous) for k in found.kpis],
        signups_by_day=[DayCount(day=d, count=c) for d, c in found.signups_by_day],
        funnel=[FunnelStep(step=s, count=c) for s, c in found.funnel],
        attention=found.attention,
        activity=[AuditEntryOut.from_entry(entry) for entry in found.activity],
    )


@router.get("/health", summary="System health")
async def get_health(_: Viewer, db: DbDep, settings: SettingsDep) -> HealthOut:
    """API, database, AI providers (from today's recorded calls) and email. Cached for 60
    seconds; no AI provider is called."""
    checks = await overview.cached_health(db, settings)
    return HealthOut(
        checks=[HealthCheck(name=c.name, status=c.status, detail=c.detail) for c in checks],
        checked_at=datetime.now(UTC),
    )
