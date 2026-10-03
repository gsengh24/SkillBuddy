"""The moderation page's API (ARCHITECTURE.md §8): for accounts in MODERATOR_EMAILS only.

Signed in as usual (session cookie with CSRF, or a bearer token). Every request is limited
per moderator (MODERATION_REQUESTS_PER_MINUTE). Moderators see report copies only, never
whole conversations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json
from app.api.v1.auth import AuthDep
from app.core.errors import PermissionDeniedError
from app.db.session import get_db_session
from app.models import REPORT_NOTE_MAX_LENGTH, Profile, Report, ReportStatus, User
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportOut, ReportPage, ResolveIn
from app.schemas.social import PersonOut
from app.services import moderation, reports
from app.services.auth.rate_limit import RateLimiter


class ModeratorOnlyError(PermissionDeniedError):
    code = "moderator_only"
    default_message = "Only moderators can do this."


async def require_moderator(auth: AuthDep, request: Request, settings: SettingsDep) -> User:
    if not moderation.is_moderator(settings, auth.user):
        raise ModeratorOnlyError
    limiter = RateLimiter(request.app.state.session_factory, settings.secret_key, window_seconds=60)
    await limiter.hit(f"moderation:{auth.user.id}", limit=settings.moderation_requests_per_minute)
    return auth.user


ModeratorDep = Annotated[User, Depends(require_moderator)]
DbDep = Annotated[AsyncSession, Depends(get_db_session)]

_403: dict[str, Any] = {"model": ErrorResponse, "description": "`moderator_only`."}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    403: _403,
    429: {"model": ErrorResponse, "description": "Rate limited (see Retry-After)."},
}

router = APIRouter(prefix="/moderation", tags=["moderation"], responses=_ERRORS)

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=REPORT_NOTE_MAX_LENGTH)]


class SuspendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Note = Field(default="", description="Why, for your own records.")
    report_id: uuid.UUID | None = Field(default=None, description="The report that led to it.")


class UnsuspendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Note = ""


class AccountOut(BaseModel):
    """An account as the moderator sees it: no email, no messages."""

    user_id: uuid.UUID
    status: Literal["active", "suspended", "pending_deletion"]
    display_name: str | None
    person: PersonOut
    suspended_at: datetime | None = None
    note: str = ""


class AccountList(BaseModel):
    items: list[AccountOut]


def _account(
    user: User, profile: Profile | None, *, suspended_at: datetime | None = None, note: str = ""
) -> AccountOut:
    return AccountOut(
        user_id=user.id,
        status=user.status,  # type: ignore[arg-type]  # CHECK-constrained column
        display_name=(profile.display_name or None) if profile else None,
        person=PersonOut.build(user.id, profile, connected=False),
        suspended_at=suspended_at,
        note=note,
    )


async def _out(db: AsyncSession, report: Report) -> ReportOut:
    statuses = await reports.reported_statuses(db, [report])
    return ReportOut.build(report, reports.status_of(statuses, report))


@router.get("/reports", summary="Reports, oldest first")
async def list_reports(
    moderator: ModeratorDep,
    db: DbDep,
    status: Annotated[ReportStatus, Query()] = ReportStatus.OPEN,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ReportPage:
    items, next_cursor = await reports.reports_page(db, status, cursor=cursor, limit=limit)
    statuses = await reports.reported_statuses(db, items)
    return ReportPage(
        items=[ReportOut.build(item, reports.status_of(statuses, item)) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/reports/{report_id}",
    summary="One report",
    responses={404: {"model": ErrorResponse, "description": "`report_not_found`."}},
)
async def get_report(report_id: uuid.UUID, moderator: ModeratorDep, db: DbDep) -> ReportOut:
    return await _out(db, await reports.get_report(db, report_id))


@router.post(
    "/reports/{report_id}/resolve",
    summary="Mark a report resolved",
    dependencies=[Depends(require_json)],
    responses={
        404: {"model": ErrorResponse, "description": "`report_not_found`."},
        409: {"model": ErrorResponse, "description": "`report_already_resolved`."},
    },
)
async def resolve_report(
    report_id: uuid.UUID, body: ResolveIn, moderator: ModeratorDep, db: DbDep
) -> ReportOut:
    """Logged in the audit log. The report and its copy are deleted 180 days later."""
    report = await reports.resolve_report(db, report_id, body.note, moderator_id=moderator.id)
    return await _out(db, report)


@router.post(
    "/accounts/{user_id}/suspend",
    summary="Suspend an account",
    dependencies=[Depends(require_json)],
    responses={
        404: {"model": ErrorResponse, "description": "`account_not_found`."},
        409: {
            "model": ErrorResponse,
            "description": "`cannot_suspend`: your own, a moderator's, or not active.",
        },
    },
)
async def suspend_account(
    user_id: uuid.UUID,
    body: SuspendIn,
    moderator: ModeratorDep,
    db: DbDep,
    settings: SettingsDep,
) -> AccountOut:
    """Signs them out everywhere at once. They can't sign in, can't be messaged and aren't
    shown in matches until unsuspended. Logged in the audit log."""
    user = await moderation.suspend(
        db, settings, moderator, user_id, body.note, report_id=body.report_id
    )
    return _account(user, await db.get(Profile, user.id), note=body.note)


@router.post(
    "/accounts/{user_id}/unsuspend",
    summary="Unsuspend an account",
    dependencies=[Depends(require_json)],
    responses={
        404: {"model": ErrorResponse, "description": "`account_not_found`."},
        409: {"model": ErrorResponse, "description": "`not_suspended`."},
    },
)
async def unsuspend_account(
    user_id: uuid.UUID, body: UnsuspendIn, moderator: ModeratorDep, db: DbDep
) -> AccountOut:
    """They can sign in again. Logged in the audit log."""
    user = await moderation.unsuspend(db, moderator, user_id, body.note)
    return _account(user, await db.get(Profile, user.id))


@router.get("/accounts/suspended", summary="Suspended accounts, newest first")
async def suspended_accounts(moderator: ModeratorDep, db: DbDep) -> AccountList:
    return AccountList(
        items=[
            _account(item.user, item.profile, suspended_at=item.suspended_at, note=item.note)
            for item in await moderation.suspended_accounts(db)
        ]
    )
