"""Teams (ADR 0016): groups of up to six. This module covers the team itself, its members,
and joining by the owner's invite.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_feature, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.teams import (
    TeamDetailOut,
    TeamIn,
    TeamInviteIn,
    TeamInviteList,
    TeamInviteOut,
    TeamInviteResponseIn,
    TeamList,
    TeamPatch,
    TeamSummaryOut,
)
from app.services import app_settings
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
_422: dict[str, Any] = {"model": ErrorResponse, "description": "Validation failed."}
_429: dict[str, Any] = {"model": ErrorResponse, "description": "A daily limit was reached."}


@router.get("", summary="Teams you are in", responses={401: _401})
async def list_teams(auth: AuthDep, service: ServiceDep) -> TeamList:
    return TeamList(
        items=[TeamSummaryOut.build(summary) for summary in await service.mine(auth.user)]
    )


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


# Declared before `/{team_id}` so "invites" is not read as a team id.
@router.get("/invites", summary="Open invites to you", responses={401: _401})
async def list_my_invites(auth: AuthDep, service: ServiceDep) -> TeamInviteList:
    return TeamInviteList(
        items=[TeamInviteOut.build(view) for view in await service.my_invites(auth.user)]
    )


@router.post(
    "/invites/{invite_id}/respond",
    summary="Accept or decline an invite to a team",
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
    """Accepting makes you a member. The owner is not told about a decline."""
    return TeamInviteOut.build(await service.respond(auth.user, invite_id, accept=body.accept))


@router.delete(
    "/invites/{invite_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Take back an invite (owner)",
    responses={
        401: _401,
        404: _404_INVITE,
        409: {"model": ErrorResponse, "description": "`team_invite_not_pending`."},
        429: _429,
    },
)
async def withdraw_invite(invite_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    await service.withdraw(auth.user, invite_id)


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
    summary="Invite someone you are connected with (owner)",
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
    return TeamInviteOut.build(await service.invite(auth.user, team_id, body.user_id))


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
