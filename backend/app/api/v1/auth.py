"""Passwordless sign-in: email a one-time code, verify it, manage the session (ADR 0006)."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.api.deps import (
    AuthContext,
    SettingsDep,
    get_auth,
    get_auth_service,
    get_client_info,
    require_json,
)
from app.api.session_cookies import clear_session_cookies, set_csrf_cookie, set_session_cookies
from app.schemas.auth import OtpRequestIn, OtpRequestOut, OtpVerifyIn, UserOut
from app.schemas.errors import ErrorResponse
from app.services.auth.events import ClientInfo
from app.services.auth.service import AuthService

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
    return UserOut.from_user(result.user)


@router.get("/me", summary="The signed-in user")
async def me(auth: AuthDep, response: Response, settings: SettingsDep) -> UserOut:
    """Also re-issues the CSRF cookie, so a client that lost it can recover."""
    if auth.via_cookie:
        set_csrf_cookie(response, settings, auth.session)
    return UserOut.from_user(auth.user)


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
