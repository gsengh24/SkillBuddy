"""Teams (ADR 0016): groups of up to six, made for a hackathon, a project or anything else.

- A team has one owner and members. Only members can see it; anyone else gets "not found".
- The owner renames it, invites, withdraws invites, removes members and closes it. Members
  can leave. When the owner leaves, the longest-standing member becomes the owner; when the
  last person leaves, the team closes.
- Joining (this module's route): the owner invites someone they have an open connection
  with, and that person accepts. Nobody is added without their own yes. A decline is not
  shown to the owner: the invite looks pending until it expires.
- Joining by link: the owner makes an invite link (a random code, kept only as a keyed
  hash, good for TEAM_LINK_TTL_DAYS; a new link replaces the old). Anyone signed in who
  has it can see the team's name and size and join at once, while there is room.
- Listed teams: the owner can list a team with a "looking for" line. Any signed-in person
  can browse listed teams and ask to join with a short note; the owner accepts or
  declines. A decline is not shown to the asker: it looks pending until it expires.
- The matcher finds teammates: the owner's match request carries the team, and the owner
  can invite a match to the team (kind ``suggested``). The person sees why they were
  suggested and the team's name, purpose and size, and accepts or declines.
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

from sqlalchemy import delete, func, or_, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import generate_token, keyed_hash
from app.models import (
    MAX_PENDING_PER_TEAM,
    MAX_TEAM_MEMBERS,
    MAX_TEAMS_OWNED,
    MAX_TEAMS_PER_PERSON,
    SIGNED_IN_STATUSES,
    TEAM_INVITE_TTL_DAYS,
    TEAM_LINK_TTL_DAYS,
    Block,
    Connection,
    FlaggedItem,
    Match,
    MatchRequest,
    NotificationKind,
    Profile,
    Team,
    TeamInvite,
    TeamInviteKind,
    TeamInviteStatus,
    TeamMember,
    User,
)
from app.services import blocks, content_rules
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode
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


class TeamLinkInvalidError(NotFoundError):
    """Unknown, expired or turned off, a closed team, or a block: the person isn't told which."""

    code = "team_link_invalid"
    default_message = "This invite link doesn't work any more."


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
    # When the invite link stops working, for the owner only; None without a live link.
    link_expires_at: datetime | None = None


def _rows(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def open_team(
    db: AsyncSession, user: User, team_id: uuid.UUID, *, lock: bool = False
) -> Team:
    """An open team ``user`` is in; anything else is "not found"."""
    query = (
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(Team.id == team_id, Team.closed_at.is_(None), TeamMember.user_id == user.id)
    )
    if lock:
        query = query.with_for_update(of=Team)
    team = await db.scalar(query)
    if team is None:
        raise TeamNotFoundError
    return team


class TeamService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # A day-long window (set by the caller).
        self._limiter = limiter

    # --- lookups ------------------------------------------------------------------------

    async def _team(self, user: User, team_id: uuid.UUID, *, lock: bool = False) -> Team:
        return await open_team(self._db, user, team_id, lock=lock)

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
                    # A request the owner declined is done; a declined invite still shows.
                    or_(
                        TeamInvite.status == TeamInviteStatus.PENDING,
                        (TeamInvite.status == TeamInviteStatus.DECLINED)
                        & (TeamInvite.kind != TeamInviteKind.REQUEST),
                    ),
                    TeamInvite.expires_at > datetime.now(UTC),
                )
                .order_by(TeamInvite.created_at, TeamInvite.id)
            )
            invites = [
                InviteView(invite, summary, name or "", TeamInviteStatus.PENDING)
                for invite, name in open_invites.tuples()
            ]
        link = team.invite_expires_at if team.owner_id == user.id else None
        if team.invite_code_hash is None or (link is not None and link <= datetime.now(UTC)):
            link = None
        return TeamView(summary, members, invites, link)

    async def update(self, user: User, team_id: uuid.UUID, changes: dict[str, Any]) -> TeamView:
        """``changes`` holds only the fields the client sent: name, purpose, description,
        listed, looking_for."""
        team = await self._owned(user, team_id)
        await self._write(user)
        for field in ("name", "purpose", "description", "listed", "looking_for"):
            if changes.get(field) is not None:
                setattr(team, field, changes[field])
        if team.listed:
            # Strangers can read a listed team: the content rules (A7) flag it for a
            # moderator; they never block the save.
            await content_rules.flag(
                self._db,
                user_id=user.id,
                item=FlaggedItem.TEAM,
                item_id=team.id,
                text="\n".join((team.name, team.description, team.looking_for)),
            )
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

    async def _open_invitees(
        self, team_id: uuid.UUID, person_id: uuid.UUID, now: datetime
    ) -> list[uuid.UUID]:
        """Everyone with an open invite or request for the team."""
        # One of ``person_id``'s that ran out but hasn't been swept yet must not block a new one.
        await self._db.execute(
            update(TeamInvite)
            .where(
                TeamInvite.team_id == team_id,
                TeamInvite.user_id == person_id,
                TeamInvite.status.in_(_OPEN),
                TeamInvite.expires_at <= now,
            )
            .values(status=TeamInviteStatus.EXPIRED)
            .execution_options(synchronize_session=False)
        )
        return list(
            await self._db.scalars(
                select(TeamInvite.user_id).where(
                    TeamInvite.team_id == team_id, TeamInvite.status.in_(_OPEN)
                )
            )
        )

    async def invite(
        self,
        user: User,
        team_id: uuid.UUID,
        invitee_id: uuid.UUID | None = None,
        *,
        match_id: uuid.UUID | None = None,
    ) -> InviteView:
        """Invite a connection, or (``match_id``) someone the matcher suggested for this team."""
        team = await self._owned(user, team_id, lock=True)
        kind, note = TeamInviteKind.INVITE, ""
        if match_id is not None:
            # Only a match from the owner's own request for this team counts.
            match = await self._db.scalar(
                select(Match)
                .join(MatchRequest, MatchRequest.id == Match.request_id)
                .where(
                    Match.id == match_id,
                    MatchRequest.user_id == user.id,
                    MatchRequest.team_id == team.id,
                )
            )
            if match is None:
                raise CannotInviteError
            invitee_id, kind, note = match.candidate_id, TeamInviteKind.SUGGESTED, match.reason
        if invitee_id is None:
            raise CannotInviteError
        now = datetime.now(UTC)
        members = await self._member_ids(team.id)
        if invitee_id in members:
            raise AlreadyMemberError
        open_invites = await self._open_invitees(team.id, invitee_id, now)
        if invitee_id in open_invites:
            raise TeamInviteExistsError
        if not await self._can_invite(user, invitee_id, members, need_connection=match_id is None):
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
            kind=kind,
            status=TeamInviteStatus.PENDING,
            note=note,
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
        self,
        user: User,
        invitee_id: uuid.UUID,
        members: list[uuid.UUID],
        *,
        need_connection: bool,
    ) -> bool:
        if invitee_id == user.id:
            return False
        if need_connection:
            connected = await self._db.scalar(
                select(Connection.id).where(
                    Connection.user_a == min(user.id, invitee_id),
                    Connection.user_b == max(user.id, invitee_id),
                    Connection.ended_at.is_(None),
                )
            )
            if connected is None:
                return False
        invitee = await self._db.get(User, invitee_id)
        if invitee is None or invitee.status not in SIGNED_IN_STATUSES:
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
                TeamInvite.kind.in_((TeamInviteKind.INVITE, TeamInviteKind.SUGGESTED)),
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
        if found is None:
            raise TeamInviteNotFoundError
        # The team row is the lock for its member count.
        team = await self._db.scalar(select(Team).where(Team.id == found.team_id).with_for_update())
        await self._db.refresh(found)
        # An invite is answered by the invited person; a request to join by the team's owner.
        is_request = found.kind == TeamInviteKind.REQUEST
        answerer = team.owner_id if is_request and team is not None else found.user_id
        if answerer != user.id:
            raise TeamInviteNotFoundError
        joiner = found.user_id
        now = datetime.now(UTC)
        if (
            team is None
            or team.closed_at is not None
            or found.status != TeamInviteStatus.PENDING
            or found.expires_at <= now
        ):
            raise TeamInviteNotPendingError
        members = await self._member_ids(team.id)
        if accept and joiner not in members:
            if (await blocks.blocked_with(self._db, joiner)).intersection(members):
                raise TeamNotAvailableError
            if len(members) >= MAX_TEAM_MEMBERS:
                raise TeamFullError
            if await self._teams_of(joiner) >= MAX_TEAMS_PER_PERSON:
                raise TooManyTeamsError
            self._db.add(TeamMember(id=uuid.uuid4(), team_id=team.id, user_id=joiner))
            for member_id in members:
                if member_id != user.id:  # the owner who said yes doesn't need telling
                    add_notification(
                        self._db, member_id, NotificationKind.TEAM_JOINED, team_id=team.id
                    )
            if is_request:
                add_notification(
                    self._db, joiner, NotificationKind.TEAM_REQUEST_ACCEPTED, team_id=team.id
                )
            members.append(joiner)
        status = TeamInviteStatus.ACCEPTED if accept else TeamInviteStatus.DECLINED
        found.status = status
        found.responded_at = now
        await self._db.commit()
        await self._db.refresh(found)
        await self._db.refresh(team)
        logger.info("team_invite_answered", extra={"accepted": accept})
        return InviteView(found, TeamSummary(team, len(members)), "", status)

    # --- listed teams and asking to join ------------------------------------------------

    async def listed(
        self, user: User, *, purpose: str | None, cursor: str | None, limit: int
    ) -> tuple[list[TeamSummary], str | None]:
        """Listed open teams ``user`` could ask to join, newest first: not their own, and none
        with a member on either side of a block with them."""
        member = aliased(TeamMember)
        count = (
            select(func.count())
            .select_from(member)
            .where(member.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        hidden = {user.id, *await blocks.blocked_with(self._db, user.id)}
        query = select(Team, count).where(
            Team.listed.is_(True),
            Team.closed_at.is_(None),
            Team.id.not_in(select(TeamMember.team_id).where(TeamMember.user_id.in_(hidden))),
        )
        if purpose is not None:
            query = query.where(Team.purpose == purpose)
        if cursor:
            created_at, identifier = decode_cursor(cursor)
            query = query.where(tuple_(Team.created_at, Team.id) < (created_at, identifier))
        rows = (
            await self._db.execute(
                query.order_by(Team.created_at.desc(), Team.id.desc()).limit(limit + 1)
            )
        ).all()
        items = [TeamSummary(team, members) for team, members in rows[:limit]]
        last = items[-1].team if items else None
        next_cursor = encode(last.created_at, last.id) if last and len(rows) > limit else None
        return items, next_cursor

    async def request_to_join(self, user: User, team_id: uuid.UUID, note: str) -> InviteView:
        team = await self._db.scalar(
            select(Team)
            .where(Team.id == team_id, Team.closed_at.is_(None), Team.listed.is_(True))
            .with_for_update()
        )
        if team is None:
            raise TeamNotFoundError
        now = datetime.now(UTC)
        members = await self._member_ids(team.id)
        if user.id in members:
            raise AlreadyMemberError
        if (await blocks.blocked_with(self._db, user.id)).intersection(members):
            raise TeamNotFoundError
        open_invites = await self._open_invitees(team.id, user.id, now)
        if user.id in open_invites:
            raise TeamInviteExistsError
        if len(members) >= MAX_TEAM_MEMBERS:
            raise TeamFullError
        if len(open_invites) >= MAX_PENDING_PER_TEAM:
            raise TooManyPendingInvitesError
        if await self._teams_of(user.id) >= MAX_TEAMS_PER_PERSON:
            raise TooManyTeamsError
        await self._limiter.hit(
            f"team-request:{user.id}", limit=self._settings.team_requests_per_day
        )
        request = TeamInvite(
            id=uuid.uuid4(),
            team_id=team.id,
            user_id=user.id,
            kind=TeamInviteKind.REQUEST,
            status=TeamInviteStatus.PENDING,
            note=note,
            expires_at=now + timedelta(days=TEAM_INVITE_TTL_DAYS),
        )
        self._db.add(request)
        if team.owner_id is not None:
            add_notification(
                self._db, team.owner_id, NotificationKind.TEAM_REQUEST, team_id=team.id
            )
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise TeamInviteExistsError from None
        await self._db.refresh(request)
        await self._db.refresh(team)
        logger.info("team_join_requested")
        return InviteView(request, TeamSummary(team, len(members)), "", TeamInviteStatus.PENDING)

    async def my_requests(self, user: User) -> list[InviteView]:
        """``user``'s requests to join that are still open, newest first. One the owner
        declined looks pending until it expires."""
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
                TeamInvite.kind == TeamInviteKind.REQUEST,
                TeamInvite.status.in_(_OPEN),
                TeamInvite.expires_at > datetime.now(UTC),
                Team.closed_at.is_(None),
            )
            .order_by(TeamInvite.created_at.desc(), TeamInvite.id)
        )
        return [
            InviteView(request, TeamSummary(team, members), "", TeamInviteStatus.PENDING)
            for request, team, members in rows.tuples()
        ]

    # --- invite link --------------------------------------------------------------------

    def _code_hash(self, code: str) -> str:
        return keyed_hash(self._settings.secret_key, "team-invite-link", code)

    async def make_link(self, user: User, team_id: uuid.UUID) -> tuple[str, datetime]:
        """A new link for the team; any earlier link stops working. The code is returned
        once and never stored."""
        team = await self._owned(user, team_id, lock=True)
        await self._write(user)
        code = generate_token(16)
        expires_at = datetime.now(UTC) + timedelta(days=TEAM_LINK_TTL_DAYS)
        team.invite_code_hash = self._code_hash(code)
        team.invite_expires_at = expires_at
        await self._db.commit()
        logger.info("team_link_made")
        return code, expires_at

    async def revoke_link(self, user: User, team_id: uuid.UUID) -> None:
        team = await self._owned(user, team_id, lock=True)
        team.invite_code_hash = None
        team.invite_expires_at = None
        await self._db.commit()

    async def _by_link(
        self, user: User, code: str, *, lock: bool = False
    ) -> tuple[Team, list[uuid.UUID]]:
        await self._limiter.hit(
            f"team-link:{user.id}", limit=self._settings.team_link_tries_per_day
        )
        query = select(Team).where(
            Team.invite_code_hash == self._code_hash(code),
            Team.invite_expires_at > datetime.now(UTC),
            Team.closed_at.is_(None),
        )
        if lock:
            query = query.with_for_update()
        team = await self._db.scalar(query)
        if team is None:
            raise TeamLinkInvalidError
        members = await self._member_ids(team.id)
        if user.id not in members and (await blocks.blocked_with(self._db, user.id)).intersection(
            members
        ):
            raise TeamLinkInvalidError
        return team, members

    async def preview_link(self, user: User, code: str) -> TeamSummary:
        """What someone holding the link sees before joining: name, purpose and size."""
        team, members = await self._by_link(user, code)
        return TeamSummary(team, len(members))

    async def join_by_link(self, user: User, code: str) -> TeamView:
        team, members = await self._by_link(user, code, lock=True)
        if user.id in members:
            return await self.get(user, team.id)
        if len(members) >= MAX_TEAM_MEMBERS:
            raise TeamFullError
        if await self._teams_of(user.id) >= MAX_TEAMS_PER_PERSON:
            raise TooManyTeamsError
        now = datetime.now(UTC)
        self._db.add(TeamMember(id=uuid.uuid4(), team_id=team.id, user_id=user.id))
        for member_id in members:
            add_notification(self._db, member_id, NotificationKind.TEAM_JOINED, team_id=team.id)
        # An open invite to the same team is answered by joining.
        await self._db.execute(
            update(TeamInvite)
            .where(
                TeamInvite.team_id == team.id,
                TeamInvite.user_id == user.id,
                TeamInvite.status.in_(_OPEN),
            )
            .values(status=TeamInviteStatus.ACCEPTED, responded_at=now)
            .execution_options(synchronize_session=False)
        )
        await self._db.commit()
        logger.info("team_joined_by_link")
        return await self.get(user, team.id)

    async def withdraw(self, user: User, invite_id: uuid.UUID) -> None:
        """The owner takes back an open invite, or someone takes back their request to join."""
        invite = await self._db.get(TeamInvite, invite_id)
        team = await self._db.get(Team, invite.team_id) if invite is not None else None
        if invite is None or team is None or team.closed_at:
            raise TeamInviteNotFoundError
        mine = invite.user_id if invite.kind == TeamInviteKind.REQUEST else team.owner_id
        if mine != user.id:
            raise TeamInviteNotFoundError
        if invite.status not in _OPEN:
            raise TeamInviteNotPendingError
        await self._write(user)
        invite.status = TeamInviteStatus.WITHDRAWN
        invite.responded_at = datetime.now(UTC)
        await self._db.commit()


async def not_invitable(db: AsyncSession, team_id: uuid.UUID) -> set[uuid.UUID]:
    """People the matcher should not suggest for a team: its members, and anyone on either
    side of a block with one of them."""
    members = set(await db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)))
    if not members:
        return members
    pairs = await db.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(Block.blocker_id.in_(members), Block.blocked_id.in_(members))
        )
    )
    return members.union(*(pair for pair in pairs.tuples()))


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
