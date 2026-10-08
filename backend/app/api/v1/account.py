"""The signed-in user's own account: pause, delete, and download my data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_storage_capacity
from app.api.session_cookies import clear_session_cookies
from app.api.v1.auth import AuthDep, AuthServiceDep, ClientDep
from app.db.session import get_db_session
from app.schemas.auth import DeletionScheduledOut, UserOut
from app.schemas.data_export import DataExportList, DataExportOut
from app.schemas.errors import ErrorResponse
from app.services import data_exports
from app.services.moderation import is_moderator

router = APIRouter(tags=["account"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse, "description": "Not signed in."},
}


@router.delete("/me", status_code=HTTPStatus.ACCEPTED, summary="Delete my account")
async def delete_account(
    auth: AuthDep,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> DeletionScheduledOut:
    """Schedule permanent deletion after the grace period (30 days by default).

    Signs out every device immediately; signing in is refused during the grace period.
    """
    scheduled_for = await service.request_deletion(auth.user, client)
    clear_session_cookies(response, settings)
    return DeletionScheduledOut(deletion_scheduled_for=scheduled_for)


@router.post(
    "/me/pause",
    summary="Pause my account",
    responses={
        **_ERRORS,
        HTTPStatus.CONFLICT.value: {
            "model": ErrorResponse,
            "description": "Only an active account can be paused (`cannot_pause`).",
        },
    },
)
async def pause(
    auth: AuthDep, service: AuthServiceDep, client: ClientDep, settings: SettingsDep
) -> UserOut:
    """Hidden from matching and can't receive new intros. Sign-in and existing chats carry
    on; ``/me/resume`` undoes it."""
    user = await service.pause(auth.user, client)
    return UserOut.from_user(user, is_moderator=is_moderator(settings, user))


@router.post(
    "/me/resume",
    summary="Resume my paused account",
    responses={
        **_ERRORS,
        HTTPStatus.CONFLICT.value: {
            "model": ErrorResponse,
            "description": "The account isn't paused (`not_paused`).",
        },
    },
)
async def resume(
    auth: AuthDep, service: AuthServiceDep, client: ClientDep, settings: SettingsDep
) -> UserOut:
    user = await service.resume(auth.user, client)
    return UserOut.from_user(user, is_moderator=is_moderator(settings, user))


@router.post(
    "/me/data-exports",
    status_code=HTTPStatus.ACCEPTED,
    summary="Ask for a copy of my data",
    dependencies=[Depends(require_storage_capacity)],
    responses={
        **_ERRORS,
        HTTPStatus.CONFLICT.value: {
            "model": ErrorResponse,
            "description": "One is being built, or one was asked for recently "
            "(`data_export_recent`).",
        },
        HTTPStatus.SERVICE_UNAVAILABLE.value: {
            "model": ErrorResponse,
            "description": "Storage nearly full; try again later.",
        },
    },
)
async def request_data_export(auth: AuthDep, db: DbDep, settings: SettingsDep) -> DataExportOut:
    """Builds the file in the background and emails a link that works for
    ``DATA_EXPORT_LINK_HOURS``. The file has your account, profile, requests, intros,
    connections and the messages you sent and received."""
    export = await data_exports.request_export(db, settings, auth.user)
    return DataExportOut.from_export(export)


@router.get("/me/data-exports", summary="My data download requests", responses=_ERRORS)
async def list_data_exports(auth: AuthDep, db: DbDep) -> DataExportList:
    items = await data_exports.recent_exports(db, auth.user)
    return DataExportList(items=[DataExportOut.from_export(item) for item in items])


@router.get(
    "/me/data-exports/{export_id}/download",
    summary="Download my data",
    response_class=Response,
    responses={
        HTTPStatus.OK.value: {
            "content": {"application/json": {}},
            "description": "The file, as a JSON attachment.",
        },
        **_ERRORS,
        HTTPStatus.NOT_FOUND.value: {
            "model": ErrorResponse,
            "description": "Not one of your requests (`data_export_not_found`).",
        },
        HTTPStatus.GONE.value: {
            "model": ErrorResponse,
            "description": "Expired, not ready or a wrong token (`data_export_unavailable`).",
        },
    },
)
async def download_data_export(
    export_id: uuid.UUID,
    auth: AuthDep,
    db: DbDep,
    token: Annotated[str, Query(min_length=1, max_length=128, description="From the email.")],
) -> Response:
    """Needs both your session and the token from the emailed link."""
    data = await data_exports.download(db, auth.user, export_id, token)
    name = f"cynergi-data-{datetime.now(UTC):%Y-%m-%d}.json"
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )
