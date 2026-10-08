"""Intros, connections and notifications."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_feature, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportIn, ReportReceipt
from app.schemas.social import (
    ConnectionList,
    ConnectionOut,
    IntroIn,
    IntroOut,
    IntroPage,
    IntroResponseIn,
    MarkedRead,
    MarkReadIn,
    NotificationOut,
    NotificationPage,
    UnreadCount,
)
from app.services import app_settings, chat, notifications, reports
from app.services.auth.rate_limit import RateLimiter
from app.services.intros import Box, IntroService
from app.services.matching.requests import DAY_SECONDS

router = APIRouter(tags=["intros"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_intro_service(request: Request, db: DbDep, settings: SettingsDep) -> IntroService:
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return IntroService(db, settings, limiter)


ServiceDep = Annotated[IntroService, Depends(get_intro_service)]

_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}
_404_INTRO: dict[str, Any] = {"model": ErrorResponse, "description": "`intro_not_found`."}
_409: dict[str, Any] = {"model": ErrorResponse, "description": "`intro_not_pending`."}


@router.post(
    "/matches/{match_id}/intro",
    status_code=HTTPStatus.CREATED,
    summary="Send an intro to a match",
    dependencies=[
        Depends(require_json),
        Depends(require_storage_capacity),
        # Can be switched off on the admin Settings page (A6).
        Depends(require_feature(app_settings.Feature.INTRO_REQUESTS)),
    ],
    responses={
        401: _401,
        404: {"model": ErrorResponse, "description": "`match_not_found` (or not yours)."},
        409: {
            "model": ErrorResponse,
            "description": "`candidate_unavailable`, `already_connected`, `intro_exists` or "
            "`too_many_pending_intros`.",
        },
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Daily intro limit reached."},
        503: {"model": ErrorResponse, "description": "`feature_off`: intros are paused."},
    },
)
async def send_intro(
    match_id: uuid.UUID, body: IntroIn, auth: AuthDep, service: ServiceDep
) -> IntroOut:
    """The other person sees your request, the match reason and your note, but not your
    name or links until they accept."""
    return IntroOut.build(await service.send(auth.user, match_id, body.note))


@router.get("/intros", summary="Intros received or sent", responses={401: _401})
async def list_intros(
    auth: AuthDep,
    service: ServiceDep,
    box: Annotated[Box, Query()] = Box.RECEIVED,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> IntroPage:
    views, next_cursor = await service.page(auth.user, box, cursor=cursor, limit=limit)
    return IntroPage(items=[IntroOut.build(view) for view in views], next_cursor=next_cursor)


@router.get("/intros/{intro_id}", summary="One intro", responses={401: _401, 404: _404_INTRO})
async def get_intro(intro_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> IntroOut:
    return IntroOut.build(await service.get(auth.user, intro_id))


@router.post(
    "/intros/{intro_id}/respond",
    summary="Accept or decline an intro",
    dependencies=[Depends(require_json)],
    responses={401: _401, 404: _404_INTRO, 409: _409},
)
async def respond_to_intro(
    intro_id: uuid.UUID, body: IntroResponseIn, auth: AuthDep, service: ServiceDep
) -> IntroOut:
    """Accepting connects you: you both see each other's name and links. Declining is
    never shown to the sender."""
    return IntroOut.build(await service.respond(auth.user, intro_id, accept=body.accept))


@router.delete(
    "/intros/{intro_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Withdraw an intro you sent",
    responses={401: _401, 404: _404_INTRO, 409: _409},
)
async def withdraw_intro(intro_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> None:
    await service.withdraw(auth.user, intro_id)


@router.get("/connections", summary="People you're connected with", responses={401: _401})
async def list_connections(auth: AuthDep, service: ServiceDep, db: DbDep) -> ConnectionList:
    rows = await service.connections(auth.user)
    chats = await chat.summaries(db, auth.user.id)
    return ConnectionList(
        items=[
            ConnectionOut.build(connection, other, profile, chats.get(connection.id))
            for connection, other, profile in rows
        ]
    )


@router.get("/notifications", summary="My notifications, newest first", responses={401: _401})
async def list_notifications(
    auth: AuthDep,
    db: DbDep,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> NotificationPage:
    items, next_cursor = await notifications.page(db, auth.user.id, cursor=cursor, limit=limit)
    return NotificationPage(
        items=[NotificationOut.build(item) for item in items],
        next_cursor=next_cursor,
        unread=await notifications.unread_count(db, auth.user.id),
    )


@router.get("/notifications/unread-count", summary="Unread notifications", responses={401: _401})
async def unread_notifications(auth: AuthDep, db: DbDep) -> UnreadCount:
    return UnreadCount(unread=await notifications.unread_count(db, auth.user.id))


@router.post(
    "/notifications/read",
    summary="Mark notifications read",
    dependencies=[Depends(require_json)],
    responses={401: _401},
)
async def mark_notifications_read(body: MarkReadIn, auth: AuthDep, db: DbDep) -> MarkedRead:
    return MarkedRead(marked=await notifications.mark_read(db, auth.user.id, body.ids))


@router.post(
    "/intros/{intro_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report an intro you received",
    dependencies=[Depends(require_json)],
    responses={
        401: _401,
        404: _404_INTRO,
        409: {"model": ErrorResponse, "description": "`already_reported`."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Daily report limit reached."},
    },
)
async def report_intro(
    intro_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> ReportReceipt:
    """The moderator sees a copy of the intro's request and note. The sender is not told."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    report = await reports.report_intro(
        db, settings, limiter, auth.user, intro_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)
