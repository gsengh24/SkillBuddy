"""Match requests and their matches. The matcher itself runs in a background job."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.matching import (
    MatchList,
    MatchOut,
    MatchRequestIn,
    MatchRequestOut,
    MatchRequestPage,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS, MatchRequestService

router = APIRouter(prefix="/requests", tags=["matching"])


def get_match_request_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: SettingsDep,
) -> MatchRequestService:
    # A day-long window: MATCH_REQUESTS_PER_DAY per user.
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return MatchRequestService(db, settings, limiter)


ServiceDep = Annotated[MatchRequestService, Depends(get_match_request_service)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    404: {"model": ErrorResponse, "description": "No such request (`match_request_not_found`)."},
}


@router.post(
    "",
    status_code=HTTPStatus.ACCEPTED,
    summary="Ask for matches",
    dependencies=[Depends(require_json), Depends(require_storage_capacity)],
    responses={
        401: _ERRORS[401],
        409: {
            "model": ErrorResponse,
            "description": "`profile_required` or `too_many_open_requests`.",
        },
        415: {"model": ErrorResponse, "description": "The body is not JSON."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Daily request limit reached."},
        503: {"model": ErrorResponse, "description": "Storage nearly full; try again later."},
    },
)
async def create_request(
    body: MatchRequestIn, auth: AuthDep, service: ServiceDep
) -> MatchRequestOut:
    """Saves the request and returns at once with `status: pending`. Matches are found in
    the background (usually within 30 seconds); poll `GET /requests/{id}`."""
    request = await service.create(auth.user, body.text, body.intent)
    return MatchRequestOut.build(request, 0)


@router.get(
    "",
    summary="My requests, newest first",
    responses={401: _ERRORS[401], 400: {"model": ErrorResponse, "description": "Bad cursor."}},
)
async def list_requests(
    auth: AuthDep,
    service: ServiceDep,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> MatchRequestPage:
    page = await service.page(auth.user, cursor=cursor, limit=limit)
    return MatchRequestPage(
        items=[MatchRequestOut.build(r, count) for r, count in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{request_id}", summary="One request", responses=_ERRORS)
async def get_request(request_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> MatchRequestOut:
    request, count = await service.get(auth.user, request_id)
    return MatchRequestOut.build(request, count)


@router.get("/{request_id}/matches", summary="The matches for a request", responses=_ERRORS)
async def list_matches(request_id: uuid.UUID, auth: AuthDep, service: ServiceDep) -> MatchList:
    """In rank order, each with the reason it was suggested. Empty while the request is
    `pending`, or when nobody fits yet."""
    rows = await service.matches(auth.user, request_id)
    return MatchList(items=[MatchOut.build(match, profile) for match, profile in rows])


@router.post("/{request_id}/close", summary="Close a request", responses=_ERRORS)
async def close_request(
    request_id: uuid.UUID, auth: AuthDep, service: ServiceDep
) -> MatchRequestOut:
    """Stops a request from counting as open. Its matches stay visible."""
    request, count = await service.close(auth.user, request_id)
    return MatchRequestOut.build(request, count)
