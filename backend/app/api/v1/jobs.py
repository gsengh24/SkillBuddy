"""The scheduler's tick (ADR 0008): enqueue due scheduled jobs and wake the runner.

Called by a Cloudflare Worker cron with the shared secret ``JOBS_TICK_TOKEN`` in the
``X-Jobs-Tick-Token`` header. Disabled (404) unless the token is configured. Calling it
twice in the same period enqueues nothing the second time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.security import constant_time_equals
from app.db.session import get_db_session
from app.jobs.schedule import enqueue_due_jobs
from app.schemas.admin import TickOut
from app.schemas.errors import ErrorResponse

TICK_TOKEN_HEADER: Final = "X-Jobs-Tick-Token"  # noqa: S105  # a header name, not a secret


async def require_tick_token(request: Request, settings: SettingsDep) -> None:
    expected = settings.jobs_tick_token
    if expected is None:
        raise NotFoundError
    supplied = request.headers.get(TICK_TOKEN_HEADER, "")
    if not supplied or not constant_time_equals(supplied, expected.get_secret_value()):
        raise PermissionDeniedError


router = APIRouter(
    prefix="/admin/jobs",
    tags=["admin"],
    dependencies=[Depends(require_tick_token)],
    responses={
        HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse},
    },
)


@router.post(
    "/tick",
    status_code=HTTPStatus.ACCEPTED,
    summary="Enqueue scheduled jobs that are due (called by the scheduler)",
)
async def tick(request: Request, db: Annotated[AsyncSession, Depends(get_db_session)]) -> TickOut:
    """Daily jobs are enqueued once per UTC day and hourly jobs once per UTC hour; the job
    runner is woken to start on them. Returns at once; the jobs run in the background."""
    now = datetime.now(UTC)
    result = await enqueue_due_jobs(db, now)
    request.app.state.job_runner.wake()
    return TickOut(
        enqueued=result.enqueued, already_enqueued=result.already_enqueued, ticked_at=now
    )
