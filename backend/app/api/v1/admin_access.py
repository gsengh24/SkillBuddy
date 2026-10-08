"""The admin Signup and access page (A5). Owners and admins only ("Signup and invites"),
reading as well as changing; every change takes a reason and is audited."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import require_json
from app.models import DomainKind
from app.schemas.admin_access import (
    AccessOut,
    ApplicationOut,
    ApplicationPage,
    DecisionIn,
    DomainIn,
    DomainOut,
    InviteCodeIn,
    InviteCodeOut,
    InviteCodePage,
    InvitedOut,
    ModeIn,
)
from app.schemas.admin_portal import ReasonIn
from app.schemas.errors import ErrorResponse
from app.services.admin import access
from app.services.admin.permissions import Permission

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}}
_CONFLICT: dict[int | str, dict[str, Any]] = {HTTPStatus.CONFLICT.value: {"model": ErrorResponse}}

router = APIRouter(prefix="/admin/access", tags=["admin"], responses=_ERRORS)

Manager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_SIGNUP))]
Cursor = Annotated[str | None, Query(max_length=200)]
Limit = Annotated[int, Query(ge=1, le=access.PAGE_MAX)]


async def _summary(db: DbDep) -> AccessOut:
    found = await access.summary(db)
    return AccessOut(
        mode=found.mode,
        waitlist=found.waitlist,
        allowed_domains=found.allowed_domains,
        blocked_domains=found.blocked_domains,
    )


@router.get("", summary="Signup mode, waitlist size and email domains")
async def get_access(_: Manager, db: DbDep) -> AccessOut:
    return await _summary(db)


@router.post(
    "/mode",
    summary="Change the signup mode",
    dependencies=[Depends(require_json)],
)
async def set_mode(body: ModeIn, request: Request, admin: Manager, db: DbDep) -> AccessOut:
    """Applies to the next sign-up. Existing users can always sign in, whatever the mode."""
    await access.set_mode(db, admin.who, body.mode, body.reason, client_ip(request))
    return await _summary(db)


@router.get("/applications", summary="The approval queue, oldest first")
async def list_applications(
    _: Manager, db: DbDep, cursor: Cursor = None, limit: Limit = 20
) -> ApplicationPage:
    rows, next_cursor = await access.pending_applications(db, cursor=cursor, limit=limit)
    return ApplicationPage(
        items=[ApplicationOut.from_application(row) for row in rows], next_cursor=next_cursor
    )


@router.post(
    "/applications/{application_id}/decide",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Approve or reject an application",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def decide_application(
    application_id: uuid.UUID, body: DecisionIn, request: Request, admin: Manager, db: DbDep
) -> None:
    """Approving lets the address create an account and emails it a one-use invite code
    (valid 14 days). 409 ``application_already_decided``."""
    await access.decide(
        db,
        admin.who,
        application_id,
        approve=body.decision == "approve",
        reason=body.reason,
        ip=client_ip(request),
    )


@router.post(
    "/applications/invite-next",
    summary="Approve the 10 oldest applications",
    dependencies=[Depends(require_json)],
)
async def invite_next(body: ReasonIn, request: Request, admin: Manager, db: DbDep) -> InvitedOut:
    invited = await access.invite_next(db, admin.who, body.reason, client_ip(request))
    return InvitedOut(invited=invited)


@router.get("/codes", summary="Invite codes, newest first")
async def list_codes(
    _: Manager, db: DbDep, cursor: Cursor = None, limit: Limit = 20
) -> InviteCodePage:
    """Shareable codes only; approved applications' one-use codes are not listed."""
    rows, next_cursor = await access.invite_codes(db, cursor=cursor, limit=limit)
    now = datetime.now(UTC)
    return InviteCodePage(
        items=[InviteCodeOut.from_row(row, now) for row in rows], next_cursor=next_cursor
    )


@router.post(
    "/codes",
    status_code=HTTPStatus.CREATED,
    summary="Create an invite code",
    dependencies=[Depends(require_json)],
    responses=_CONFLICT,
)
async def create_code(
    body: InviteCodeIn, request: Request, admin: Manager, db: DbDep
) -> InviteCodeOut:
    """409 ``invite_code_taken`` or ``invalid_invite_code_format``."""
    row = await access.create_code(
        db,
        admin.who,
        code=body.code or None,
        max_uses=body.max_uses,
        expires_in_days=body.expires_in_days,
        reason=body.reason,
        ip=client_ip(request),
    )
    return InviteCodeOut.from_row(row, datetime.now(UTC))


@router.post(
    "/codes/{code_id}/revoke",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Revoke an invite code",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def revoke_code(
    code_id: uuid.UUID, body: ReasonIn, request: Request, admin: Manager, db: DbDep
) -> None:
    """The code stops working; people who already joined with it are not affected."""
    await access.revoke_code(db, admin.who, code_id, body.reason, client_ip(request))


@router.post(
    "/domains/{kind}",
    status_code=HTTPStatus.CREATED,
    summary="Add an allowed or blocked email domain",
    dependencies=[Depends(require_json)],
    responses=_CONFLICT,
)
async def add_domain(
    kind: DomainKind, body: DomainIn, request: Request, admin: Manager, db: DbDep
) -> DomainOut:
    """For new accounts only. An empty allow list means any domain; blocked wins. 409
    ``invalid_domain``, ``domain_already_listed`` or ``domain_list_full``."""
    domain = await access.add_domain(
        db, admin.who, kind, body.domain, body.reason, client_ip(request)
    )
    return DomainOut(domain=domain)


@router.post(
    "/domains/{kind}/remove",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Remove an allowed or blocked email domain",
    dependencies=[Depends(require_json)],
    responses=_NOT_FOUND,
)
async def remove_domain(
    kind: DomainKind, body: DomainIn, request: Request, admin: Manager, db: DbDep
) -> None:
    await access.remove_domain(db, admin.who, kind, body.domain, body.reason, client_ip(request))
