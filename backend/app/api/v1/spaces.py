"""Pair-space request and response shapes, and reporting a goal or a note (ADR 0018).

A pair space is a team: its endpoints are in ``team_spaces`` under /teams/{id}/space. The
report endpoints live here, outside the team's own path: like messages, entries are
reported by their id.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.models import GOAL_TITLE_MAX_LENGTH, LOG_NOTE_MAX_LENGTH, SKILL_NAME_MAX_LENGTH
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportIn, ReportReceipt
from app.services import reports
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS

DbDep = Annotated[AsyncSession, Depends(get_db_session)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=GOAL_TITLE_MAX_LENGTH)
]


# --- schemas ------------------------------------------------------------------------------


class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    due_on: date | None = None


class GoalPatch(BaseModel):
    """Send only what changes. `due_on: null` clears the due date."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    status: Literal["open", "done"] | None = None
    due_on: date | None = None


class SkillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=SKILL_NAME_MAX_LENGTH),
    ]


class LogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LOG_NOTE_MAX_LENGTH)
    ]
    goal_id: uuid.UUID | None = Field(default=None, description="About one of the space's goals.")
    skill_id: uuid.UUID | None = Field(default=None, description="About one of your skills.")

    @model_validator(mode="after")
    def _one_link(self) -> Self:
        if self.goal_id is not None and self.skill_id is not None:
            raise ValueError("a note can be about a goal or a skill, not both")
        return self


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    status: Literal["open", "done"]
    due_on: date | None
    done_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime


class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime


class LogOut(BaseModel):
    id: uuid.UUID
    note: str
    author_id: uuid.UUID
    goal_id: uuid.UUID | None
    skill_id: uuid.UUID | None
    created_at: datetime


class LogPage(BaseModel):
    items: list[LogOut] = Field(description="Newest first.")
    next_cursor: str | None = Field(description="Pass as `before` for older notes.")


# Reporting works while the teams feature is switched off, like other reports.
report_router = APIRouter(tags=["spaces"])

_REPORT_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _401,
    409: {
        "model": ErrorResponse,
        "description": "`cannot_report_own_entry` or `already_reported`.",
    },
    422: {"model": ErrorResponse, "description": "Validation failed."},
    429: {"model": ErrorResponse, "description": "Daily report limit reached."},
}


def _report_limiter(request: Request, settings: SettingsDep) -> RateLimiter:
    return RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )


@report_router.post(
    "/space-goals/{goal_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report a goal in a pair space",
    dependencies=[Depends(require_json)],
    responses={**_REPORT_ERRORS, 404: {"model": ErrorResponse, "description": "`goal_not_found`."}},
)
async def report_goal(
    goal_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    limiter: Annotated[RateLimiter, Depends(_report_limiter)],
) -> ReportReceipt:
    """A goal the other person added. The moderator sees a copy of its title; they are not
    told."""
    report = await reports.report_goal(
        db, settings, limiter, auth.user, goal_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)


@report_router.post(
    "/progress-logs/{log_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report a progress note in a pair space",
    dependencies=[Depends(require_json)],
    responses={**_REPORT_ERRORS, 404: {"model": ErrorResponse, "description": "`log_not_found`."}},
)
async def report_progress_log(
    log_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    limiter: Annotated[RateLimiter, Depends(_report_limiter)],
) -> ReportReceipt:
    """A note the other person wrote. The moderator sees a copy of it; they are not told."""
    report = await reports.report_progress_log(
        db, settings, limiter, auth.user, log_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)
