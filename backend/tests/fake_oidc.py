"""A fake Google OpenID Connect provider, for tests and the dev/CI stack only (ADR 0011).

It implements just what our sign-in uses: an authorize page that "signs in" whatever email
is typed (or passed as ``login_hint``), a token endpoint that checks the client secret,
redirect URI and PKCE verifier and returns an RS256 ID token, and a JWKS endpoint.

Integration tests use it in-process (``FakeOidc.app`` behind ``httpx.ASGITransport``) and
tamper with tokens through ``FakeOidc.tamper``. The compose stack runs it as a service:

    uvicorn tests.fake_oidc:app --host 0.0.0.0 --port 9000

It is never part of the production image (``tests/`` is not copied into it).
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Annotated, Any
from urllib.parse import parse_qs, urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


def _new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class Tamper:
    """Ways to make the next ID tokens wrong, for negative tests."""

    claims: dict[str, Any] = field(default_factory=dict)
    drop_claims: set[str] = field(default_factory=set)
    sign_with_foreign_key: bool = False


@dataclass
class _Grant:
    email: str
    nonce: str | None
    code_challenge: str
    redirect_uri: str


class FakeOidc:
    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
        workspace_domains: tuple[str, ...] = ("thapar.edu",),
    ) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.client_secret = client_secret
        self.workspace_domains = workspace_domains
        self.key = _new_key()
        self.kid = secrets.token_hex(8)
        self.tamper = Tamper()
        self.grants: dict[str, _Grant] = {}
        self.token_requests: list[dict[str, str]] = []
        self.app = self._build()

    def subject_for(self, email: str) -> str:
        return str(int(hashlib.sha256(email.encode()).hexdigest()[:15], 16))

    def id_token(self, email: str, nonce: str | None) -> str:
        now = int(time.time())
        domain = email.rpartition("@")[2]
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.client_id,
            "sub": self.subject_for(email),
            "email": email,
            "email_verified": True,
            "iat": now,
            "exp": now + 3600,
            "name": "Test Student",
        }
        if nonce is not None:
            claims["nonce"] = nonce
        if domain in self.workspace_domains:
            claims["hd"] = domain
        claims.update(self.tamper.claims)
        for name in self.tamper.drop_claims:
            claims.pop(name, None)
        key = _new_key() if self.tamper.sign_with_foreign_key else self.key
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": self.kid})

    def jwks(self) -> dict[str, Any]:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def _build(self) -> FastAPI:
        app = FastAPI(title="Fake Google OIDC (tests only)", docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/authorize", response_model=None)
        async def authorize(
            client_id: str,
            redirect_uri: str,
            response_type: str,
            scope: str,
            state: str,
            code_challenge: str,
            code_challenge_method: str,
            nonce: str | None = None,
            login_hint: Annotated[str | None, Query()] = None,
        ) -> HTMLResponse | RedirectResponse:
            if client_id != self.client_id:
                raise HTTPException(400, "unknown client")
            if response_type != "code" or code_challenge_method != "S256":
                raise HTTPException(400, "unsupported request")
            if set(scope.split()) != {"openid", "email", "profile"}:
                raise HTTPException(400, "unexpected scopes")
            if not login_hint:
                # The "choose an account" page: type any email and continue.
                hidden = "".join(
                    f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
                    for k, v in {
                        "client_id": client_id,
                        "redirect_uri": redirect_uri,
                        "response_type": response_type,
                        "scope": scope,
                        "state": state,
                        "code_challenge": code_challenge,
                        "code_challenge_method": code_challenge_method,
                        "nonce": nonce or "",
                    }.items()
                )
                return HTMLResponse(
                    '<!doctype html><html lang="en"><head><title>Fake Google</title></head>'
                    "<body><main><h1>Fake Google sign-in</h1>"
                    '<form method="get" action="/authorize">'
                    f"{hidden}"
                    '<label for="login_hint">Email</label>'
                    '<input id="login_hint" name="login_hint" type="email">'
                    '<button type="submit">Continue</button></form>'
                    '<a href="'
                    + html.escape(
                        f"{redirect_uri}?{urlencode({'state': state, 'error': 'access_denied'})}"
                    )
                    + '">Cancel</a>'
                    "</main></body></html>"
                )
            code = secrets.token_urlsafe(24)
            self.grants[code] = _Grant(
                email=login_hint.strip().lower(),
                nonce=nonce or None,
                code_challenge=code_challenge,
                redirect_uri=redirect_uri,
            )
            return RedirectResponse(
                f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302
            )

        @app.post("/token")
        async def token(request: Request) -> JSONResponse:
            # Parsed by hand: FastAPI's Form() would need python-multipart for one test fake.
            form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
            grant_type = form.get("grant_type", "")
            code = form.get("code", "")
            redirect_uri = form.get("redirect_uri", "")
            client_id = form.get("client_id", "")
            client_secret = form.get("client_secret", "")
            code_verifier = form.get("code_verifier", "")
            self.token_requests.append({"code": code, "redirect_uri": redirect_uri})
            grant = self.grants.pop(code, None)  # codes are single use
            if (
                grant_type != "authorization_code"
                or grant is None
                or client_id != self.client_id
                or client_secret != self.client_secret
                or redirect_uri != grant.redirect_uri
            ):
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            digest = hashlib.sha256(code_verifier.encode()).digest()
            challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
            if challenge != grant.code_challenge:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            return JSONResponse(
                {
                    "access_token": secrets.token_urlsafe(16),
                    "token_type": "Bearer",
                    "expires_in": 3599,
                    "scope": "openid email profile",
                    "id_token": self.id_token(grant.email, grant.nonce),
                }
            )

        @app.get("/jwks")
        async def jwks() -> dict[str, Any]:
            return self.jwks()

        return app


def _from_env() -> FastAPI:
    domains = os.environ.get("FAKE_OIDC_WORKSPACE_DOMAINS", "thapar.edu")
    return FakeOidc(
        issuer=os.environ.get("FAKE_OIDC_ISSUER", "http://fake-oidc:9000"),
        client_id=os.environ.get("FAKE_OIDC_CLIENT_ID", "fake-client-id"),
        client_secret=os.environ.get("FAKE_OIDC_CLIENT_SECRET", "fake-client-secret"),
        workspace_domains=tuple(d.strip() for d in domains.split(",") if d.strip()),
    ).app


def __getattr__(name: str) -> Any:
    # ``uvicorn tests.fake_oidc:app`` builds the app on first use, so importing this module in
    # tests does not generate a key pair.
    if name == "app":
        return _from_env()
    raise AttributeError(name)
