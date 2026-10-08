"""Operator endpoints: ADMIN_API_TOKEN (sent as X-Admin-Token), or an admin (ADR 0015).

With the header, the token is checked: 404 when none is configured, 403 when wrong. Every
request is rate-limited per IP (ADMIN_REQUESTS_PER_MINUTE) first, the token is compared in
constant time, and the header is never logged. Without it, the caller must be an admin
past the two-step code with the route's permission, like every other /admin route.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import operator_or_admin
from app.api.deps import SettingsDep, StorageMonitorDep, require_json
from app.core.config import Settings
from app.db.session import get_db_session
from app.models import ReportStatus
from app.schemas.admin import StorageReport, TableSize
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportOut, ReportPage, ResolveIn
from app.services import reports
from app.services.admin.permissions import Permission
from app.services.auth.rate_limit import RateLimiter
from app.services.storage import checked_at

ADMIN_TOKEN_HEADER: Final = "X-Admin-Token"  # noqa: S105  # a header name, not a secret


async def limit_admin_requests(request: Request, settings: SettingsDep) -> None:
    """Counted before the token check, so guessing the token is slow too."""
    if settings.admin_api_token is None:
        return  # Disabled: require_admin_token answers 404.
    limiter = RateLimiter(request.app.state.session_factory, settings.secret_key, window_seconds=60)
    ip = request.client.host if request.client else "unknown"
    await limiter.hit(f"admin:ip:{ip}", limit=settings.admin_requests_per_minute)


def _admin_token(settings: Settings) -> str | None:
    return settings.admin_api_token.get_secret_value() if settings.admin_api_token else None


def _operator(permission: Permission) -> Any:
    return Depends(operator_or_admin(permission, ADMIN_TOKEN_HEADER, _admin_token))


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(limit_admin_requests)],
)

DbDep = Annotated[AsyncSession, Depends(get_db_session)]
_404: dict[str, Any] = {"model": ErrorResponse, "description": "`report_not_found`."}


@router.get(
    "/storage",
    summary="Database size against the free-tier limit",
    dependencies=[_operator(Permission.VIEW_DASHBOARDS)],
)
async def storage_report(monitor: StorageMonitorDep, settings: SettingsDep) -> StorageReport:
    """Warns at 70% of the limit; at 90% sign-ups and non-essential writes are paused."""
    status = await monitor.status()
    return StorageReport(
        status=status.level,
        database_bytes=status.database_bytes,
        limit_bytes=status.limit_bytes,
        used_percent=status.used_percent,
        warn_at_percent=settings.storage_warn_percent,
        pause_at_percent=settings.storage_pause_percent,
        largest_tables=[
            TableSize(name=name, bytes=size) for name, size in await monitor.largest_tables()
        ],
        checked_at=checked_at(),
    )


@router.get(
    "/reports",
    summary="Reports of chat messages, oldest first",
    dependencies=[_operator(Permission.READ_REPORTED_MESSAGES)],
)
async def list_reports(
    db: DbDep,
    status: Annotated[ReportStatus, Query()] = ReportStatus.OPEN,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ReportPage:
    """Each report carries a copy of the reported message and the 10 before it."""
    items, next_cursor = await reports.reports_page(db, status, cursor=cursor, limit=limit)
    statuses = await reports.reported_statuses(db, items)
    return ReportPage(
        items=[ReportOut.build(item, reports.status_of(statuses, item)) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/reports/{report_id}",
    summary="One report",
    responses={404: _404},
    dependencies=[_operator(Permission.READ_REPORTED_MESSAGES)],
)
async def get_report(report_id: uuid.UUID, db: DbDep) -> ReportOut:
    report = await reports.get_report(db, report_id)
    statuses = await reports.reported_statuses(db, [report])
    return ReportOut.build(report, reports.status_of(statuses, report))


@router.post(
    "/reports/{report_id}/resolve",
    summary="Mark a report resolved",
    dependencies=[Depends(require_json), _operator(Permission.HANDLE_REPORTS)],
    responses={
        404: _404,
        409: {"model": ErrorResponse, "description": "`report_already_resolved`."},
    },
)
async def resolve_report(report_id: uuid.UUID, body: ResolveIn, db: DbDep) -> ReportOut:
    """It and its copy of the messages are deleted REPORT_RETENTION_DAYS (180) later."""
    report = await reports.resolve_report(db, report_id, body.note, moderator_id=None)
    statuses = await reports.reported_statuses(db, [report])
    return ReportOut.build(report, reports.status_of(statuses, report))
