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
