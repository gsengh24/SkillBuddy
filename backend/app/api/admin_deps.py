"""The one check every /api/v1/admin route goes through (ADR 0015).

``require_admin(permission)``:
- no session: 401;
- signed in but not an admin: 403 ``not_admin``;
- an admin whose role lacks the permission: 403 ``admin_permission_denied``;
- an admin without a live admin session (the two-step code): 401
  ``admin_two_step_required``.

``operator_or_admin`` does the same for the operator endpoints, which also accept a machine
token (the Cloudflare scheduler's tick, ADMIN_API_TOKEN) so they keep working unattended.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, SettingsDep, get_auth, get_optional_auth
from app.api.session_cookies import ADMIN_SESSION_COOKIE
from app.core.config import Settings
from app.core.errors import AuthenticationRequiredError, NotFoundError, PermissionDeniedError
from app.core.security import constant_time_equals
from app.db.session import get_db_session
from app.models import AdminSession
from app.services.admin.core import (
    AdminIdentity,
    AdminService,
    NotAdminError,
    TwoStepRequiredError,
    identity,
    require,
    resolve_admin_session,
)
from app.services.admin.permissions import Permission
from app.services.auth.rate_limit import RateLimiter

# Non-browser clients send the admin session token here instead of the cookie.
ADMIN_SESSION_HEADER: Final = "X-Admin-Session"
TWO_STEP_WINDOW_SECONDS: Final = 15 * 60

DbDep = Annotated[AsyncSession, Depends(get_db_session)]

# Which permission each guard checks, so the route tests can hold every admin route to the
# permission table without a hand-kept list.
PERMISSION_OF: dict[Callable[..., object], Permission] = {}


@dataclass(frozen=True)
class AdminContext:
    """An admin after the second step, allowed the route's permission."""

    who: AdminIdentity
    session: AdminSession
    auth: AuthContext


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_admin_service(request: Request, db: DbDep, settings: SettingsDep) -> AdminService:
    limiter = RateLimiter(
        request.app.state.session_factory,
        settings.secret_key,
        window_seconds=TWO_STEP_WINDOW_SECONDS,
    )
    return AdminService(db, settings, limiter)


async def get_admin_identity(
    auth: Annotated[AuthContext, Depends(get_auth)], db: DbDep, settings: SettingsDep
) -> AdminIdentity:
    """An admin by role, before the second step (for setting it up and passing it)."""
    who = await identity(db, settings, auth.user)
    if who is None:
        raise NotAdminError
    return who


async def _admin_context(
    request: Request,
    auth: AuthContext,
    db: AsyncSession,
    settings: Settings,
    permission: Permission,
) -> AdminContext:
    who = await identity(db, settings, auth.user)
    if who is None:
        raise NotAdminError
    require(who, permission)
    token = request.headers.get(ADMIN_SESSION_HEADER) or request.cookies.get(
        ADMIN_SESSION_COOKIE, ""
    )
    session = await resolve_admin_session(db, settings, token, auth.user.id) if token else None
    if session is None:
        raise TwoStepRequiredError
    return AdminContext(who=who, session=session, auth=auth)


def require_admin(permission: Permission) -> Callable[..., Awaitable[AdminContext]]:
    async def dependency(
        request: Request,
        auth: Annotated[AuthContext, Depends(get_auth)],
        db: DbDep,
        settings: SettingsDep,
    ) -> AdminContext:
        return await _admin_context(request, auth, db, settings, permission)

    PERMISSION_OF[dependency] = permission
    return dependency


def operator_or_admin(
    permission: Permission, header: str, token_of: Callable[[Settings], str | None]
) -> Callable[..., Awaitable[AdminContext | None]]:
    """A machine token in ``header`` (404 if none is configured, 403 if wrong), or else
    an admin with ``permission`` exactly as ``require_admin``."""

    async def dependency(
        request: Request,
        auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
        db: DbDep,
        settings: SettingsDep,
    ) -> AdminContext | None:
        if header in request.headers:
            expected = token_of(settings)
            if expected is None:
                raise NotFoundError
            supplied = request.headers.get(header, "")
            if not supplied or not constant_time_equals(supplied, expected):
                raise PermissionDeniedError
            return None
        if auth is None:
            raise AuthenticationRequiredError
        return await _admin_context(request, auth, db, settings, permission)

    PERMISSION_OF[dependency] = permission
    return dependency


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
AdminIdentityDep = Annotated[AdminIdentity, Depends(get_admin_identity)]
