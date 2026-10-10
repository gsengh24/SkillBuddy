"""Pair spaces v1 (ADR 0013): shared goals, skills to grow and progress logs.

- The space is the connection: only its two people can see or change it. Anyone else, an
  ended connection (a block), or a block in either direction gets "not found".
- Goals are shared (either person edits or deletes); skills and logs belong to their author
  (only they delete them; a log can only point at the author's own skill).
- Every write counts against SPACE_WRITES_PER_DAY; at most MAX_GOALS_PER_SPACE goals and
  MAX_SKILLS_PER_PERSON skills each.
- Daily purge: logs older than SPACE_RETENTION_DAYS, and everything in spaces whose
  connection ended more than SPACE_RETENTION_DAYS ago.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.models import (
    MAX_GOALS_PER_SPACE,
    MAX_SKILLS_PER_PERSON,
    Connection,
    GoalStatus,
    ProgressLog,
    SpaceGoal,
    SpaceSkill,
    User,
)
from app.services import blocks
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode

logger = logging.getLogger(__name__)

RECENT_LOGS = 20


class SpaceNotFoundError(NotFoundError):
    code = "space_not_found"
    default_message = "That pair space doesn't exist."


class GoalNotFoundError(NotFoundError):
    code = "goal_not_found"
    default_message = "That goal doesn't exist."


class SkillNotFoundError(NotFoundError):
    code = "skill_not_found"
    default_message = "That skill doesn't exist."


class LogNotFoundError(NotFoundError):
    code = "log_not_found"
    default_message = "That progress note doesn't exist."


class NotYoursError(PermissionDeniedError):
    code = "not_yours"
    default_message = "Only the person who added this can remove it."


class TooManyGoalsError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "too_many_goals"
    default_message = "This space has the most goals allowed. Delete or finish some first."


class TooManySkillsError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "too_many_skills"
    default_message = "You have the most skills allowed in this space."


class SkillExistsError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "skill_exists"
    default_message = "You've already added this skill."


@dataclass(frozen=True)
class Space:
    connection: Connection
    goals: list[SpaceGoal]
    skills: list[SpaceSkill]
    logs: list[ProgressLog]


def author(connection: Connection, from_a: bool | None) -> uuid.UUID:
    return connection.user_a if from_a else connection.user_b


class SpaceService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # A day-long window (set by the caller): SPACE_WRITES_PER_DAY.
        self._limiter = limiter

    async def _space(self, user: User, connection_id: uuid.UUID) -> Connection:
        connection = await self._db.get(Connection, connection_id)
        if (
            connection is None
            or user.id not in (connection.user_a, connection.user_b)
            or connection.ended_at is not None
        ):
            raise SpaceNotFoundError
        other = connection.user_b if connection.user_a == user.id else connection.user_a
        if other in await blocks.blocked_with(self._db, user.id):
            raise SpaceNotFoundError
        return connection

    async def _write(self, user: User) -> None:
        await self._limiter.hit(f"space-write:{user.id}", limit=self._settings.space_writes_per_day)

    async def get(self, user: User, connection_id: uuid.UUID) -> Space:
        connection = await self._space(user, connection_id)
        goals = list(
            await self._db.scalars(
                select(SpaceGoal)
                .where(SpaceGoal.connection_id == connection.id)
                .order_by(SpaceGoal.status, SpaceGoal.created_at)
            )
        )
        skills = list(
            await self._db.scalars(
                select(SpaceSkill)
                .where(SpaceSkill.connection_id == connection.id)
                .order_by(SpaceSkill.created_at)
            )
        )
        logs, _ = await self._logs(connection, before=None, limit=RECENT_LOGS)
        return Space(connection, goals, skills, logs)

    async def _logs(
        self, connection: Connection, *, before: str | None, limit: int
    ) -> tuple[list[ProgressLog], str | None]:
        query = select(ProgressLog).where(ProgressLog.connection_id == connection.id)
        if before:
            created_at, identifier = decode_cursor(before)
            query = query.where(
                tuple_(ProgressLog.created_at, ProgressLog.id) < (created_at, identifier)
            )
        rows = list(
            await self._db.scalars(
                query.order_by(ProgressLog.created_at.desc(), ProgressLog.id.desc()).limit(
                    limit + 1
                )
            )
        )
        items = rows[:limit]
        next_cursor = encode(items[-1].created_at, items[-1].id) if len(rows) > limit else None
        return items, next_cursor

    async def logs(
        self, user: User, connection_id: uuid.UUID, *, before: str | None, limit: int
    ) -> tuple[Connection, list[ProgressLog], str | None]:
        connection = await self._space(user, connection_id)
        items, next_cursor = await self._logs(connection, before=before, limit=limit)
        return connection, items, next_cursor

    # --- goals --------------------------------------------------------------------------

    async def add_goal(
        self, user: User, connection_id: uuid.UUID, title: str, due_on: date | None
    ) -> tuple[Connection, SpaceGoal]:
        connection = await self._space(user, connection_id)
        count = await self._db.scalar(
            select(func.count())
            .select_from(SpaceGoal)
            .where(SpaceGoal.connection_id == connection.id)
        )
        if (count or 0) >= MAX_GOALS_PER_SPACE:
            raise TooManyGoalsError
        await self._write(user)
        goal = SpaceGoal(
            id=uuid.uuid4(),
            connection_id=connection.id,
            from_a=connection.user_a == user.id,
            title=title,
            due_on=due_on,
        )
        self._db.add(goal)
        await self._db.commit()
        await self._db.refresh(goal)
        return connection, goal

    async def _goal(self, connection: Connection, goal_id: uuid.UUID) -> SpaceGoal:
        goal = await self._db.get(SpaceGoal, goal_id)
        if goal is None or goal.connection_id != connection.id:
            raise GoalNotFoundError
        return goal

    async def update_goal(
        self, user: User, connection_id: uuid.UUID, goal_id: uuid.UUID, changes: dict[str, Any]
    ) -> tuple[Connection, SpaceGoal]:
        """``changes`` holds only the fields the client sent: title, status, due_on."""
        connection = await self._space(user, connection_id)
        goal = await self._goal(connection, goal_id)
        await self._write(user)
        if changes.get("title") is not None:
            goal.title = changes["title"]
        if "due_on" in changes:
            goal.due_on = changes["due_on"]
        status = changes.get("status")
        if status is not None and status != goal.status:
            goal.status = status
            goal.done_at = datetime.now(UTC) if status == GoalStatus.DONE else None
        await self._db.commit()
        await self._db.refresh(goal)
        return connection, goal

    async def delete_goal(self, user: User, connection_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        connection = await self._space(user, connection_id)
        goal = await self._goal(connection, goal_id)
        await self._write(user)
        await self._db.delete(goal)
        await self._db.commit()

    # --- skills -------------------------------------------------------------------------

    async def add_skill(
        self, user: User, connection_id: uuid.UUID, name: str
    ) -> tuple[Connection, SpaceSkill]:
        connection = await self._space(user, connection_id)
        from_a = connection.user_a == user.id
        count = await self._db.scalar(
            select(func.count())
            .select_from(SpaceSkill)
            .where(SpaceSkill.connection_id == connection.id, SpaceSkill.from_a == from_a)
        )
        if (count or 0) >= MAX_SKILLS_PER_PERSON:
            raise TooManySkillsError
        await self._write(user)
        skill = SpaceSkill(id=uuid.uuid4(), connection_id=connection.id, from_a=from_a, name=name)
        self._db.add(skill)
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise SkillExistsError from None
        await self._db.refresh(skill)
        return connection, skill

    async def delete_skill(self, user: User, connection_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        connection = await self._space(user, connection_id)
        skill = await self._db.get(SpaceSkill, skill_id)
        if skill is None or skill.connection_id != connection.id:
            raise SkillNotFoundError
        if author(connection, skill.from_a) != user.id:
            raise NotYoursError
        await self._write(user)
        await self._db.delete(skill)
        await self._db.commit()

    # --- logs ---------------------------------------------------------------------------

    async def add_log(
        self,
        user: User,
        connection_id: uuid.UUID,
        note: str,
        *,
        goal_id: uuid.UUID | None,
        skill_id: uuid.UUID | None,
    ) -> tuple[Connection, ProgressLog]:
        connection = await self._space(user, connection_id)
        from_a = connection.user_a == user.id
        if goal_id is not None:
            await self._goal(connection, goal_id)
        if skill_id is not None:
            skill = await self._db.get(SpaceSkill, skill_id)
            # A note can only be about the author's own skill.
            if skill is None or skill.connection_id != connection.id or skill.from_a != from_a:
                raise SkillNotFoundError
        await self._write(user)
        log = ProgressLog(
            id=uuid.uuid4(),
            connection_id=connection.id,
            from_a=from_a,
            note=note,
            goal_id=goal_id,
            skill_id=skill_id,
        )
        self._db.add(log)
        await self._db.commit()
        await self._db.refresh(log)
        return connection, log

    async def delete_log(self, user: User, connection_id: uuid.UUID, log_id: uuid.UUID) -> None:
        connection = await self._space(user, connection_id)
        log = await self._db.get(ProgressLog, log_id)
        if log is None or log.connection_id != connection.id:
            raise LogNotFoundError
        if author(connection, log.from_a) != user.id:
            raise NotYoursError
        await self._write(user)
        await self._db.delete(log)
        await self._db.commit()


async def purge_spaces(db: AsyncSession, settings: Settings, now: datetime) -> dict[str, int]:
    """Daily: logs older than the retention period, and whole spaces whose connection ended
    longer ago than that. Returns how many rows went from each table."""
    cutoff = now - timedelta(days=settings.space_retention_days)
    ended = select(Connection.id).where(Connection.ended_at < cutoff)
    deleted: dict[str, int] = {}
    for name, statement in (
        (
            "progress_logs",
            delete(ProgressLog).where(
                (ProgressLog.created_at < cutoff) | ProgressLog.connection_id.in_(ended)
            ),
        ),
        ("space_skills", delete(SpaceSkill).where(SpaceSkill.connection_id.in_(ended))),
        ("space_goals", delete(SpaceGoal).where(SpaceGoal.connection_id.in_(ended))),
    ):
        result = await db.execute(statement)
        deleted[name] = int(getattr(result, "rowcount", 0) or 0)
    await db.commit()
    logger.info("spaces_purged", extra=deleted)
    return deleted
