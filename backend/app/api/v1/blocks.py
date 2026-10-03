"""Blocking people (ARCHITECTURE.md §8). A block works both ways; see app/services/blocks.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.reports import ReportIn, ReportReceipt
from app.schemas.social import PersonOut
from app.services import blocks, reports
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS

router = APIRouter(tags=["blocks"])

DbDep = Annotated[AsyncSession, Depends(get_db_session)]
_401: dict[str, Any] = {"model": ErrorResponse, "description": "Not signed in."}


class BlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class BlockedOut(BaseModel):
    """Someone you blocked. No name or links: blocking ends the connection."""

    user_id: uuid.UUID
    created_at: datetime
    person: PersonOut

    @classmethod
    def build(cls, item: blocks.BlockedPerson) -> BlockedOut:
        blocked_id = item.block.blocked_id
        return cls(
            user_id=blocked_id,
            created_at=item.block.created_at,
            person=PersonOut.build(blocked_id, item.profile, connected=False),
        )


class BlockList(BaseModel):
    items: list[BlockedOut]


@router.post(
    "/blocks",
    status_code=HTTPStatus.CREATED,
    summary="Block someone",
    dependencies=[Depends(require_json)],
    responses={
        401: _401,
        404: {
            "model": ErrorResponse,
            "description": "`person_not_found`: not someone you've matched, had an intro "
            "with or connected with.",
        },
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Daily block limit reached."},
    },
)
async def block_person(
    body: BlockIn, auth: AuthDep, request: Request, db: DbDep, settings: SettingsDep
) -> BlockedOut:
    """Works both ways: no chat, no intros, no matches between you, and your connection
    ends for good. They aren't told. Calling it again changes nothing. Unblocking later
    does not reopen the connection."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    return BlockedOut.build(await blocks.block(db, settings, limiter, auth.user, body.user_id))


@router.get("/blocks", summary="People you've blocked, newest first", responses={401: _401})
async def list_blocks(auth: AuthDep, db: DbDep) -> BlockList:
    return BlockList(
        items=[BlockedOut.build(item) for item in await blocks.my_blocks(db, auth.user)]
    )


@router.delete(
    "/blocks/{user_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Unblock someone",
    responses={
        401: _401,
        404: {"model": ErrorResponse, "description": "`block_not_found`."},
    },
)
async def unblock_person(user_id: uuid.UUID, auth: AuthDep, db: DbDep) -> None:
    """They can appear in your matches again. Your old connection stays ended: to talk
    again, one of you sends a new intro."""
    await blocks.unblock(db, auth.user, user_id)


@router.post(
    "/people/{user_id}/report",
    status_code=HTTPStatus.CREATED,
    summary="Report someone's profile",
    dependencies=[Depends(require_json)],
    responses={
        401: _401,
        404: {
            "model": ErrorResponse,
            "description": "`person_not_found`: not someone you've matched, had an intro "
            "with or connected with.",
        },
        409: {"model": ErrorResponse, "description": "`already_reported`."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
        429: {"model": ErrorResponse, "description": "Daily report limit reached."},
    },
)
async def report_person(
    user_id: uuid.UUID,
    body: ReportIn,
    auth: AuthDep,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> ReportReceipt:
    """The moderator sees a copy of their profile as you could see it. They are not told."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    report = await reports.report_person(
        db, settings, limiter, auth.user, user_id, body.reason, body.details
    )
    return ReportReceipt(id=report.id, created_at=report.created_at)
