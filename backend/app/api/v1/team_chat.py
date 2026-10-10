"""Team chat (ADR 0016). New messages arrive through the one poll, `GET /messages/updates`
(`team_items`); these endpoints send, page back through history and mark a team's chat read.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_feature, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.chat import MessageIn, TeamMessageOut, TeamMessagePage
from app.schemas.errors import ErrorResponse
from app.services import app_settings
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS
from app.services.team_chat import TeamChatService

# Needs both switches on the admin Settings page (A6): teams and chats.
router = APIRouter(
    prefix="/teams/{team_id}",
    tags=["teams"],
    dependencies=[
        Depends(require_feature(app_settings.Feature.TEAMS)),
        Depends(require_feature(app_settings.Feature.CHATS)),
    ],
    responses={503: {"model": ErrorResponse, "description": "`feature_off`."}},
)

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_team_chat_service(request: Request, db: DbDep, settings: SettingsDep) -> TeamChatService:
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return TeamChatService(db, settings, limiter)


ServiceDep = Annotated[TeamChatService, Depends(get_team_chat_service)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`team_not_found`: no such open team, or you are not in it.",
}


@router.get(
    "/messages",
    summary="Messages in a team's chat, newest first",
    responses={
        400: {"model": ErrorResponse, "description": "`invalid_cursor`."},
        401: _401,
        404: _404,
    },
)
async def list_team_messages(
    team_id: uuid.UUID,
    auth: AuthDep,
    service: ServiceDep,
    settings: SettingsDep,
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TeamMessagePage:
    """A new member can read what was said before they joined."""
    items, next_cursor = await service.history(auth.user, team_id, before=before, limit=limit)
    return TeamMessagePage(
        items=[TeamMessageOut.build(message) for message in items],
        next_cursor=next_cursor,
        retention_days=settings.message_retention_days,
    )


@router.post(
    "/messages",
    status_code=HTTPStatus.CREATED,
    summary="Send a message to a team",
    dependencies=[Depends(require_json), Depends(require_storage_capacity)],
    responses={
        401: _401,
        404: _404,
        422: {
            "model": ErrorResponse,
            "description": "Validation failed, or `message_too_long` (the length limit).",
        },
        429: {"model": ErrorResponse, "description": "Daily message limit (see Retry-After)."},
    },
)
async def send_team_message(
    team_id: uuid.UUID, body: MessageIn, auth: AuthDep, service: ServiceDep
) -> TeamMessageOut:
    """Counts against the same daily limit as one-to-one messages. Deleted
    `MESSAGE_RETENTION_DAYS` (90) after sending."""
    return TeamMessageOut.build(await service.send(auth.user, team_id, body.body))


@router.post(
    "/read",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Mark a team's chat read",
    responses={401: _401, 404: _404},
)
async def mark_team_read(team_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    await service.mark_read(auth.user, team_id)
