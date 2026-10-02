"""Chat between connected people, delivered by client polling (ADR 0012)."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.chat import MessageIn, MessageOut, MessagePage, MessageUpdates
from app.schemas.errors import ErrorResponse
from app.services.auth.rate_limit import RateLimiter
from app.services.chat import ChatService
from app.services.matching.requests import DAY_SECONDS

router = APIRouter(tags=["chat"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_chat_service(request: Request, db: DbDep, settings: SettingsDep) -> ChatService:
    factory = request.app.state.session_factory
    return ChatService(
        db,
        settings,
        minute_limiter=RateLimiter(factory, settings.secret_key, window_seconds=60),
        day_limiter=RateLimiter(factory, settings.secret_key, window_seconds=DAY_SECONDS),
    )


ServiceDep = Annotated[ChatService, Depends(get_chat_service)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "`conversation_not_found`: no such connection, or you're not in it.",
}
_429: dict[str, Any] = {"model": ErrorResponse, "description": "Rate limited (see Retry-After)."}


@router.get(
    "/connections/{connection_id}/messages",
    summary="Messages in one conversation, newest first",
    responses={401: _401, 404: _404},
)
async def list_messages(
    connection_id: uuid.UUID,
    auth: AuthDep,
    service: ServiceDep,
    settings: SettingsDep,
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    items, next_cursor = await service.history(auth.user, connection_id, before=before, limit=limit)
    return MessagePage(
        items=[MessageOut.build(view) for view in items],
        next_cursor=next_cursor,
        retention_days=settings.message_retention_days,
    )


@router.post(
    "/connections/{connection_id}/messages",
    status_code=HTTPStatus.CREATED,
    summary="Send a message",
    dependencies=[Depends(require_json), Depends(require_storage_capacity)],
    responses={
        401: _401,
        404: _404,
        409: {
            "model": ErrorResponse,
            "description": "`conversation_closed`: the other person's account is not active.",
        },
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: _429,
    },
)
async def send_message(
    connection_id: uuid.UUID, body: MessageIn, auth: AuthDep, service: ServiceDep
) -> MessageOut:
    """Only possible inside a connection (both people accepted). Messages are deleted
    `MESSAGE_RETENTION_DAYS` (90) after they were sent."""
    return MessageOut.build(await service.send(auth.user, connection_id, body.body))


@router.post(
    "/connections/{connection_id}/read",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Mark a conversation read",
    responses={401: _401, 404: _404},
)
async def mark_conversation_read(
    connection_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> None:
    await service.mark_read(auth.user, connection_id)


@router.get(
    "/messages/updates",
    summary="Poll for new messages in all your conversations",
    responses={
        400: {"model": ErrorResponse, "description": "`invalid_cursor`."},
        401: _401,
        429: _429,
    },
)
async def message_updates(
    auth: AuthDep,
    service: ServiceDep,
    after: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> MessageUpdates:
    """Start without `after` to get a cursor, then pass the returned `cursor` each time.

    Poll on this cadence (ADR 0012): every 3 s for a minute after a message, every 10 s
    until 5 quiet minutes, every 30 s until 10 quiet minutes, then stop until the person
    is back; never while the app is hidden. If `poll_after_seconds` is set, wait that long.
    """
    return MessageUpdates.build(await service.updates(auth.user, after=after, limit=limit))
