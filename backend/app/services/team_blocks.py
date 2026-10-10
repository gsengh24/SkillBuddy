"""What a block does to teams (ADR 0016). Kept apart from ``app.services.teams`` so that
``app.services.blocks`` can use it without an import cycle.

A block takes the two people out of every team they share: where the blocker owns the team,
the blocked person is removed; otherwise the blocker leaves. Open invites that would put
them in the same team end. Nobody is told why.
"""

from __future__ import annotations

import uuid

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import Team, TeamInvite, TeamInviteStatus, TeamMember


async def separate(db: AsyncSession, *, blocker: uuid.UUID, blocked: uuid.UUID) -> None:
    """Runs in the caller's transaction (the caller commits). Safe to run twice."""
    shared = select(TeamMember.team_id).where(
        TeamMember.user_id == blocker,
        TeamMember.team_id.in_(select(TeamMember.team_id).where(TeamMember.user_id == blocked)),
    )
    teams = (await db.execute(select(Team.id, Team.owner_id).where(Team.id.in_(shared)))).tuples()
    for team_id, owner_id in teams.all():
        leaver = blocked if owner_id == blocker else blocker
        await db.execute(
            delete(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == leaver)
        )

    def invited_to_team_of(invitee: uuid.UUID, member: uuid.UUID) -> ColumnElement[bool]:
        return and_(
            TeamInvite.user_id == invitee,
            TeamInvite.team_id.in_(select(TeamMember.team_id).where(TeamMember.user_id == member)),
        )

    await db.execute(
        update(TeamInvite)
        .where(
            TeamInvite.status == TeamInviteStatus.PENDING,
            or_(invited_to_team_of(blocked, blocker), invited_to_team_of(blocker, blocked)),
        )
        .values(status=TeamInviteStatus.WITHDRAWN, responded_at=func.now())
        .execution_options(synchronize_session=False)
    )
