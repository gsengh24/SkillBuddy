"""Security primitives: random tokens, keyed hashes, log-safe values, security headers.

Authentication itself (codes, sessions, CSRF) lives in ``app.services.auth`` and
``app.api.deps``; see ADR 0006.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

from pydantic import SecretStr
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SECURITY_HEADERS: Final = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # API responses can carry personal data and session state; never cache them.
    "Cache-Control": "no-store",
}
_HSTS: Final = "max-age=31536000; includeSubDomains"


def generate_token(nbytes: int = 32) -> str:
    """Return a URL-safe random token (256 bits by default)."""
    return secrets.token_urlsafe(nbytes)


def generate_numeric_code(digits: int = 6) -> str:
    """Return a uniformly random, zero-padded numeric one-time code."""
    return f"{secrets.randbelow(10**digits):0{digits}d}"


def constant_time_equals(left: str, right: str) -> bool:
    """Compare secrets without leaking their contents through timing."""
    return hmac.compare_digest(left.encode(), right.encode())


def keyed_hash(secret: SecretStr, purpose: str, value: str) -> str:
    """HMAC-SHA256 of ``value`` under a key derived from the server secret and ``purpose``.

    Separate purposes ("otp", "email", "csrf") get separate keys, so a digest made for one
    use can never be replayed as another.
    """
    key = hmac.new(secret.get_secret_value().encode(), purpose.encode(), hashlib.sha256)
    return hmac.new(key.digest(), value.encode(), hashlib.sha256).hexdigest()


def hash_token(token: str) -> str:
    """SHA-256 of a high-entropy random token, for storage and lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def mask_email(email: str) -> str:
    """Log-safe form of an email address: first character and domain only."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


class SecurityHeadersMiddleware:
    """Add conservative security headers to every HTTP response."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.headers = dict(_SECURITY_HEADERS)
        if hsts:
            self.headers["Strict-Transport-Security"] = _HSTS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)
