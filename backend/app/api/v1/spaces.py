"""Pair spaces v1 (ADR 0013): shared goals, skills to grow and progress logs.

The space is the connection, so it lives under /connections/{id}/space. Only the two
people in an open connection can use it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.models import (
    GOAL_TITLE_MAX_LENGTH,
    LOG_NOTE_MAX_LENGTH,
    MAX_GOALS_PER_SPACE,
    MAX_SKILLS_PER_PERSON,
    SKILL_NAME_MAX_LENGTH,
    Connection,
    ProgressLog,
    SpaceGoal,
    SpaceSkill,
)
from app.schemas.errors import ErrorResponse
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS
from app.services.spaces import SpaceService, author

router = APIRouter(prefix="/connections/{connection_id}/space", tags=["spaces"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_space_service(request: Request, db: DbDep, settings: SettingsDep) -> SpaceService:
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return SpaceService(db, settings, limiter)


ServiceDep = Annotated[SpaceService, Depends(get_space_service)]
WRITE = [Depends(require_json), Depends(require_storage_capacity)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`space_not_found` (no such open connection, or a block), or the item's "
    "own `*_not_found`.",
}
_429: dict[str, Any] = {"model": ErrorResponse, "description": "Daily space write limit."}

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

    @classmethod
    def build(cls, connection: Connection, goal: SpaceGoal) -> GoalOut:
        return cls(
            id=goal.id,
            title=goal.title,
            status=goal.status,  # type: ignore[arg-type]  # CHECK-constrained column
            due_on=goal.due_on,
            done_at=goal.done_at,
            created_by=author(connection, goal.from_a),
            created_at=goal.created_at,
        )


class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime

    @classmethod
    def build(cls, connection: Connection, skill: SpaceSkill) -> SkillOut:
        return cls(
            id=skill.id,
            name=skill.name,
            owner_id=author(connection, skill.from_a),
            created_at=skill.created_at,
        )


class LogOut(BaseModel):
    id: uuid.UUID
    note: str
    author_id: uuid.UUID
    goal_id: uuid.UUID | None
    skill_id: uuid.UUID | None
    created_at: datetime

    @classmethod
    def build(cls, connection: Connection, log: ProgressLog) -> LogOut:
        return cls(
            id=log.id,
            note=log.note,
            author_id=author(connection, log.from_a),
            goal_id=log.goal_id,
            skill_id=log.skill_id,
            created_at=log.created_at,
        )


class SpaceOut(BaseModel):
    connection_id: uuid.UUID
    goals: list[GoalOut] = Field(description="Open goals first, then done; oldest first.")
    skills: list[SkillOut] = Field(description="Both people's skills, oldest first.")
    logs: list[LogOut] = Field(description="The newest progress notes (more via /logs).")
    retention_days: int = Field(
        description="Progress notes are deleted this many days after they are written."
    )
    max_goals: int
    max_skills_per_person: int


class LogPage(BaseModel):
    items: list[LogOut] = Field(description="Newest first.")
    next_cursor: str | None = Field(description="Pass as `before` for older notes.")


# --- endpoints ----------------------------------------------------------------------------


@router.get("", summary="A pair space", responses={401: _401, 404: _404})
async def get_space(
    connection_id: uuid.UUID, auth: AuthDep, service: ServiceDep, settings: SettingsDep
) -> SpaceOut:
    space = await service.get(auth.user, connection_id)
    connection = space.connection
    return SpaceOut(
        connection_id=connection.id,
        goals=[GoalOut.build(connection, goal) for goal in space.goals],
        skills=[SkillOut.build(connection, skill) for skill in space.skills],
        logs=[LogOut.build(connection, log) for log in space.logs],
        retention_days=settings.space_retention_days,
        max_goals=MAX_GOALS_PER_SPACE,
        max_skills_per_person=MAX_SKILLS_PER_PERSON,
    )


@router.get(
    "/logs",
    summary="Progress notes, newest first",
    responses={
        400: {"model": ErrorResponse, "description": "`invalid_cursor`."},
        401: _401,
        404: _404,
    },
)
async def list_logs(
    connection_id: uuid.UUID,
    auth: AuthDep,
    service: ServiceDep,
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> LogPage:
    connection, items, next_cursor = await service.logs(
        auth.user, connection_id, before=before, limit=limit
    )
    return LogPage(items=[LogOut.build(connection, log) for log in items], next_cursor=next_cursor)


@router.post(
    "/goals",
    status_code=HTTPStatus.CREATED,
    summary="Add a shared goal",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404,
        409: {"model": ErrorResponse, "description": "`too_many_goals`."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: _429,
    },
)
async def add_goal(
    connection_id: uuid.UUID, body: GoalIn, auth: AuthDep, service: ServiceDep
) -> GoalOut:
    connection, goal = await service.add_goal(auth.user, connection_id, body.title, body.due_on)
    return GoalOut.build(connection, goal)


@router.patch(
    "/goals/{goal_id}",
    summary="Change a shared goal (either person)",
    dependencies=WRITE,
    responses={401: _401, 404: _404, 422: {"model": ErrorResponse}, 429: _429},
)
async def update_goal(
    connection_id: uuid.UUID,
    goal_id: uuid.UUID,
    body: GoalPatch,
    auth: AuthDep,
    service: ServiceDep,
) -> GoalOut:
    connection, goal = await service.update_goal(
        auth.user, connection_id, goal_id, body.model_dump(exclude_unset=True)
    )
    return GoalOut.build(connection, goal)


@router.delete(
    "/goals/{goal_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a shared goal (either person)",
    responses={401: _401, 404: _404, 429: _429},
)
async def delete_goal(
    connection_id: uuid.UUID, goal_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_goal(auth.user, connection_id, goal_id)


@router.post(
    "/skills",
    status_code=HTTPStatus.CREATED,
    summary="Add a skill you want to grow",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404,
        409: {"model": ErrorResponse, "description": "`too_many_skills` or `skill_exists`."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: _429,
    },
)
async def add_skill(
    connection_id: uuid.UUID, body: SkillIn, auth: AuthDep, service: ServiceDep
) -> SkillOut:
    connection, skill = await service.add_skill(auth.user, connection_id, body.name)
    return SkillOut.build(connection, skill)


@router.delete(
    "/skills/{skill_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Remove one of your skills",
    responses={
        401: _401,
        403: {"model": ErrorResponse, "description": "`not_yours`."},
        404: _404,
        429: _429,
    },
)
async def delete_skill(
    connection_id: uuid.UUID, skill_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_skill(auth.user, connection_id, skill_id)


@router.post(
    "/logs",
    status_code=HTTPStatus.CREATED,
    summary="Write a progress note",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404,
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: _429,
    },
)
async def add_log(
    connection_id: uuid.UUID, body: LogIn, auth: AuthDep, service: ServiceDep
) -> LogOut:
    """Deleted automatically `SPACE_RETENTION_DAYS` (90) after writing."""
    connection, log = await service.add_log(
        auth.user, connection_id, body.note, goal_id=body.goal_id, skill_id=body.skill_id
    )
    return LogOut.build(connection, log)


@router.delete(
    "/logs/{log_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete one of your progress notes",
    responses={
        401: _401,
        403: {"model": ErrorResponse, "description": "`not_yours`."},
        404: _404,
        429: _429,
    },
)
async def delete_log(
    connection_id: uuid.UUID, log_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.delete_log(auth.user, connection_id, log_id)
