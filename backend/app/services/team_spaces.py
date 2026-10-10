"""Goals, skills to grow and progress notes inside a team (ADR 0016).

The same three tables and the same rules as pair spaces (``app.services.spaces``), with the
team in place of the connection:

- Only members of an open team can see or change anything; anyone else gets "team not
  found".
- Goals are shared (any member edits or deletes); skills and notes belong to their author
  (only they delete them; a note can only point at the author's own skill).
- Every write counts against SPACE_WRITES_PER_DAY; at most MAX_GOALS_PER_SPACE goals per
  team and MAX_SKILLS_PER_PERSON skills each.
- What a person wrote stays with the team after they leave. Notes are deleted
  SPACE_RETENTION_DAYS after writing (``purge_spaces``); the rest goes with the team.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    MAX_GOALS_PER_SPACE,
    MAX_SKILLS_PER_PERSON,
    GoalStatus,
    ProgressLog,
    SpaceGoal,
    SpaceSkill,
    Team,
    User,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode
from app.services.spaces import (
    RECENT_LOGS,
    GoalNotFoundError,
    LogNotFoundError,
    NotYoursError,
    SkillExistsError,
    SkillNotFoundError,
    TooManyGoalsError,
    TooManySkillsError,
)
from app.services.teams import open_team


@dataclass(frozen=True)
class TeamSpace:
    team: Team
    goals: list[SpaceGoal]
    skills: list[SpaceSkill]
    logs: list[ProgressLog]


class TeamSpaceService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # A day-long window (set by the caller): SPACE_WRITES_PER_DAY.
        self._limiter = limiter

    async def _write(self, user: User) -> None:
        await self._limiter.hit(f"space-write:{user.id}", limit=self._settings.space_writes_per_day)

    async def get(self, user: User, team_id: uuid.UUID) -> TeamSpace:
        team = await open_team(self._db, user, team_id)
        goals = list(
            await self._db.scalars(
                select(SpaceGoal)
                .where(SpaceGoal.team_id == team.id)
                .order_by(SpaceGoal.status, SpaceGoal.created_at)
            )
        )
        skills = list(
            await self._db.scalars(
                select(SpaceSkill)
                .where(SpaceSkill.team_id == team.id)
                .order_by(SpaceSkill.created_at)
            )
        )
        logs, _ = await self._logs(team, before=None, limit=RECENT_LOGS)
        return TeamSpace(team, goals, skills, logs)

    async def _logs(
        self, team: Team, *, before: str | None, limit: int
    ) -> tuple[list[ProgressLog], str | None]:
        query = select(ProgressLog).where(ProgressLog.team_id == team.id)
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
        self, user: User, team_id: uuid.UUID, *, before: str | None, limit: int
    ) -> tuple[list[ProgressLog], str | None]:
        team = await open_team(self._db, user, team_id)
        return await self._logs(team, before=before, limit=limit)

    # --- goals --------------------------------------------------------------------------

    async def add_goal(
        self, user: User, team_id: uuid.UUID, title: str, due_on: date | None
    ) -> SpaceGoal:
        team = await open_team(self._db, user, team_id)
        count = await self._db.scalar(
            select(func.count()).select_from(SpaceGoal).where(SpaceGoal.team_id == team.id)
        )
        if (count or 0) >= MAX_GOALS_PER_SPACE:
            raise TooManyGoalsError
        await self._write(user)
        goal = SpaceGoal(
            id=uuid.uuid4(), team_id=team.id, author_id=user.id, title=title, due_on=due_on
        )
        self._db.add(goal)
        await self._db.commit()
        await self._db.refresh(goal)
        return goal

    async def _goal(self, team: Team, goal_id: uuid.UUID) -> SpaceGoal:
        goal = await self._db.get(SpaceGoal, goal_id)
        if goal is None or goal.team_id != team.id:
            raise GoalNotFoundError
        return goal

    async def update_goal(
        self, user: User, team_id: uuid.UUID, goal_id: uuid.UUID, changes: dict[str, Any]
    ) -> SpaceGoal:
        """``changes`` holds only the fields the client sent: title, status, due_on."""
        team = await open_team(self._db, user, team_id)
        goal = await self._goal(team, goal_id)
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
        return goal

    async def delete_goal(self, user: User, team_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        team = await open_team(self._db, user, team_id)
        goal = await self._goal(team, goal_id)
        await self._write(user)
        await self._db.delete(goal)
        await self._db.commit()

    # --- skills -------------------------------------------------------------------------

    async def add_skill(self, user: User, team_id: uuid.UUID, name: str) -> SpaceSkill:
        team = await open_team(self._db, user, team_id)
        count = await self._db.scalar(
            select(func.count())
            .select_from(SpaceSkill)
            .where(SpaceSkill.team_id == team.id, SpaceSkill.author_id == user.id)
        )
        if (count or 0) >= MAX_SKILLS_PER_PERSON:
            raise TooManySkillsError
        await self._write(user)
        skill = SpaceSkill(id=uuid.uuid4(), team_id=team.id, author_id=user.id, name=name)
        self._db.add(skill)
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise SkillExistsError from None
        await self._db.refresh(skill)
        return skill

    async def delete_skill(self, user: User, team_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        team = await open_team(self._db, user, team_id)
        skill = await self._db.get(SpaceSkill, skill_id)
        if skill is None or skill.team_id != team.id:
            raise SkillNotFoundError
        if skill.author_id != user.id:
            raise NotYoursError
        await self._write(user)
        await self._db.delete(skill)
        await self._db.commit()

    # --- logs ---------------------------------------------------------------------------

    async def add_log(
        self,
        user: User,
        team_id: uuid.UUID,
        note: str,
        *,
        goal_id: uuid.UUID | None,
        skill_id: uuid.UUID | None,
    ) -> ProgressLog:
        team = await open_team(self._db, user, team_id)
        if goal_id is not None:
            await self._goal(team, goal_id)
        if skill_id is not None:
            skill = await self._db.get(SpaceSkill, skill_id)
            # A note can only be about the author's own skill.
            if skill is None or skill.team_id != team.id or skill.author_id != user.id:
                raise SkillNotFoundError
        await self._write(user)
        log = ProgressLog(
            id=uuid.uuid4(),
            team_id=team.id,
            author_id=user.id,
            note=note,
            goal_id=goal_id,
            skill_id=skill_id,
        )
        self._db.add(log)
        await self._db.commit()
        await self._db.refresh(log)
        return log

    async def delete_log(self, user: User, team_id: uuid.UUID, log_id: uuid.UUID) -> None:
        team = await open_team(self._db, user, team_id)
        log = await self._db.get(ProgressLog, log_id)
        if log is None or log.team_id != team.id:
            raise LogNotFoundError
        if log.author_id != user.id:
            raise NotYoursError
        await self._write(user)
        await self._db.delete(log)
        await self._db.commit()
