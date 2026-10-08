"""Passwordless sign-in: email a one-time code, verify it, manage the session (ADR 0006)."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import (
    AuthContext,
    SettingsDep,
    get_auth,
    get_auth_service,
    get_client_info,
    require_json,
)
from app.api.session_cookies import (
    GOOGLE_STATE_COOKIE,
    clear_google_state_cookie,
    clear_session_cookies,
    set_csrf_cookie,
    set_google_state_cookie,
    set_session_cookies,
)
from app.core.errors import AppError
from app.schemas.auth import (
    AuthMethodsOut,
    GoogleStartIn,
    GoogleStartOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    SessionList,
    SessionOut,
    UserOut,
)
from app.schemas.errors import ErrorResponse
from app.services.auth.events import ClientInfo
from app.services.auth.service import OAUTH_STATE_TTL, AuthService
from app.services.moderation import is_moderator

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ClientDep = Annotated[ClientInfo, Depends(get_client_info)]
AuthDep = Annotated[AuthContext, Depends(get_auth)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.BAD_REQUEST.value: {"model": ErrorResponse},
    HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse},
    HTTPStatus.SERVICE_UNAVAILABLE.value: {"model": ErrorResponse},
}


@router.post(
    "/otp/request",
    status_code=HTTPStatus.ACCEPTED,
    summary="Email a sign-in code",
    dependencies=[Depends(require_json)],
    responses=_ERRORS,
)
async def request_code(
    body: OtpRequestIn, service: AuthServiceDep, client: ClientDep, settings: SettingsDep
) -> OtpRequestOut:
    """Send a 6-digit code (valid 10 minutes) to the address.

    The response is the same whether or not an account exists. Requesting a new code
    invalidates any earlier unused one. Rate-limited per address and per IP (429).
    """
    await service.request_code(body.email, client)
    return OtpRequestOut(expires_in_seconds=settings.otp_ttl_minutes * 60)


@router.post(
    "/otp/verify",
    summary="Sign in with a code",
    dependencies=[Depends(require_json)],
    responses={**_ERRORS, HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse}},
)
async def verify_code(
    body: OtpVerifyIn,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> UserOut:
    """Verify the code and start a session (cookie). Creates the account on first use,
    which requires ``age_confirmed`` and ``accept_terms``; an account without a recorded age
    confirmation needs ``age_confirmed`` too. Five wrong guesses lock a code."""
    result = await service.verify_code(
        body.email,
        body.code,
        age_confirmed=body.age_confirmed,
        accept_terms=body.accept_terms,
        client=client,
    )
    set_session_cookies(response, settings, result.token, result.session)
    return UserOut.from_user(result.user, is_moderator=is_moderator(settings, result.user))


@router.get("/me", summary="The signed-in user")
async def me(auth: AuthDep, response: Response, settings: SettingsDep) -> UserOut:
    """Also re-issues the CSRF cookie, so a client that lost it can recover."""
    if auth.via_cookie:
        set_csrf_cookie(response, settings, auth.session)
    return UserOut.from_user(auth.user, is_moderator=is_moderator(settings, auth.user))


@router.post("/logout", status_code=HTTPStatus.NO_CONTENT, summary="Sign out this device")
async def logout(
    auth: AuthDep,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> None:
    await service.logout(auth.user, auth.session, client)
    clear_session_cookies(response, settings)


@router.post("/logout-all", status_code=HTTPStatus.NO_CONTENT, summary="Sign out everywhere")
async def logout_all(
    auth: AuthDep,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> None:
    await service.logout_all(auth.user, client)
    clear_session_cookies(response, settings)


_SESSION_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse, "description": "Not signed in."},
}


@router.get("/sessions", summary="My signed-in devices", responses=_SESSION_ERRORS)
async def sessions(auth: AuthDep, service: AuthServiceDep) -> SessionList:
    """Every device still signed in, most recently used first; ``current`` marks this one."""
    items = await service.sessions(auth.user)
    return SessionList(
        items=[SessionOut.from_session(item, current_id=auth.session.id) for item in items]
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Sign out one device",
    responses={
        **_SESSION_ERRORS,
        HTTPStatus.NOT_FOUND.value: {
            "model": ErrorResponse,
            "description": "Not one of your devices, or already signed out (`session_not_found`).",
        },
    },
)
async def revoke_session(
    session_id: uuid.UUID,
    auth: AuthDep,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> None:
    """Signing out the current device this way also clears its cookies, like ``/logout``."""
    await service.revoke(auth.user, session_id, client)
    if session_id == auth.session.id:
        clear_session_cookies(response, settings)


@router.post(
    "/logout-others",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Sign out every other device",
    responses=_SESSION_ERRORS,
)
async def logout_others(auth: AuthDep, service: AuthServiceDep, client: ClientDep) -> None:
    await service.logout_others(auth.user, auth.session, client)


# --- Methods and Google sign-in (ADR 0011) --------------------------------------------------

# Where the browser lands after Google sign-in fails: the web app's sign-in page, which shows
# a message for the error code.
LOGIN_PATH = "/login"


@router.get("/methods", summary="Available sign-in methods")
async def methods(settings: SettingsDep) -> AuthMethodsOut:
    available = settings.google_signin_available
    return AuthMethodsOut(
        google=available,
        google_domains=list(settings.allowed_email_domains) if available else [],
    )


@router.post(
    "/google/start",
    summary="Start Google sign-in",
    dependencies=[Depends(require_json)],
    responses={**_ERRORS, HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}},
)
async def google_start(
    body: GoogleStartIn,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> GoogleStartOut:
    """Returns Google's sign-in URL and sets a short-lived httpOnly cookie that ties the
    attempt to this browser. 404 ``google_signin_unavailable`` when Google is off."""
    start = await service.start_google(
        age_confirmed=body.age_confirmed,
        accept_terms=body.accept_terms,
        next_path=body.next,
        client=client,
    )
    set_google_state_cookie(response, settings, start.state, int(OAUTH_STATE_TTL.total_seconds()))
    return GoogleStartOut(authorization_url=start.authorization_url)


@router.get(
    "/google/callback",
    summary="Google sends the browser back here",
    status_code=HTTPStatus.SEE_OTHER,
    response_class=RedirectResponse,
    responses={HTTPStatus.SEE_OTHER.value: {"description": "To `next`, or to /login?error=<code>"}},
)
async def google_callback(
    request: Request,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
    state: Annotated[str | None, Query(max_length=200)] = None,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    """Verifies the attempt and Google's ID token, then signs in (session cookie) and
    redirects to ``next``. Any failure redirects to ``/login?error=<code>`` with a stable
    code (``google_state_invalid``, ``google_cancelled``, ``google_failed``,
    ``email_not_allowed``, ``consent_required``, ...); details go to the audit log only."""
    try:
        result = await service.finish_google(
            state=state,
            bound_state=request.cookies.get(GOOGLE_STATE_COOKIE),
            code=code,
            error=error,
            client=client,
        )
    except AppError as refused:
        redirect = RedirectResponse(
            f"{LOGIN_PATH}?{urlencode({'error': refused.code})}",
            status_code=HTTPStatus.SEE_OTHER,
        )
    else:
        redirect = RedirectResponse(result.next_path, status_code=HTTPStatus.SEE_OTHER)
        set_session_cookies(redirect, settings, result.sign_in.token, result.sign_in.session)
    clear_google_state_cookie(redirect, settings)
    return redirect
