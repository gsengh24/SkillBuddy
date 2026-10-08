"""Appeals from suspended or banned people (A3). No session: a signed token from a refused
sign-in or the notice email authorises it."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request

from app.api.deps import SettingsDep, require_json
from app.api.v1.account import DbDep
from app.schemas.admin_safety import AppealIn, AppealReceipt
from app.schemas.errors import ErrorResponse
from app.services import appeals
from app.services.auth.rate_limit import RateLimiter

router = APIRouter(tags=["account"])


@router.post(
    "/appeals",
    status_code=HTTPStatus.CREATED,
    summary="Appeal a suspension or ban",
    dependencies=[Depends(require_json)],
    responses={
        HTTPStatus.UNAUTHORIZED.value: {
            "model": ErrorResponse,
            "description": "The link has expired or isn't valid (`invalid_appeal_link`).",
        },
        HTTPStatus.CONFLICT.value: {
            "model": ErrorResponse,
            "description": "`nothing_to_appeal` or `appeal_exists` (one per suspension or ban).",
        },
        HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse},
    },
)
async def appeal(
    body: AppealIn, request: Request, db: DbDep, settings: SettingsDep
) -> AppealReceipt:
    """The token comes with a refused sign-in (an hour) or in the notice email (7 days)."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=3600
    )
    ip = request.client.host if request.client else "unknown"
    await limiter.hit(f"appeal:ip:{ip}", limit=10)
    created = await appeals.submit(db, settings, body.token, body.appeal)
    return AppealReceipt(created_at=created.created_at)
