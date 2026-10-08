"""The admin Communication page (A8): banners, the email send log and template tests.
Owners and admins only ("Settings and switches"); changes take a reason and are audited."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.models import BannerKind, EmailSendStatus
from app.schemas.admin_comms import (
    AdminBannerOut,
    BannerIn,
    CommsOut,
    EmailSendOut,
    EmailSendPage,
    TemplateOut,
)
from app.schemas.admin_portal import ReasonIn
from app.schemas.errors import ErrorResponse
from app.services import banners
from app.services.admin import comms
from app.services.admin.permissions import Permission
from app.services.auth.rate_limit import RateLimiter
from app.services.email import catalog

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}}
_CONFLICT: dict[int | str, dict[str, Any]] = {HTTPStatus.CONFLICT.value: {"model": ErrorResponse}}

router = APIRouter(prefix="/admin/comms", tags=["admin"], responses=_ERRORS)

Manager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_SETTINGS))]


@router.get("", summary="Banners and email templates")
async def get_comms(_: Manager, db: DbDep) -> CommsOut:
    now = datetime.now(UTC)
    return CommsOut(
        banners=[AdminBannerOut.from_banner(b, now) for b in await banners.recent(db)],
        templates=[
            TemplateOut(key=t.key, name=t.name, sent_when=t.sent_when) for t in catalog.TEMPLATES
        ],
    )


@router.post(
    "/banners",
    status_code=HTTPStatus.CREATED,
    summary="Publish a banner",
    dependencies=[Depends(require_json)],
    responses=_CONFLICT,
)
async def publish_banner(
    body: BannerIn, request: Request, admin: Manager, db: DbDep
) -> AdminBannerOut:
    """Shows at the top of the app within 60 seconds, until ``ends_at`` or until ended."""
    banner = await banners.publish(
        db,
        admin.who,
        message=body.announcement,
        kind=BannerKind(body.kind),
        ends_at=body.ends_at,
        reason=body.reason,
        ip=client_ip(request),
    )
    return AdminBannerOut.from_banner(banner, datetime.now(UTC))


@router.post(
    "/banners/{banner_id}/end",
    status_code=HTTPStatus.NO_CONTENT,
    summary="End a banner now",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def end_banner(
    banner_id: uuid.UUID, body: ReasonIn, request: Request, admin: Manager, db: DbDep
) -> None:
    await banners.end(db, admin.who, banner_id, body.reason, client_ip(request))


@router.get("/emails", summary="The email send log, newest first")
async def list_emails(
    _: Manager,
    db: DbDep,
    status: EmailSendStatus | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=comms.PAGE_MAX)] = 50,
) -> EmailSendPage:
    """Kept 30 days. Never the body of an email."""
    rows, next_cursor = await comms.send_log(db, status=status, cursor=cursor, limit=limit)
    return EmailSendPage(items=[EmailSendOut.from_send(r) for r in rows], next_cursor=next_cursor)


@router.post(
    "/emails/{send_id}/retry",
    status_code=HTTPStatus.ACCEPTED,
    summary="Retry a failed email",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def retry_email(
    send_id: uuid.UUID, body: ReasonIn, request: Request, admin: Manager, db: DbDep
) -> None:
    """Queues the job that sent it again; the usual sender sends it. Once per failed email.
    409 ``email_not_retryable`` (delivered, already retried, or a sign-in code)."""
    await comms.retry(db, admin.who, send_id, body.reason, client_ip(request))


@router.post(
    "/templates/{key}/test",
    status_code=HTTPStatus.ACCEPTED,
    summary="Send a test copy of a template to yourself",
    responses={**_NOT_FOUND, HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse}},
)
async def send_test(
    key: str, request: Request, admin: Manager, db: DbDep, settings: SettingsDep
) -> None:
    """Made-up values, "[Test]" in the subject. At most 10 an hour per admin."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=3600
    )
    await limiter.hit(f"test-email:{admin.who.user.id}", limit=comms.TESTS_PER_HOUR)
    await comms.send_test(db, admin.who, key, client_ip(request))
