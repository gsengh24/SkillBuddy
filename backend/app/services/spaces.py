"""Pair spaces: the errors and the daily purge shared by a team's goals, skills and notes.

A pair space is a team (ADR 0016, 0018); the work itself is in ``app.services.team_spaces``.

- Goals are shared (any member edits or deletes); skills and logs belong to their author.
- Every write counts against SPACE_WRITES_PER_DAY; at most MAX_GOALS_PER_SPACE goals and
  MAX_SKILLS_PER_PERSON skills each.
- Daily purge: logs older than SPACE_RETENTION_DAYS.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from http import HTTPStatus

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.models import ProgressLog

logger = logging.getLogger(__name__)

RECENT_LOGS = 20


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


async def purge_spaces(db: AsyncSession, settings: Settings, now: datetime) -> dict[str, int]:
    """Daily: progress notes older than the retention period. Returns how many rows went."""
    cutoff = now - timedelta(days=settings.space_retention_days)
    result = await db.execute(delete(ProgressLog).where(ProgressLog.created_at < cutoff))
    deleted = {"progress_logs": int(getattr(result, "rowcount", 0) or 0)}
    await db.commit()
    logger.info("spaces_purged", extra=deleted)
    return deleted
