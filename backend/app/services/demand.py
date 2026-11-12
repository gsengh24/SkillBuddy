"""Aggregate social proof (ADR 0022, screen 8): how many people want a skill this week.

A count only: never names, avatars or anything that points at a person. Below a minimum the
count is withheld (``None``) so small numbers can't single anyone out; clients then hide the
line. The minimum comes from the onboarding P0 report.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import blocks

WINDOW_DAYS: Final = 7
MIN_COUNT: Final = 5

# People (other than the viewer, active only) who, in the window, picked the skill as a want
# on their profile or asked for it in a match request.
_DEMAND = text(
    """
    SELECT DISTINCT wanted.user_id FROM (
        SELECT p.user_id FROM profiles AS p
        WHERE p.updated_at >= :since
          AND EXISTS (SELECT 1 FROM unnest(p.want_skills) AS w(skill)
                      WHERE lower(w.skill) = lower(:skill))
        UNION
        SELECT r.user_id FROM match_requests AS r
        WHERE r.created_at >= :since
          AND jsonb_typeof(r.structured -> 'seeks') = 'array'
          AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(r.structured -> 'seeks') AS s(seek)
                      WHERE lower(s.seek) = lower(:skill))
    ) AS wanted
    JOIN users AS u ON u.id = wanted.user_id
    WHERE u.status = 'active' AND u.id <> :viewer
    """
)


async def demand_count(db: AsyncSession, viewer: uuid.UUID, skill: str) -> int | None:
    """How many people want ``skill`` this week, or None below the minimum."""
    since = datetime.now(UTC) - timedelta(days=WINDOW_DAYS)
    rows = await db.execute(_DEMAND, {"since": since, "skill": skill, "viewer": viewer})
    hidden = await blocks.blocked_with(db, viewer)
    count = sum(1 for (user_id,) in rows if user_id not in hidden)
    return count if count >= MIN_COUNT else None
