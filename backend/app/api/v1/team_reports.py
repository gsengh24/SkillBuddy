"""Reporting a team or a team chat message (ADR 0016).

Outside the teams router on purpose: like other reports, these still work while the teams
feature is switched off. A team's goals and notes are reported through the pair-space
report endpoints (`/space-goals/{id}/report`, `/progress-logs/{id}/report`).
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportIn, ReportReceipt
from app.services import reports
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS

router = APIRouter(tags=["teams"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def _report_limiter(request: Request, settings: SettingsDep) -> RateLimiter:
    return RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )


LimiterDep = Annotated[RateLimiter, Depends(_report_limiter)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    422: {"model": ErrorResponse, "description": "Validation failed."},
    429: {"model": ErrorResponse, "description": "Daily report limit reached."},
}


@router.post(
    "/teams/{team_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report a team",
    dependencies=[Depends(require_json)],
    responses={
        **_ERRORS,
        404: {"model": ErrorResponse, "description": "`team_not_found` (or not yours to see)."},
        409: {
            "model": ErrorResponse,
            "description": "`cannot_report_own_entry` (your own team) or `already_reported`.",
        },
    },
)
async def report_team(
    team_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ReportReceipt:
    """A team you are in, were invited to, or can see listed. The moderator sees a copy of
    its name, description and "looking for" line, never who is in it. The report is about
    the team's owner, who is not told."""
    report = await reports.report_team(
        db, settings, limiter, auth.user, team_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)


@router.post(
    "/team-messages/{message_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report a team chat message",
    dependencies=[Depends(require_json)],
    responses={
        **_ERRORS,
        404: {"model": ErrorResponse, "description": "`message_not_found` (or not yours to see)."},
        409: {
            "model": ErrorResponse,
            "description": "`cannot_report_own_message` or `already_reported`.",
        },
    },
)
async def report_team_message(
    message_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ReportReceipt:
    """A message someone else sent in a team you are in. The moderator sees a copy of that
    one message, not the rest of the chat. The sender is not told."""
    report = await reports.report_team_message(
        db, settings, limiter, auth.user, message_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)
