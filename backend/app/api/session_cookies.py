"""Setting and clearing the session and CSRF cookies.

Session cookie: httpOnly, Secure (except the plain-http local stack), SameSite=Lax, and
lives until the session's absolute expiry; idle expiry is enforced on the server.
CSRF cookie: same attributes but readable by the web app, which echoes it in X-CSRF-Token.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Response

from app.core.config import Settings
from app.models import UserSession
from app.services.auth.sessions import absolute_expiry, csrf_token_for


def _remaining_seconds(settings: Settings, session: UserSession) -> int:
    remaining = absolute_expiry(settings, session.created_at) - datetime.now(UTC)
    return max(0, int(remaining.total_seconds()))


def set_csrf_cookie(response: Response, settings: Settings, session: UserSession) -> None:
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token_for(settings, session),
        max_age=_remaining_seconds(settings, session),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )


def set_session_cookies(
    response: Response, settings: Settings, token: str, session: UserSession
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=_remaining_seconds(settings, session),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    set_csrf_cookie(response, settings, session)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in (
        (settings.session_cookie_name, True),
        (settings.csrf_cookie_name, False),
    ):
        response.delete_cookie(
            name, path="/", secure=settings.session_cookie_secure, httponly=httponly, samesite="lax"
        )


# Google sign-in (ADR 0011): ties a callback to the browser that started the attempt.
GOOGLE_STATE_COOKIE = "google_oauth_state"
GOOGLE_STATE_COOKIE_PATH = "/api/v1/auth/google"


def set_google_state_cookie(response: Response, settings: Settings, state: str, ttl: int) -> None:
    response.set_cookie(
        GOOGLE_STATE_COOKIE,
        state,
        max_age=ttl,
        path=GOOGLE_STATE_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        # Lax still sends it on Google's top-level redirect back to the callback.
        samesite="lax",
    )


def clear_google_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        GOOGLE_STATE_COOKIE,
        path=GOOGLE_STATE_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


# Admin portal (ADR 0015): the second session after the two-step code. httpOnly, Strict:
# it is only ever needed on this site's own pages and API calls.
ADMIN_SESSION_COOKIE = "admin_session"


def set_admin_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        # The server ends it after ADMIN_SESSION_IDLE_MINUTES without use; the cookie
        # never outlives the maximum.
        max_age=settings.admin_session_max_hours * 3600,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_admin_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
