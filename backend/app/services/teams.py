"""Teams (ADR 0016): groups of up to six, made for a hackathon, a project or anything else.

- A team has one owner and members. Only members can see it; anyone else gets "not found".
- The owner renames it, invites, withdraws invites, removes members and closes it. Members
  can leave. When the owner leaves, the longest-standing member becomes the owner; when the
  last person leaves, the team closes.
- Joining (this module's route): the owner invites someone they have an open connection
  with, and that person accepts. Nobody is added without their own yes. A decline is not
  shown to the owner: the invite looks pending until it expires.
- Nobody can be invited to, or join, a team with a member on either side of a block with
  them (``app.services.blocks``). They are told only that it can't be done, never who.
- Caps: MAX_TEAM_MEMBERS people, MAX_TEAMS_PER_PERSON teams each, MAX_TEAMS_OWNED owned,
  MAX_PENDING_PER_TEAM open invites, TEAMS_CREATED_PER_DAY and TEAM_INVITES_PER_DAY; other
  changes count against SPACE_WRITES_PER_DAY.
- Daily purge: invites past their expiry, old answered invites, and teams closed more than
  TEAM_RETENTION_DAYS ago. A team whose owner's account was deleted passes to its
  longest-standing member.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models import (
    MAX_PENDING_PER_TEAM,
    MAX_TEAM_MEMBERS,
    MAX_TEAMS_OWNED,
    MAX_TEAMS_PER_PERSON,
    SIGNED_IN_STATUSES,
    TEAM_INVITE_TTL_DAYS,
    Connection,
    NotificationKind,
    Profile,
    Team,
    TeamInvite,
    TeamInviteKind,
    TeamInviteStatus,
    TeamMember,
    User,
)
from app.services import blocks
from app.services.auth.rate_limit import RateLimiter
from app.services.notifications import add_notification

logger = logging.getLogger(__name__)

# A declined invite stays "pending" for the owner until it expires.
_OPEN = (TeamInviteStatus.PENDING, TeamInviteStatus.DECLINED)


class TeamNotFoundError(NotFoundError):
    code = "team_not_found"
    default_message = "That team doesn't exist."


class TeamInviteNotFoundError(NotFoundError):
    code = "team_invite_not_found"
    default_message = "That invite doesn't exist."


class TeamMemberNotFoundError(NotFoundError):
    code = "team_member_not_found"
    default_message = "That person isn't in this team."


class NotTeamOwnerError(PermissionDeniedError):
    code = "not_team_owner"
    default_message = "Only the team's owner can do this."


class TooManyTeamsError(ConflictError):
    code = "too_many_teams"
    default_message = "You're in the most teams allowed. Leave one first."


class TooManyTeamsOwnedError(ConflictError):
    code = "too_many_teams_owned"
    default_message = "You own the most teams allowed. Close one first."


class TeamFullError(ConflictError):
    code = "team_full"
    default_message = "This team is full."


class TooManyPendingInvitesError(ConflictError):
    code = "too_many_pending_invites"
    default_message = "This team has the most open invites allowed."


class AlreadyMemberError(ConflictError):
    code = "already_member"
    default_message = "This person is already in the team."


class TeamInviteExistsError(ConflictError):
    code = "team_invite_exists"
    default_message = "This person already has an invite to this team."


class CannotInviteError(ConflictError):
    """Not connected, not available, or a block somewhere: the owner isn't told which."""

    code = "cannot_invite"
    default_message = "This person can't be invited to this team."


class TeamNotAvailableError(ConflictError):
    code = "team_not_available"
    default_message = "This team isn't available."


class TeamInviteNotPendingError(ConflictError):
    code = "team_invite_not_pending"
    default_message = "This invite is no longer open."


@dataclass(frozen=True)
class TeamSummary:
    team: Team
    member_count: int


@dataclass(frozen=True)
class MemberView:
    user_id: uuid.UUID
    display_name: str
    joined_at: datetime


@dataclass(frozen=True)
class InviteView:
    invite: TeamInvite
    summary: TeamSummary
    # The invited person's name, for the owner's list; empty for the invited person.
    display_name: str
    status: TeamInviteStatus


@dataclass(frozen=True)
class TeamView:
    summary: TeamSummary
    members: list[MemberView]
    # Open invites, for the owner only.
    invites: list[InviteView]


def _rows(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


class TeamService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # A day-long window (set by the caller).
        self._limiter = limiter

    # --- lookups ------------------------------------------------------------------------

    async def _team(self, user: User, team_id: uuid.UUID, *, lock: bool = False) -> Team:
        """An open team ``user`` is in."""
        query = (
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(Team.id == team_id, Team.closed_at.is_(None), TeamMember.user_id == user.id)
        )
        if lock:
            query = query.with_for_update(of=Team)
        team = await self._db.scalar(query)
        if team is None:
            raise TeamNotFoundError
        return team

    async def _owned(self, user: User, team_id: uuid.UUID, *, lock: bool = False) -> Team:
        team = await self._team(user, team_id, lock=lock)
        if team.owner_id != user.id:
            raise NotTeamOwnerError
        return team

    async def _member_ids(self, team_id: uuid.UUID) -> list[uuid.UUID]:
        """Longest-standing first."""
        return list(
            await self._db.scalars(
                select(TeamMember.user_id)
                .where(TeamMember.team_id == team_id)
                .order_by(TeamMember.created_at, TeamMember.id)
            )
        )

    async def _teams_of(self, user_id: uuid.UUID) -> int:
        count = await self._db.scalar(
            select(func.count())
            .select_from(TeamMember)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.user_id == user_id, Team.closed_at.is_(None))
        )
        return count or 0

    async def _write(self, user: User) -> None:
        await self._limiter.hit(f"space-write:{user.id}", limit=self._settings.space_writes_per_day)

    async def _end_invites(self, team_id: uuid.UUID, now: datetime) -> None:
        await self._db.execute(
            update(TeamInvite)
            .where(TeamInvite.team_id == team_id, TeamInvite.status.in_(_OPEN))
            .values(status=TeamInviteStatus.WITHDRAWN, responded_at=now)
            .execution_options(synchronize_session=False)
        )

    # --- teams --------------------------------------------------------------------------

    async def mine(self, user: User) -> list[TeamSummary]:
        """Open teams ``user`` is in, most recently joined first."""
        other = aliased(TeamMember)
        count = (
            select(func.count())
            .select_from(other)
            .where(other.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        rows = await self._db.execute(
            select(Team, count)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user.id, Team.closed_at.is_(None))
            .order_by(TeamMember.created_at.desc(), Team.id)
        )
        return [TeamSummary(team, members) for team, members in rows.tuples()]

    async def create(self, user: User, name: str, purpose: str, description: str) -> TeamView:
        owned = await self._db.scalar(
            select(func.count())
            .select_from(Team)
            .where(Team.owner_id == user.id, Team.closed_at.is_(None))
        )
        if (owned or 0) >= MAX_TEAMS_OWNED:
            raise TooManyTeamsOwnedError
        if await self._teams_of(user.id) >= MAX_TEAMS_PER_PERSON:
            raise TooManyTeamsError
        await self._limiter.hit(
            f"team-create:{user.id}", limit=self._settings.teams_created_per_day
        )
        team = Team(
            id=uuid.uuid4(), name=name, purpose=purpose, description=description, owner_id=user.id
        )
        self._db.add(team)
        await self._db.flush()
        self._db.add(TeamMember(id=uuid.uuid4(), team_id=team.id, user_id=user.id))
        await self._db.commit()
        logger.info("team_created")
        return await self.get(user, team.id)

    async def get(self, user: User, team_id: uuid.UUID) -> TeamView:
        team = await self._team(user, team_id)
        rows = await self._db.execute(
            select(TeamMember, Profile.display_name)
            .outerjoin(Profile, Profile.user_id == TeamMember.user_id)
            .where(TeamMember.team_id == team.id)
            .order_by(TeamMember.created_at, TeamMember.id)
        )
        members = [
            MemberView(member.user_id, name or "", member.created_at)
            for member, name in rows.tuples()
        ]
        summary = TeamSummary(team, len(members))
        invites: list[InviteView] = []
        if team.owner_id == user.id:
            open_invites = await self._db.execute(
                select(TeamInvite, Profile.display_name)
                .outerjoin(Profile, Profile.user_id == TeamInvite.user_id)
                .where(
                    TeamInvite.team_id == team.id,
                    TeamInvite.status.in_(_OPEN),
                    TeamInvite.expires_at > datetime.now(UTC),
                )
                .order_by(TeamInvite.created_at, TeamInvite.id)
            )
            invites = [
                InviteView(invite, summary, name or "", TeamInviteStatus.PENDING)
                for invite, name in open_invites.tuples()
            ]
        return TeamView(summary, members, invites)

    async def update(self, user: User, team_id: uuid.UUID, changes: dict[str, Any]) -> TeamView:
        """``changes`` holds only the fields the client sent: name, purpose, description."""
        team = await self._owned(user, team_id)
        await self._write(user)
        for field in ("name", "purpose", "description"):
            if changes.get(field) is not None:
                setattr(team, field, changes[field])
        await self._db.commit()
        return await self.get(user, team_id)

    async def close(self, user: User, team_id: uuid.UUID) -> None:
        team = await self._owned(user, team_id, lock=True)
        now = datetime.now(UTC)
        team.closed_at = now
        await self._end_invites(team.id, now)
        await self._db.commit()
        logger.info("team_closed")

    # --- members ------------------------------------------------------------------------

    async def leave(self, user: User, team_id: uuid.UUID) -> None:
        team = await self._team(user, team_id, lock=True)
        await self._db.execute(
            delete(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        )
        if team.owner_id == user.id:
            remaining = await self._member_ids(team.id)
            if remaining:
                team.owner_id = remaining[0]
            else:
                now = datetime.now(UTC)
                team.closed_at = now
                await self._end_invites(team.id, now)
        await self._db.commit()
        logger.info("team_left")

    async def remove(self, user: User, team_id: uuid.UUID, member_id: uuid.UUID) -> None:
        """The owner takes someone else out of the team."""
        team = await self._owned(user, team_id, lock=True)
        await self._write(user)
        result = await self._db.execute(
            delete(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == member_id,
                TeamMember.user_id != user.id,
            )
        )
        if not _rows(result):
            await self._db.rollback()
            raise TeamMemberNotFoundError
        await self._db.commit()
        logger.info("team_member_removed")

    # --- invites ------------------------------------------------------------------------

    async def invite(self, user: User, team_id: uuid.UUID, invitee_id: uuid.UUID) -> InviteView:
        team = await self._owned(user, team_id, lock=True)
        now = datetime.now(UTC)
        members = await self._member_ids(team.id)
        if invitee_id in members:
            raise AlreadyMemberError
        # An invite that ran out but hasn't been swept yet must not block a new one.
        await self._db.execute(
            update(TeamInvite)
            .where(
                TeamInvite.team_id == team.id,
                TeamInvite.user_id == invitee_id,
                TeamInvite.status.in_(_OPEN),
                TeamInvite.expires_at <= now,
            )
            .values(status=TeamInviteStatus.EXPIRED)
            .execution_options(synchronize_session=False)
        )
        open_invites = list(
            await self._db.scalars(
                select(TeamInvite.user_id).where(
                    TeamInvite.team_id == team.id, TeamInvite.status.in_(_OPEN)
                )
            )
        )
        if invitee_id in open_invites:
            raise TeamInviteExistsError
        if not await self._can_invite(user, invitee_id, members):
            raise CannotInviteError
        if len(members) >= MAX_TEAM_MEMBERS:
            raise TeamFullError
        if len(open_invites) >= MAX_PENDING_PER_TEAM:
            raise TooManyPendingInvitesError
        await self._limiter.hit(f"team-invite:{user.id}", limit=self._settings.team_invites_per_day)
        invite = TeamInvite(
            id=uuid.uuid4(),
            team_id=team.id,
            user_id=invitee_id,
            kind=TeamInviteKind.INVITE,
            status=TeamInviteStatus.PENDING,
            expires_at=now + timedelta(days=TEAM_INVITE_TTL_DAYS),
        )
        self._db.add(invite)
        add_notification(self._db, invitee_id, NotificationKind.TEAM_INVITE, team_id=team.id)
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise TeamInviteExistsError from None
        await self._db.refresh(invite)
        await self._db.refresh(team)
        name = await self._db.scalar(
            select(Profile.display_name).where(Profile.user_id == invitee_id)
        )
        logger.info("team_invite_sent")
        return InviteView(
            invite, TeamSummary(team, len(members)), name or "", TeamInviteStatus.PENDING
        )

    async def _can_invite(
        self, user: User, invitee_id: uuid.UUID, members: list[uuid.UUID]
    ) -> bool:
        if invitee_id == user.id:
            return False
        connected = await self._db.scalar(
            select(Connection.id).where(
                Connection.user_a == min(user.id, invitee_id),
                Connection.user_b == max(user.id, invitee_id),
                Connection.ended_at.is_(None),
            )
        )
        invitee = await self._db.get(User, invitee_id)
        if connected is None or invitee is None or invitee.status not in SIGNED_IN_STATUSES:
            return False
        return not (await blocks.blocked_with(self._db, invitee_id)).intersection(members)

    async def my_invites(self, user: User) -> list[InviteView]:
        """Open invites to ``user``, newest first."""
        member = aliased(TeamMember)
        count = (
            select(func.count())
            .select_from(member)
            .where(member.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        rows = await self._db.execute(
            select(TeamInvite, Team, count)
            .join(Team, Team.id == TeamInvite.team_id)
            .where(
                TeamInvite.user_id == user.id,
                TeamInvite.kind == TeamInviteKind.INVITE,
                TeamInvite.status == TeamInviteStatus.PENDING,
                TeamInvite.expires_at > datetime.now(UTC),
                Team.closed_at.is_(None),
            )
            .order_by(TeamInvite.created_at.desc(), TeamInvite.id)
        )
        return [
            InviteView(invite, TeamSummary(team, members), "", TeamInviteStatus.PENDING)
            for invite, team, members in rows.tuples()
        ]

    async def respond(self, user: User, invite_id: uuid.UUID, *, accept: bool) -> InviteView:
        found = await self._db.get(TeamInvite, invite_id)
        if found is None or found.user_id != user.id or found.kind != TeamInviteKind.INVITE:
            raise TeamInviteNotFoundError
        # The team row is the lock for its member count.
        team = await self._db.scalar(select(Team).where(Team.id == found.team_id).with_for_update())
        await self._db.refresh(found)
        now = datetime.now(UTC)
        if (
            team is None
            or team.closed_at is not None
            or found.status != TeamInviteStatus.PENDING
            or found.expires_at <= now
        ):
            raise TeamInviteNotPendingError
        members = await self._member_ids(team.id)
        if accept and user.id not in members:
            if (await blocks.blocked_with(self._db, user.id)).intersection(members):
                raise TeamNotAvailableError
            if len(members) >= MAX_TEAM_MEMBERS:
                raise TeamFullError
            if await self._teams_of(user.id) >= MAX_TEAMS_PER_PERSON:
                raise TooManyTeamsError
            self._db.add(TeamMember(id=uuid.uuid4(), team_id=team.id, user_id=user.id))
            for member_id in members:
                add_notification(self._db, member_id, NotificationKind.TEAM_JOINED, team_id=team.id)
            members.append(user.id)
        status = TeamInviteStatus.ACCEPTED if accept else TeamInviteStatus.DECLINED
        found.status = status
        found.responded_at = now
        await self._db.commit()
        await self._db.refresh(found)
        await self._db.refresh(team)
        logger.info("team_invite_answered", extra={"accepted": accept})
        return InviteView(found, TeamSummary(team, len(members)), "", status)

    async def withdraw(self, user: User, invite_id: uuid.UUID) -> None:
        """The owner takes back an open invite."""
        invite = await self._db.get(TeamInvite, invite_id)
        team = await self._db.get(Team, invite.team_id) if invite is not None else None
        if invite is None or team is None or team.owner_id != user.id or team.closed_at:
            raise TeamInviteNotFoundError
        if invite.status not in _OPEN:
            raise TeamInviteNotPendingError
        await self._write(user)
        invite.status = TeamInviteStatus.WITHDRAWN
        invite.responded_at = datetime.now(UTC)
        await self._db.commit()


async def purge_teams(db: AsyncSession, settings: Settings, now: datetime) -> dict[str, int]:
    """Daily. Returns what it changed."""
    done: dict[str, int] = {"teams_adopted": 0, "teams_closed": 0}
    # Teams whose owner's account was deleted: the longest-standing member takes over.
    orphans = await db.scalars(
        select(Team).where(Team.owner_id.is_(None), Team.closed_at.is_(None)).with_for_update()
    )
    for team in orphans.all():
        heir = await db.scalar(
            select(TeamMember.user_id)
            .where(TeamMember.team_id == team.id)
            .order_by(TeamMember.created_at, TeamMember.id)
            .limit(1)
        )
        if heir is None:
            team.closed_at = now
            done["teams_closed"] += 1
        else:
            team.owner_id = heir
            done["teams_adopted"] += 1
    await db.flush()

    cutoff = now - timedelta(days=settings.team_retention_days)
    expired = await db.execute(
        update(TeamInvite)
        .where(TeamInvite.status.in_(_OPEN), TeamInvite.expires_at < now)
        .values(status=TeamInviteStatus.EXPIRED)
        .execution_options(synchronize_session=False)
    )
    done["invites_expired"] = _rows(expired)
    old_invites = await db.execute(
        delete(TeamInvite).where(
            TeamInvite.status != TeamInviteStatus.PENDING, TeamInvite.expires_at < cutoff
        )
    )
    done["invites_deleted"] = _rows(old_invites)
    # Members, invites and notifications go with the team (ON DELETE CASCADE).
    old_teams = await db.execute(delete(Team).where(Team.closed_at < cutoff))
    done["teams_deleted"] = _rows(old_teams)
    await db.commit()
    logger.info("teams_purged", extra=done)
    return done
