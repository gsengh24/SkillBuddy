"""Security primitives and stubs.

Authentication (email OTP and Google sign-in) arrives with the Auth module. Until then
:func:`require_authenticated_user` fails closed: any endpoint that depends on it
responds 401, so a protected route can never be exposed by accident.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import AuthenticationRequiredError

_SECURITY_HEADERS: Final = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def generate_token(nbytes: int = 32) -> str:
    """Return a URL-safe random token suitable for one-time codes and links."""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(left: str, right: str) -> bool:
    """Compare secrets without leaking their contents through timing."""
    return hmac.compare_digest(left.encode(), right.encode())


async def require_authenticated_user() -> None:
    """Dependency for protected endpoints. Fails closed until auth is implemented."""
    raise AuthenticationRequiredError


class SecurityHeadersMiddleware:
    """Add conservative security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)
