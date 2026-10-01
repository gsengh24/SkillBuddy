"""Operator-only endpoints, protected by ADMIN_API_TOKEN (sent as X-Admin-Token).

Disabled (404) unless the token is configured. A proper admin role arrives with the
Admin/Trust module.
"""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter, Depends, Request

from app.api.deps import SettingsDep, StorageMonitorDep
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.security import constant_time_equals
from app.schemas.admin import StorageReport, TableSize
from app.services.storage import checked_at

ADMIN_TOKEN_HEADER: Final = "X-Admin-Token"  # noqa: S105  # a header name, not a secret


async def require_admin_token(request: Request, settings: SettingsDep) -> None:
    expected = settings.admin_api_token
    if expected is None:
        raise NotFoundError
    supplied = request.headers.get(ADMIN_TOKEN_HEADER, "")
    if not supplied or not constant_time_equals(supplied, expected.get_secret_value()):
        raise PermissionDeniedError


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


@router.get("/storage", summary="Database size against the free-tier limit")
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
