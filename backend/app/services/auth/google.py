"""Google OpenID Connect: authorization URL, code exchange and ID token checks (ADR 0011).

Authorization-code flow with PKCE (S256), run on the server. Scopes: openid, email and
profile only. The ID token is accepted only if every check passes:

- RS256 signature from a key in Google's published key set (refetched once for an unknown
  key id, otherwise cached for an hour);
- issuer, audience (our client id), expiry and issued-at, with 60 seconds of clock leeway;
- the nonce bound to this attempt;
- ``email_verified`` is true;
- the ``hd`` (hosted domain) claim equals the email's own domain. Whether that domain is
  allowed at all is checked separately against ALLOWED_EMAIL_DOMAINS (``policy.py``), so
  ``hd`` alone never admits anyone.

Nothing secret (client secret, authorization code, tokens) is ever logged or put into an
error message: failures carry only a short reason code.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import Settings
from app.core.security import constant_time_equals, keyed_hash
from app.models import GOOGLE_PICTURE_URL_MAX_LENGTH

logger = logging.getLogger(__name__)

SCOPES: Final = "openid email profile"
CLOCK_LEEWAY_SECONDS: Final = 60
JWKS_CACHE_SECONDS: Final = 3600
# Google serves account pictures from these hosts. Any other address in the ``picture``
# claim is ignored, so the web app only ever loads pictures from Google (ADR 0017).
_PICTURE_URL: Final = re.compile(r"https://lh[3-6]\.googleusercontent\.com/[\w\-./=~%]+", re.ASCII)

# jwks_url -> (fetched_at, {kid: key})
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class GoogleSignInError(Exception):
    """A rejected attempt. ``reason`` is a short code for logs and the audit log only."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    hosted_domain: str
    # The account picture's address, or None when Google sent none we accept.
    picture_url: str | None = None


def picture_url_from(claim: object) -> str | None:
    """The ``picture`` claim, if it is a Google-hosted https address of a sane length."""
    if (
        isinstance(claim, str)
        and len(claim) <= GOOGLE_PICTURE_URL_MAX_LENGTH
        and _PICTURE_URL.fullmatch(claim)
    ):
        return claim
    return None


def nonce_for(settings: Settings, state: str) -> str:
    """The nonce is derived from the state, so it never needs storing."""
    return keyed_hash(settings.secret_key, "oidc-nonce", state)


def code_verifier_for(settings: Settings, state: str) -> str:
    """PKCE verifier: 64 hex characters (RFC 7636 allows 43-128 unreserved characters)."""
    return keyed_hash(settings.secret_key, "oidc-pkce", state)


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class GoogleOidcClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self._transport, timeout=self._settings.google_oidc_timeout_seconds
        )

    def authorization_url(self, state: str) -> str:
        settings = self._settings
        domains = settings.allowed_email_domains
        params = {
            "response_type": "code",
            "client_id": settings.google_oauth_client_id or "",
            "redirect_uri": settings.google_oauth_redirect_uri or "",
            "scope": SCOPES,
            "state": state,
            "nonce": nonce_for(settings, state),
            "code_challenge": code_challenge(code_verifier_for(settings, state)),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        if len(domains) == 1:
            # Only a hint for Google's account chooser; the domain is enforced on our side.
            params["hd"] = domains[0]
        return f"{settings.google_oidc_authorization_url}?{urlencode(params)}"

    async def sign_in(self, code: str, state: str) -> GoogleIdentity:
        """Exchange the code (with the PKCE verifier) and verify the returned ID token."""
        id_token = await self._exchange(code, state)
        return await self.verify_id_token(id_token, expected_nonce=nonce_for(self._settings, state))

    async def _exchange(self, code: str, state: str) -> str:
        settings = self._settings
        secret = settings.google_oauth_client_secret
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.google_oauth_redirect_uri or "",
            "client_id": settings.google_oauth_client_id or "",
            "client_secret": secret.get_secret_value() if secret else "",
            "code_verifier": code_verifier_for(settings, state),
        }
        try:
            async with self._http() as http:
                response = await http.post(
                    settings.google_oidc_token_url,
                    data=form,
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError:
            raise GoogleSignInError("token_endpoint_unreachable") from None
        if response.status_code != 200:
            # The body can echo request details: never log or raise it.
            logger.warning("google_token_exchange_failed", extra={"status": response.status_code})
            raise GoogleSignInError("token_exchange_failed")
        try:
            id_token = response.json().get("id_token")
        except ValueError:
            id_token = None
        if not isinstance(id_token, str) or not id_token:
            raise GoogleSignInError("no_id_token")
        return id_token

    async def _keys(self, *, refresh: bool) -> dict[str, Any]:
        url = self._settings.google_oidc_jwks_url
        cached = _jwks_cache.get(url)
        if cached and not refresh and time.monotonic() - cached[0] < JWKS_CACHE_SECONDS:
            return cached[1]
        try:
            async with self._http() as http:
                response = await http.get(url)
            response.raise_for_status()
            key_set = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, ValueError, jwt.PyJWKSetError):
            raise GoogleSignInError("jwks_unavailable") from None
        keys = {key.key_id: key.key for key in key_set.keys if key.key_id}
        _jwks_cache[url] = (time.monotonic(), keys)
        return keys

    async def _signing_key(self, id_token: str) -> Any:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError:
            raise GoogleSignInError("malformed_token") from None
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str):
            raise GoogleSignInError("bad_token_header")
        keys = await self._keys(refresh=False)
        if kid not in keys:
            keys = await self._keys(refresh=True)  # Google rotates keys
        if kid not in keys:
            raise GoogleSignInError("unknown_signing_key")
        return keys[kid]

    async def verify_id_token(self, id_token: str, *, expected_nonce: str) -> GoogleIdentity:
        settings = self._settings
        key = await self._signing_key(id_token)
        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key=key,
                algorithms=["RS256"],
                audience=settings.google_oauth_client_id,
                issuer=settings.google_oidc_issuers,
                leeway=CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            raise GoogleSignInError("token_expired") from None
        except jwt.InvalidAudienceError:
            raise GoogleSignInError("wrong_audience") from None
        except jwt.InvalidIssuerError:
            raise GoogleSignInError("wrong_issuer") from None
        except jwt.InvalidSignatureError:
            raise GoogleSignInError("bad_signature") from None
        except jwt.PyJWTError:
            raise GoogleSignInError("invalid_token") from None

        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or not constant_time_equals(nonce, expected_nonce):
            raise GoogleSignInError("nonce_mismatch")
        if claims.get("email_verified") is not True:
            raise GoogleSignInError("email_not_verified")
        email = claims.get("email")
        subject = claims.get("sub")
        if not isinstance(email, str) or "@" not in email or not isinstance(subject, str):
            raise GoogleSignInError("missing_email")
        email = email.strip().lower()
        domain = email.rpartition("@")[2]
        hosted_domain = claims.get("hd")
        if not isinstance(hosted_domain, str) or hosted_domain.lower() != domain:
            raise GoogleSignInError("hosted_domain_mismatch")
        return GoogleIdentity(
            subject=subject,
            email=email,
            hosted_domain=domain,
            picture_url=picture_url_from(claims.get("picture")),
        )
