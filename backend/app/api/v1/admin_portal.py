"""The admin portal API (ADR 0015). Every route goes through ``require_admin`` or, for
setting up and passing the second step, ``get_admin_identity``."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.admin_deps import (
    AdminContext,
    AdminIdentityDep,
    AdminServiceDep,
    DbDep,
    client_ip,
    require_admin,
)
from app.api.deps import SettingsDep, require_json
from app.api.session_cookies import clear_admin_session_cookie, set_admin_session_cookie
from app.models import AdminRole
from app.schemas.admin_portal import (
    AdminMeOut,
    AdminSessionOut,
    AuditEntryOut,
    AuditPage,
    GrantIn,
    PermissionRow,
    PermissionTable,
    ReasonIn,
    TeamMemberOut,
    TeamOut,
    TwoStepCodeIn,
    TwoStepSetupOut,
    TwoStepStatusOut,
)
from app.schemas.errors import ErrorResponse
from app.services.admin import core
from app.services.admin.permissions import LABELS, ROLE_PERMISSIONS, Permission, permissions_of

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {
        "model": ErrorResponse,
        "description": "Not signed in, or the two-step code is needed (`admin_two_step_required`).",
    },
    HTTPStatus.FORBIDDEN.value: {
        "model": ErrorResponse,
        "description": "Not an admin (`not_admin`), or the role doesn't allow it "
        "(`admin_permission_denied`).",
    },
}

router = APIRouter(prefix="/admin", tags=["admin"], responses=_ERRORS)

Viewer = Annotated[AdminContext, Depends(require_admin(Permission.VIEW_DASHBOARDS))]
TeamManager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_ADMINS))]


def _name(email: str) -> str:
    return email.split("@", 1)[0]


# --- the second step -----------------------------------------------------------------------


@router.get("/two-step", summary="Is two-step login set up for me?")
async def two_step_status(who: AdminIdentityDep) -> TwoStepStatusOut:
    return TwoStepStatusOut(role=who.role.value, two_step_enabled=who.two_step_enabled)


@router.post(
    "/two-step/setup",
    summary="Start setting up two-step login",
    responses={HTTPStatus.CONFLICT.value: {"model": ErrorResponse}},
)
async def two_step_setup(who: AdminIdentityDep, service: AdminServiceDep) -> TwoStepSetupOut:
    """A new secret for an authenticator app, until the first code is confirmed."""
    setup = await service.start_two_step(who)
    return TwoStepSetupOut(secret=setup.secret, otpauth_uri=setup.otpauth_uri)


@router.post(
    "/two-step/confirm",
    summary="Turn two-step login on with a first code",
    dependencies=[Depends(require_json)],
    responses={
        HTTPStatus.BAD_REQUEST.value: {"model": ErrorResponse},
        HTTPStatus.CONFLICT.value: {"model": ErrorResponse},
        HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse},
    },
)
async def two_step_confirm(
    body: TwoStepCodeIn,
    request: Request,
    response: Response,
    who: AdminIdentityDep,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> AdminSessionOut:
    """Returns the recovery codes once, and starts an admin session."""
    signed_in = await service.confirm_two_step(who, body.code, client_ip(request))
    set_admin_session_cookie(response, settings, signed_in.token)
    return AdminSessionOut(
        expires_at=signed_in.session.expires_at, recovery_codes=signed_in.recovery_codes
    )


@router.post(
    "/two-step/verify",
    summary="Pass the second step",
    dependencies=[Depends(require_json)],
    responses={
        HTTPStatus.BAD_REQUEST.value: {"model": ErrorResponse},
        HTTPStatus.CONFLICT.value: {"model": ErrorResponse},
        HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse},
    },
)
async def two_step_verify(
    body: TwoStepCodeIn,
    request: Request,
    response: Response,
    who: AdminIdentityDep,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> AdminSessionOut:
    """A code from the app, or one unused recovery code. Non-browser clients send the
    returned cookie's value as ``X-Admin-Session``."""
    signed_in = await service.verify(who, body.code, client_ip(request))
    set_admin_session_cookie(response, settings, signed_in.token)
    return AdminSessionOut(expires_at=signed_in.session.expires_at)


@router.post("/sign-out", status_code=HTTPStatus.NO_CONTENT, summary="End the admin session")
async def sign_out(
    request: Request,
    response: Response,
    admin: Viewer,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> None:
    """Ends only the admin session; the normal one stays."""
    await service.sign_out(admin.who, admin.session, client_ip(request))
    clear_admin_session_cookie(response, settings)


# --- who am I, and what may roles do -------------------------------------------------------


@router.get("/me", summary="The signed-in admin")
async def me(admin: Viewer) -> AdminMeOut:
    user = admin.who.user
    return AdminMeOut(
        user_id=user.id,
        email=user.email,
        name=_name(user.email),
        role=admin.who.role.value,
        permissions=[p.value for p in permissions_of(admin.who.role)],
    )


@router.get("/permissions", summary="What each role may do")
async def permissions(_: Viewer) -> PermissionTable:
    """The permission table every admin route is checked against."""
    roles = list(AdminRole)
    return PermissionTable(
        roles=[role.value for role in roles],
        rows=[
            PermissionRow(
                permission=permission.value,
                label=label,
                roles=[role.value for role in roles if permission in ROLE_PERMISSIONS[role]],
            )
            for permission, label in LABELS.items()
        ],
    )


# --- audit log and team (owners) ----------------------------------------------------------


@router.get("/audit", summary="The audit log, newest first")
async def audit(
    _: TeamManager,
    db: DbDep,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=core.AUDIT_PAGE_MAX)] = core.AUDIT_PAGE_MAX,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_id: uuid.UUID | None = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
) -> AuditPage:
    """Entries can't be edited or deleted (the database refuses)."""
    items, next_cursor = await core.audit_page(
        db, cursor=cursor, limit=limit, action=action, actor_id=actor_id, target_id=target_id
    )
    return AuditPage(
        items=[AuditEntryOut.from_entry(item) for item in items], next_cursor=next_cursor
    )


@router.get("/team", summary="Admin accounts")
async def team(_: TeamManager, service: AdminServiceDep, settings: SettingsDep) -> TeamOut:
    members = await service.team()
    return TeamOut(
        items=[
            TeamMemberOut(
                user_id=user.id,
                email=user.email,
                role=role.value,
                from_environment=user.email.lower() in settings.admin_owner_emails,
                two_step_enabled=bool(account and account.two_step_enabled_at),
                last_active_at=seen,
            )
            for user, role, account, seen in members
        ]
    )


@router.post(
    "/team",
    status_code=HTTPStatus.CREATED,
    summary="Give someone an admin role",
    dependencies=[Depends(require_json)],
    responses={
        HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse},
        HTTPStatus.CONFLICT.value: {"model": ErrorResponse},
    },
)
async def grant(
    body: GrantIn, request: Request, admin: TeamManager, service: AdminServiceDep
) -> TeamMemberOut:
    """They need an account already. They set up two-step login the first time they open
    the admin portal. Owners can only be set on the server."""
    user = await service.grant(
        admin.who, body.email, AdminRole(body.role), body.reason, client_ip(request)
    )
    return TeamMemberOut(
        user_id=user.id,
        email=user.email,
        role=body.role,
        from_environment=False,
        two_step_enabled=False,
        last_active_at=None,
    )


@router.post(
    "/team/{user_id}/remove",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Take someone's admin role away",
    dependencies=[Depends(require_json)],
    responses={
        HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse},
        HTTPStatus.CONFLICT.value: {"model": ErrorResponse},
    },
)
async def remove(
    user_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    admin: TeamManager,
    service: AdminServiceDep,
) -> None:
    """Ends their admin sessions and removes their two-step set-up too."""
    await service.remove(admin.who, user_id, body.reason, client_ip(request))
