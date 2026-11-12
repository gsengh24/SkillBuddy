"""Home's in-context nudges (screen 11) and aggregate demand (screen 8), ADR 0022."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.models import NudgeKind
from app.schemas.errors import ErrorResponse
from app.schemas.nudges import CurrentNudgeOut, DemandOut, NudgeOut, SkillQuery
from app.services.auth.rate_limit import RateLimiter
from app.services.demand import WINDOW_DAYS, demand_count
from app.services.nudges import NudgeService

router = APIRouter(tags=["onboarding"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]
# Demand counts are cheap but not free: a person loads Home a few times a day at most.
DEMAND_LIMIT_PER_WINDOW = 120

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}


@router.get("/me/nudge", summary="Today's in-context nudge", responses={401: _401})
async def current_nudge(auth: AuthDep, db: DbDep) -> CurrentNudgeOut:
    """At most one nudge a day, each kind on one day at most, never one that was dismissed.
    `null` before onboarding is finished."""
    nudge = await NudgeService(db).current(auth.user)
    return CurrentNudgeOut(nudge=NudgeOut.of(nudge) if nudge else None)


@router.post(
    "/me/nudges/{kind}/dismiss",
    status_code=204,
    summary="Dismiss a nudge for good",
    responses={401: _401, 422: {"model": ErrorResponse, "description": "Unknown kind."}},
)
async def dismiss_nudge(kind: NudgeKind, auth: AuthDep, db: DbDep) -> Response:
    await NudgeService(db).dismiss(auth.user, kind)
    return Response(status_code=204)


@router.get(
    "/stats/demand",
    summary="How many people want a skill this week",
    responses={
        401: _401,
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Too many requests; retry later."},
    },
)
async def skill_demand(
    request: Request,
    auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    skill: Annotated[SkillQuery, Query(description="A skill name, any case.")],
) -> DemandOut:
    """An aggregate count only (no names or avatars), withheld below the minimum."""
    limiter = RateLimiter(
        request.app.state.session_factory,
        settings.secret_key,
        window_seconds=settings.rate_limit_window_seconds,
    )
    await limiter.hit(f"demand:{auth.user.id}", limit=DEMAND_LIMIT_PER_WINDOW)
    count = await demand_count(db, auth.user.id, skill)
    return DemandOut(skill=skill, count=count, window_days=WINDOW_DAYS)
