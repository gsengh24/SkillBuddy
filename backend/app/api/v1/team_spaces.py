"""A team's goals, skills to grow and progress notes (ADR 0016).

The same shapes as a pair space (``app.api.v1.spaces``), under /teams/{id}/space. Only
members of an open team can use it.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_feature, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.api.v1.spaces import GoalIn, GoalOut, GoalPatch, LogIn, LogOut, LogPage, SkillIn, SkillOut
from app.db.session import get_db_session
from app.models import (
    MAX_GOALS_PER_SPACE,
    MAX_SKILLS_PER_PERSON,
    ProgressLog,
    SpaceGoal,
    SpaceSkill,
)
from app.schemas.errors import ErrorResponse
from app.services import app_settings
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS
from app.services.team_spaces import TeamSpaceService

router = APIRouter(
    prefix="/teams/{team_id}/space",
    tags=["teams"],
    dependencies=[Depends(require_feature(app_settings.Feature.TEAMS))],
    responses={503: {"model": ErrorResponse, "description": "`feature_off`."}},
)

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_team_space_service(request: Request, db: DbDep, settings: SettingsDep) -> TeamSpaceService:
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return TeamSpaceService(db, settings, limiter)


ServiceDep = Annotated[TeamSpaceService, Depends(get_team_space_service)]
WRITE = [Depends(require_json), Depends(require_storage_capacity)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`team_not_found` (no such open team, or you are not in it), or the item's "
    "own `*_not_found`.",
}
_422: dict[str, Any] = {"model": ErrorResponse, "description": "Validation failed."}
_429: dict[str, Any] = {"model": ErrorResponse, "description": "Daily space write limit."}


def _author(row: SpaceGoal | SpaceSkill | ProgressLog) -> uuid.UUID:
    # A team's row always has its author (the one_parent CHECK).
    return cast(uuid.UUID, row.author_id)


def _goal(goal: SpaceGoal) -> GoalOut:
    return GoalOut(
        id=goal.id,
        title=goal.title,
        status=goal.status,  # type: ignore[arg-type]  # CHECK-constrained column
        due_on=goal.due_on,
        done_at=goal.done_at,
        created_by=_author(goal),
        created_at=goal.created_at,
    )


def _skill(skill: SpaceSkill) -> SkillOut:
    return SkillOut(
        id=skill.id, name=skill.name, owner_id=_author(skill), created_at=skill.created_at
    )


def _log(log: ProgressLog) -> LogOut:
    return LogOut(
        id=log.id,
        note=log.note,
        author_id=_author(log),
        goal_id=log.goal_id,
        skill_id=log.skill_id,
        created_at=log.created_at,
    )


class TeamSpaceOut(BaseModel):
    team_id: uuid.UUID
    goals: list[GoalOut] = Field(description="Open goals first, then done; oldest first.")
    skills: list[SkillOut] = Field(description="Every member's skills, oldest first.")
    logs: list[LogOut] = Field(description="The newest progress notes (more via /logs).")
    retention_days: int = Field(
        description="Progress notes are deleted this many days after they are written."
    )
    max_goals: int
    max_skills_per_person: int


@router.get("", summary="A team's goals, skills and notes", responses={401: _401, 404: _404})
async def get_team_space(
    team_id: uuid.UUID, auth: AuthDep, service: ServiceDep, settings: SettingsDep
) -> TeamSpaceOut:
    space = await service.get(auth.user, team_id)
    return TeamSpaceOut(
        team_id=space.team.id,
        goals=[_goal(goal) for goal in space.goals],
        skills=[_skill(skill) for skill in space.skills],
        logs=[_log(log) for log in space.logs],
        retention_days=settings.space_retention_days,
        max_goals=MAX_GOALS_PER_SPACE,
        max_skills_per_person=MAX_SKILLS_PER_PERSON,
    )


@router.get(
    "/logs",
    summary="A team's progress notes, newest first",
    responses={
        400: {"model": ErrorResponse, "description": "`invalid_cursor`."},
        401: _401,
        404: _404,
    },
)
async def list_team_logs(
    team_id: uuid.UUID,
    auth: AuthDep,
    service: ServiceDep,
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> LogPage:
    items, next_cursor = await service.logs(auth.user, team_id, before=before, limit=limit)
    return LogPage(items=[_log(log) for log in items], next_cursor=next_cursor)


@router.post(
    "/goals",
    status_code=HTTPStatus.CREATED,
    summary="Add a team goal",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404,
        409: {"model": ErrorResponse, "description": "`too_many_goals`."},
        422: _422,
        429: _429,
    },
)
async def add_team_goal(
    team_id: uuid.UUID, body: GoalIn, auth: AuthDep, service: ServiceDep
) -> GoalOut:
    return _goal(await service.add_goal(auth.user, team_id, body.title, body.due_on))


@router.patch(
    "/goals/{goal_id}",
    summary="Change a team goal (any member)",
    dependencies=WRITE,
    responses={401: _401, 404: _404, 422: _422, 429: _429},
)
async def update_team_goal(
    team_id: uuid.UUID, goal_id: uuid.UUID, body: GoalPatch, auth: AuthDep, service: ServiceDep
) -> GoalOut:
    return _goal(
        await service.update_goal(auth.user, team_id, goal_id, body.model_dump(exclude_unset=True))
    )


@router.delete(
    "/goals/{goal_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a team goal (any member)",
    responses={401: _401, 404: _404, 429: _429},
)
async def delete_team_goal(
    team_id: uuid.UUID, goal_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_goal(auth.user, team_id, goal_id)


@router.post(
    "/skills",
    status_code=HTTPStatus.CREATED,
    summary="Add a skill you want to grow in this team",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404,
        409: {"model": ErrorResponse, "description": "`too_many_skills` or `skill_exists`."},
        422: _422,
        429: _429,
    },
)
async def add_team_skill(
    team_id: uuid.UUID, body: SkillIn, auth: AuthDep, service: ServiceDep
) -> SkillOut:
    return _skill(await service.add_skill(auth.user, team_id, body.name))


@router.delete(
    "/skills/{skill_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Remove one of your skills from a team",
    responses={
        401: _401,
        403: {"model": ErrorResponse, "description": "`not_yours`."},
        404: _404,
        429: _429,
    },
)
async def delete_team_skill(
    team_id: uuid.UUID, skill_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_skill(auth.user, team_id, skill_id)


@router.post(
    "/logs",
    status_code=HTTPStatus.CREATED,
    summary="Write a progress note in a team",
    dependencies=WRITE,
    responses={401: _401, 404: _404, 422: _422, 429: _429},
)
async def add_team_log(
    team_id: uuid.UUID, body: LogIn, auth: AuthDep, service: ServiceDep
) -> LogOut:
    """Deleted automatically `SPACE_RETENTION_DAYS` (90) after writing."""
    return _log(
        await service.add_log(
            auth.user, team_id, body.note, goal_id=body.goal_id, skill_id=body.skill_id
        )
    )


@router.delete(
    "/logs/{log_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete one of your progress notes in a team",
    responses={
        401: _401,
        403: {"model": ErrorResponse, "description": "`not_yours`."},
        404: _404,
        429: _429,
    },
)
async def delete_team_log(
    team_id: uuid.UUID, log_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_log(auth.user, team_id, log_id)
