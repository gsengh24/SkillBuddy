"""Shared FastAPI dependencies, including authentication (ADR 0006).

Protect an endpoint with ``Depends(get_current_user)``; use ``get_optional_user`` where
signed-out access is allowed. Both accept the session token from the httpOnly cookie
(browsers) or an ``Authorization: Bearer`` header (non-browser clients). Cookie-authenticated
state-changing requests must also send a valid ``X-CSRF-Token`` header.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Final

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AuthenticationRequiredError, CsrfError, UnsupportedMediaTypeError
from app.core.security import constant_time_equals
from app.db.session import get_db_session
from app.models import User, UserSession
from app.services.auth.delivery import OtpDelivery, QueuedOtpDelivery
from app.services.auth.events import ClientInfo
from app.services.auth.rate_limit import RateLimiter
from app.services.auth.service import AuthService
from app.services.auth.sessions import csrf_token_for, resolve_session
from app.services.storage import StorageMonitor

CSRF_HEADER: Final = "X-CSRF-Token"
SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})


def get_app_settings(request: Request) -> Settings:
    """Settings the running app was created with (overridable per app in tests)."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_client_info(request: Request) -> ClientInfo:
    return ClientInfo.build(
        request.client.host if request.client else None, request.headers.get("user-agent")
    )


async def require_json(request: Request) -> None:
    """Reject non-JSON bodies, so cross-site HTML forms cannot reach the endpoint."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise UnsupportedMediaTypeError


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession
    via_cookie: bool


def _read_token(request: Request, settings: Settings) -> tuple[str | None, bool]:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip(), False
    return request.cookies.get(settings.session_cookie_name), True


async def get_optional_auth(request: Request, settings: SettingsDep) -> AuthContext | None:
    token, via_cookie = _read_token(request, settings)
    if not token:
        return None
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as db:
        resolved = await resolve_session(db, settings, token)
    if resolved is None:
        return None
    session, user = resolved
    if via_cookie and request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not constant_time_equals(supplied, csrf_token_for(settings, session)):
            raise CsrfError
    return AuthContext(user=user, session=session, via_cookie=via_cookie)


async def get_auth(
    context: Annotated[AuthContext | None, Depends(get_optional_auth)],
) -> AuthContext:
    if context is None:
        raise AuthenticationRequiredError
    return context


async def get_current_user(context: Annotated[AuthContext, Depends(get_auth)]) -> User:
    return context.user


async def get_optional_user(
    context: Annotated[AuthContext | None, Depends(get_optional_auth)],
) -> User | None:
    return context.user if context else None


def get_otp_delivery(settings: SettingsDep) -> OtpDelivery:
    return QueuedOtpDelivery(code_ttl=timedelta(minutes=settings.otp_ttl_minutes))


def get_storage_monitor(request: Request, settings: SettingsDep) -> StorageMonitor:
    return StorageMonitor(request.app.state.engine, request.app.state.redis, settings)


StorageMonitorDep = Annotated[StorageMonitor, Depends(get_storage_monitor)]


async def require_storage_capacity(monitor: StorageMonitorDep) -> None:
    """Add to non-essential write endpoints: refuses with 503 near the storage limit."""
    await monitor.ensure_capacity_for_optional_writes()


def get_auth_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: SettingsDep,
    delivery: Annotated[OtpDelivery, Depends(get_otp_delivery)],
    storage: StorageMonitorDep,
) -> AuthService:
    limiter = RateLimiter(
        request.app.state.redis, window_seconds=settings.rate_limit_window_seconds
    )
    return AuthService(db, settings, limiter, delivery, storage)
