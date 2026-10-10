"""Teams (ADR 0016): groups of up to six. This module covers the team itself, its members,
and joining by the owner's invite.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_feature, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.teams import (
    ListedTeamPage,
    Purpose,
    TeamDetailOut,
    TeamIn,
    TeamInviteIn,
    TeamInviteList,
    TeamInviteOut,
    TeamInviteResponseIn,
    TeamLinkOut,
    TeamList,
    TeamPatch,
    TeamRequestIn,
    TeamSummaryOut,
)
from app.services import app_settings, team_chat
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS
from app.services.teams import TeamService

# Teams are switched on from the admin Settings page (A6); off by default: 503 `feature_off`.
router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    dependencies=[Depends(require_feature(app_settings.Feature.TEAMS))],
    responses={503: {"model": ErrorResponse, "description": "`feature_off`."}},
)

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_team_service(request: Request, db: DbDep, settings: SettingsDep) -> TeamService:
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return TeamService(db, settings, limiter)


ServiceDep = Annotated[TeamService, Depends(get_team_service)]
WRITE = [Depends(require_json), Depends(require_storage_capacity)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_403: dict[str, Any] = {"model": ErrorResponse, "description": "`not_team_owner`."}
_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`team_not_found`: no such open team, or you are not in it.",
}
_404_INVITE: dict[str, Any] = {"model": ErrorResponse, "description": "`team_invite_not_found`."}
_404_LINK: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`team_link_invalid`: unknown, expired or turned off.",
}
_422: dict[str, Any] = {"model": ErrorResponse, "description": "Validation failed."}
LinkCode = Annotated[str, Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
_429: dict[str, Any] = {"model": ErrorResponse, "description": "A daily limit was reached."}


@router.get("", summary="Teams you are in", responses={401: _401})
async def list_teams(auth: AuthDep, service: ServiceDep, db: DbDep) -> TeamList:
    chats = await team_chat.summaries(db, auth.user.id)
    items = []
    for summary in await service.mine(auth.user):
        item = TeamSummaryOut.build(summary)
        chat = chats.get(item.id)
        if chat is not None:
            item.unread, item.last_message_at = chat.unread, chat.last_message_at
        items.append(item)
    return TeamList(items=items)


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    summary="Create a team",
    dependencies=WRITE,
    responses={
        401: _401,
        409: {
            "model": ErrorResponse,
            "description": "`too_many_teams` or `too_many_teams_owned`.",
        },
        422: _422,
        429: _429,
    },
)
async def create_team(body: TeamIn, auth: AuthDep, service: ServiceDep) -> TeamDetailOut:
    """You become its owner and first member."""
    return TeamDetailOut.build_full(
        await service.create(auth.user, body.name, body.purpose, body.description)
    )


# Declared before `/{team_id}` so "listed", "requests" and "invites" are not read as a team id.
@router.get(
    "/listed",
    summary="Listed teams you could ask to join",
    responses={
        400: {"model": ErrorResponse, "description": "`invalid_cursor`."},
        401: _401,
    },
)
async def list_listed_teams(
    auth: AuthDep,
    service: ServiceDep,
    purpose: Annotated[Purpose | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ListedTeamPage:
    """Teams their owners chose to list. Your own teams are left out, and so is any team
    with a member on either side of a block with you."""
    items, next_cursor = await service.listed(
        auth.user, purpose=purpose, cursor=cursor, limit=limit
    )
    return ListedTeamPage(
        items=[TeamSummaryOut.build(summary) for summary in items], next_cursor=next_cursor
    )


@router.get("/requests", summary="Your open requests to join teams", responses={401: _401})
async def list_my_requests(auth: AuthDep, service: ServiceDep) -> TeamInviteList:
    """A request the owner declined looks pending until it expires."""
    return TeamInviteList(
        items=[TeamInviteOut.build(view) for view in await service.my_requests(auth.user)]
    )


@router.get("/invites", summary="Open invites to you", responses={401: _401})
async def list_my_invites(auth: AuthDep, service: ServiceDep) -> TeamInviteList:
    return TeamInviteList(
        items=[TeamInviteOut.build(view) for view in await service.my_invites(auth.user)]
    )


@router.post(
    "/invites/{invite_id}/respond",
    summary="Accept or decline an invite, or (owner) a request to join",
    dependencies=WRITE,
    responses={
        401: _401,
        404: _404_INVITE,
        409: {
            "model": ErrorResponse,
            "description": "`team_invite_not_pending`, `team_full`, `too_many_teams` or "
            "`team_not_available`.",
        },
        422: _422,
    },
)
async def respond_to_invite(
    invite_id: uuid.UUID, body: TeamInviteResponseIn, auth: AuthDep, service: ServiceDep
) -> TeamInviteOut:
    """An invite is answered by the invited person; a request to join by the team's owner.
    Accepting makes the person a member. The other side is not told about a decline."""
    return TeamInviteOut.build(await service.respond(auth.user, invite_id, accept=body.accept))


@router.delete(
    "/invites/{invite_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Take back an invite (owner) or your own request to join",
    responses={
        401: _401,
        404: _404_INVITE,
        409: {"model": ErrorResponse, "description": "`team_invite_not_pending`."},
        429: _429,
    },
)
async def withdraw_invite(invite_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    await service.withdraw(auth.user, invite_id)


@router.get(
    "/join/{code}",
    summary="The team behind an invite link",
    responses={
        401: _401,
        404: _404_LINK,
        429: _429,
    },
)
async def preview_invite_link(code: LinkCode, auth: AuthDep, service: ServiceDep) -> TeamSummaryOut:
    """Its name, purpose and size, so the person can decide. Nothing is joined."""
    return TeamSummaryOut.build(await service.preview_link(auth.user, code))


@router.post(
    "/join/{code}",
    summary="Join a team with its invite link",
    dependencies=[Depends(require_storage_capacity)],
    responses={
        401: _401,
        404: _404_LINK,
        409: {"model": ErrorResponse, "description": "`team_full` or `too_many_teams`."},
        429: _429,
    },
)
async def join_by_invite_link(code: LinkCode, auth: AuthDep, service: ServiceDep) -> TeamDetailOut:
    """You join at once, without waiting for the owner. The members are told someone
    joined. Using the link again when you are already in changes nothing."""
    return TeamDetailOut.build_full(await service.join_by_link(auth.user, code))


@router.get("/{team_id}", summary="A team and its members", responses={401: _401, 404: _404})
async def get_team(team_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> TeamDetailOut:
    return TeamDetailOut.build_full(await service.get(auth.user, team_id))


@router.patch(
    "/{team_id}",
    summary="Change a team's name, purpose or description (owner)",
    dependencies=WRITE,
    responses={401: _401, 403: _403, 404: _404, 422: _422, 429: _429},
)
async def update_team(
    team_id: uuid.UUID, body: TeamPatch, auth: AuthDep, service: ServiceDep
) -> TeamDetailOut:
    return TeamDetailOut.build_full(
        await service.update(auth.user, team_id, body.model_dump(exclude_unset=True))
    )


@router.delete(
    "/{team_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Close a team (owner)",
    responses={401: _401, 403: _403, 404: _404},
)
async def close_team(team_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    """Hidden from everyone at once; deleted `TEAM_RETENTION_DAYS` (90) later."""
    await service.close(auth.user, team_id)


@router.post(
    "/{team_id}/invites",
    status_code=HTTPStatus.CREATED,
    summary="Invite a connection, or a match suggested for the team (owner)",
    dependencies=WRITE,
    responses={
        401: _401,
        403: _403,
        404: _404,
        409: {
            "model": ErrorResponse,
            "description": "`already_member`, `team_invite_exists`, `cannot_invite`, `team_full` "
            "or `too_many_pending_invites`.",
        },
        422: _422,
        429: _429,
    },
)
async def invite_to_team(
    team_id: uuid.UUID, body: TeamInviteIn, auth: AuthDep, service: ServiceDep
) -> TeamInviteOut:
    """They get an in-app notification and have 14 days to answer."""
    return TeamInviteOut.build(
        await service.invite(auth.user, team_id, body.user_id, match_id=body.match_id)
    )


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Leave a team, or remove a member (owner)",
    responses={
        401: _401,
        403: _403,
        404: {
            "model": ErrorResponse,
            "description": "`team_not_found` or `team_member_not_found`.",
        },
        429: _429,
    },
)
async def remove_member(
    team_id: uuid.UUID, user_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    """With your own id you leave: if you own the team, its longest-standing member becomes
    the owner, and the team closes when nobody is left. With someone else's id, the owner
    removes them."""
    if user_id == auth.user.id:
        await service.leave(auth.user, team_id)
    else:
        await service.remove(auth.user, team_id, user_id)


@router.post(
    "/{team_id}/invite-link",
    status_code=HTTPStatus.CREATED,
    summary="Make an invite link (owner)",
    dependencies=[Depends(require_storage_capacity)],
    responses={401: _401, 403: _403, 404: _404, 429: _429},
)
async def make_invite_link(team_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> TeamLinkOut:
    """Good for 7 days. Any earlier link stops working. Anyone signed in who has the link
    can join while there is room, so share it with care."""
    code, expires_at = await service.make_link(auth.user, team_id)
    return TeamLinkOut(code=code, expires_at=expires_at)


@router.delete(
    "/{team_id}/invite-link",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Turn off the invite link (owner)",
    responses={401: _401, 403: _403, 404: _404},
)
async def revoke_invite_link(team_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    await service.revoke_link(auth.user, team_id)


@router.post(
    "/{team_id}/requests",
    status_code=HTTPStatus.CREATED,
    summary="Ask to join a listed team",
    dependencies=WRITE,
    responses={
        401: _401,
        404: {
            "model": ErrorResponse,
            "description": "`team_not_found`: no such listed team, or it isn't available to you.",
        },
        409: {
            "model": ErrorResponse,
            "description": "`already_member`, `team_invite_exists`, `team_full`, "
            "`too_many_pending_invites` or `too_many_teams`.",
        },
        422: _422,
        429: _429,
    },
)
async def ask_to_join(
    team_id: uuid.UUID, body: TeamRequestIn, auth: AuthDep, service: ServiceDep
) -> TeamInviteOut:
    """The owner gets an in-app notification, sees your name and note, and has 14 days to
    answer. You are not told about a decline."""
    return TeamInviteOut.build(await service.request_to_join(auth.user, team_id, body.note))
