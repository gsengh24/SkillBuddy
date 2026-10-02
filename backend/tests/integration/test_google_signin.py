"""Google sign-in end to end through the API, with a fake Google and real PostgreSQL.

The fake provider (``tests/fake_oidc.py``) is served in-process; no test talks to Google.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from app.api.deps import get_google_oidc, get_otp_delivery
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.main import create_app
from app.services.auth import google as google_module
from app.services.auth.google import GoogleOidcClient
from app.services.auth.retention import purge_expired_auth_data
from tests.conftest import SettingsFactory
from tests.fake_oidc import FakeOidc
from tests.integration.conftest import CapturingDelivery, run_sql
from tests.integration.test_auth_codes import error_code, new_email, request_code

ISSUER = "http://fake-oidc.test"
CLIENT_ID = "client-123.apps.googleusercontent.com"
CLIENT_SECRET = "fake-secret-value-for-tests"
REDIRECT = "https://testserver/api/v1/auth/google/callback"
START = "/api/v1/auth/google/start"
ME = "/api/v1/auth/me"


def google_settings(make_settings: SettingsFactory, url: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": url,
        "google_signin_enabled": True,
        "google_oauth_client_id": CLIENT_ID,
        "google_oauth_client_secret": CLIENT_SECRET,
        "google_oauth_redirect_uri": REDIRECT,
        "google_oidc_authorization_url": f"{ISSUER}/authorize",
        "google_oidc_token_url": f"{ISSUER}/token",
        "google_oidc_jwks_url": f"{ISSUER}/jwks",
        "google_oidc_issuers": [ISSUER],
        "allowed_email_domains": ["thapar.edu"],
        "allowed_emails": ["owner@gmail.com"],
        "blocked_emails": ["blocked@thapar.edu"],
    }
    return make_settings(**(values | overrides))


@pytest.fixture
def fake() -> FakeOidc:
    google_module._jwks_cache.clear()
    return FakeOidc(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        workspace_domains=("thapar.edu", "evilthapar.edu"),
    )


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return google_settings(make_settings, migrated_database_url)


@asynccontextmanager
async def browser(
    settings: Settings, fake: FakeOidc, delivery: CapturingDelivery | None = None
) -> AsyncIterator[AsyncClient]:
    """A browser-like client for the app, with Google pointed at the fake provider."""
    app: FastAPI = create_app(settings)
    app.dependency_overrides[get_google_oidc] = lambda: GoogleOidcClient(
        settings, transport=ASGITransport(app=fake.app)
    )
    app.dependency_overrides[get_otp_delivery] = lambda: delivery or CapturingDelivery()
    async with LifespanManager(app) as manager:
        run_sql(
            settings.database_url.unicode_string(),
            "DELETE FROM rate_limit_counters WHERE key LIKE 'rl:%'",
        )
        transport = ASGITransport(app=manager.app, client=("198.51.100.20", 40000))
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            yield client


async def start(client: AsyncClient, *, consent: bool = True, next_path: str | None = None) -> str:
    body: dict[str, Any] = {"age_confirmed": consent, "accept_terms": consent}
    if next_path:
        body["next"] = next_path
    response = await client.post(START, json=body)
    assert response.status_code == 200, response.text
    return str(response.json()["authorization_url"])


async def at_google(fake: FakeOidc, authorization_url: str, email: str) -> str:
    """What Google does: sign the person in and redirect back. Returns the callback path."""
    async with AsyncClient(transport=ASGITransport(app=fake.app)) as google:
        response = await google.get(f"{authorization_url}&{urlencode({'login_hint': email})}")
    assert response.status_code == 302, response.text
    location = urlparse(response.headers["location"])
    assert f"https://{location.netloc}{location.path}" == REDIRECT
    return f"{location.path}?{location.query}"


async def google_sign_in(
    client: AsyncClient, fake: FakeOidc, email: str, *, consent: bool = True
) -> Response:
    callback = await at_google(fake, await start(client, consent=consent), email)
    return await client.get(callback)


def landed(response: Response) -> str:
    assert response.status_code == 303, response.text
    return response.headers["location"]


def users(url: str, email: str) -> list[dict[str, Any]]:
    return run_sql(url, "SELECT id, age_confirmed_at FROM users WHERE email = :e", e=email)


def thapar_email() -> str:
    return new_email().replace("@example.com", "@thapar.edu")


# --- availability ----------------------------------------------------------------------


async def test_methods_report_google_only_when_fully_configured(
    make_settings: SettingsFactory, migrated_database_url: str, fake: FakeOidc
) -> None:
    on = google_settings(make_settings, migrated_database_url)
    without_secret = google_settings(
        make_settings, migrated_database_url, google_oauth_client_secret=None
    )
    off = google_settings(make_settings, migrated_database_url, google_signin_enabled=False)
    for settings, expected in ((on, True), (without_secret, False), (off, False)):
        async with browser(settings, fake) as client:
            methods = (await client.get("/api/v1/auth/methods")).json()
            started = await client.post(START, json={"age_confirmed": True, "accept_terms": True})
        assert methods["email_code"] is True
        assert methods["google"] is expected
        assert methods["google_domains"] == (["thapar.edu"] if expected else [])
        assert started.status_code == (200 if expected else 404)


# --- happy paths -----------------------------------------------------------------------


async def test_first_google_sign_in_creates_the_account_and_a_session(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:
    email = thapar_email()
    async with browser(settings, fake) as client:
        callback = await at_google(fake, await start(client, next_path="/profile"), email)
        response = await client.get(callback)
        me = await client.get(ME)

    assert landed(response) == "/profile"
    assert me.status_code == 200
    assert me.json()["email"] == email
    cookies = response.headers.get_list("set-cookie")
    assert any(
        c.startswith(f"{settings.session_cookie_name}=") and "HttpOnly" in c for c in cookies
    )
    assert any(c.startswith("google_oauth_state=") and "Max-Age=0" in c for c in cookies)
    identities = run_sql(
        migrated_database_url,
        "SELECT i.provider, i.subject FROM auth_identities i JOIN users u ON u.id = i.user_id "
        "WHERE u.email = :e",
        e=email,
    )
    assert identities == [{"provider": "google", "subject": fake.subject_for(email)}]
    events = run_sql(
        migrated_database_url,
        "SELECT e.event_type, e.detail FROM auth_events e JOIN users u ON u.id = e.user_id "
        "WHERE u.email = :e",
        e=email,
    )
    assert events == [{"event_type": "signup", "detail": {"method": "google"}}]


async def test_google_signs_in_to_an_existing_email_code_account(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:
    email = thapar_email()
    user_id = run_sql(
        migrated_database_url,
        "INSERT INTO users (email, age_confirmed_at, terms_accepted_at, terms_version) "
        "VALUES (:e, now(), now(), 'v') RETURNING id",
        e=email,
    )[0]["id"]
    async with browser(settings, fake) as client:
        # Tick boxes are only needed for new accounts, as with email codes.
        first = await google_sign_in(client, fake, email, consent=False)
        second = await google_sign_in(client, fake, email, consent=False)

    assert landed(first) == "/home"
    assert landed(second) == "/home"
    assert users(migrated_database_url, email)[0]["id"] == user_id
    providers = run_sql(
        migrated_database_url,
        "SELECT provider FROM auth_identities WHERE user_id = :u",
        u=user_id,
    )
    assert providers == [{"provider": "google"}]


# --- consent and account state ---------------------------------------------------------


async def test_first_sign_in_without_the_tick_boxes_creates_nothing(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:
    email = thapar_email()
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, email, consent=False)
    assert landed(response) == "/login?error=consent_required"
    assert users(migrated_database_url, email) == []


async def test_an_account_without_age_confirmation_must_tick_it(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:
    email = thapar_email()
    run_sql(migrated_database_url, "INSERT INTO users (email) VALUES (:e)", e=email)
    async with browser(settings, fake) as client:
        refused = await google_sign_in(client, fake, email, consent=False)
        accepted = await google_sign_in(client, fake, email, consent=True)
    assert landed(refused) == "/login?error=consent_required"
    assert landed(accepted) == "/home"
    assert users(migrated_database_url, email)[0]["age_confirmed_at"] is not None


async def test_an_account_pending_deletion_cannot_sign_in(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:
    email = thapar_email()
    run_sql(
        migrated_database_url,
        "INSERT INTO users (email, status, age_confirmed_at, deleted_at, deletion_scheduled_for) "
        "VALUES (:e, 'pending_deletion', now(), now(), now() + interval '30 days')",
        e=email,
    )
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, email)
    assert landed(response) == "/login?error=account_pending_deletion"


# --- state -----------------------------------------------------------------------------


async def test_a_replayed_callback_is_refused(settings: Settings, fake: FakeOidc) -> None:
    async with browser(settings, fake) as client:
        authorization_url = await start(client)
        callback = await at_google(fake, authorization_url, thapar_email())
        first = await client.get(callback)
        client.cookies.clear()
        # Even with the binding cookie restored, a used state never works again.
        state = parse_qs(urlparse(callback).query)["state"][0]
        client.cookies.set("google_oauth_state", state, path="/api/v1/auth/google")
        replay = await client.get(callback)
    assert landed(first) == "/home"
    assert landed(replay) == "/login?error=google_state_invalid"


async def test_missing_state_or_another_browsers_callback_is_refused(
    settings: Settings, fake: FakeOidc
) -> None:
    async with browser(settings, fake) as attacker:
        callback = await at_google(fake, await start(attacker), thapar_email())
    async with browser(settings, fake) as victim:
        foreign = await victim.get(callback)  # no binding cookie: login CSRF blocked
        missing = await victim.get("/api/v1/auth/google/callback?code=abc")
        me = await victim.get(ME)
    assert landed(foreign) == "/login?error=google_state_invalid"
    assert landed(missing) == "/login?error=google_state_invalid"
    assert me.status_code == 401


async def test_cancelling_at_google(settings: Settings, fake: FakeOidc) -> None:
    async with browser(settings, fake) as client:
        authorization_url = await start(client)
        state = parse_qs(urlparse(authorization_url).query)["state"][0]
        response = await client.get(
            f"/api/v1/auth/google/callback?{urlencode({'state': state, 'error': 'access_denied'})}"
        )
    assert landed(response) == "/login?error=google_cancelled"


# --- who may sign in -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "error"),
    [
        ("asha@evilthapar.edu", "email_not_allowed"),  # look-alike domain, with its own hd
        ("blocked@thapar.edu", "email_not_allowed"),
        ("owner@gmail.com", "google_failed"),  # an exception, but not a Workspace account
        ("someone@gmail.com", "google_failed"),  # no hd claim
    ],
)
async def test_only_allowed_college_accounts_get_in(
    settings: Settings, fake: FakeOidc, migrated_database_url: str, email: str, error: str
) -> None:
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, email)
    assert landed(response) == f"/login?error={error}"
    assert users(migrated_database_url, email) == []


async def test_hd_thapar_on_a_non_thapar_email_is_refused(
    settings: Settings, fake: FakeOidc
) -> None:
    fake.tamper.claims = {"hd": "thapar.edu"}
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, "asha@gmail.com")
    assert landed(response) == "/login?error=google_failed"


@pytest.mark.parametrize(
    "tamper",
    [
        {"aud": "another-client"},
        {"iss": "https://accounts.google.com.evil.example"},
        {"exp": 1_000_000_000, "iat": 999_000_000},
        {"nonce": "not-this-attempt"},
        {"email_verified": False},
    ],
)
async def test_bad_id_tokens_are_refused_and_audited(
    settings: Settings,
    fake: FakeOidc,
    migrated_database_url: str,
    tamper: dict[str, Any],
) -> None:
    fake.tamper.claims = tamper
    email = thapar_email()
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, email)
        me = await client.get(ME)
    assert landed(response) == "/login?error=google_failed"
    assert me.status_code == 401
    assert users(migrated_database_url, email) == []
    refused = run_sql(
        migrated_database_url,
        "SELECT detail FROM auth_events WHERE event_type = 'login_refused' "
        "AND detail->>'method' = 'google' ORDER BY created_at DESC LIMIT 1",
    )
    assert refused[0]["detail"]["reason"] in {
        "wrong_audience",
        "wrong_issuer",
        "token_expired",
        "nonce_mismatch",
        "email_not_verified",
    }


async def test_a_bad_signature_is_refused(settings: Settings, fake: FakeOidc) -> None:
    fake.tamper.sign_with_foreign_key = True
    async with browser(settings, fake) as client:
        response = await google_sign_in(client, fake, thapar_email())
    assert landed(response) == "/login?error=google_failed"


async def test_email_codes_use_the_same_lists(settings: Settings, fake: FakeOidc) -> None:
    async with browser(settings, fake) as client:
        outsider = await request_code(client, new_email())
        lookalike = await request_code(client, "asha@evilthapar.edu")
        blocked = await request_code(client, "Blocked@Thapar.edu")
        student = await request_code(client, thapar_email())
        exception = await request_code(client, "owner@gmail.com")
    for refused in (outsider, lookalike, blocked):
        assert refused.status_code == 403
        assert error_code(refused) == "email_not_allowed"
    assert (student.status_code, exception.status_code) == (202, 202)


# --- limits, secrets, retention --------------------------------------------------------


async def test_starts_are_rate_limited_per_ip(
    make_settings: SettingsFactory, migrated_database_url: str, fake: FakeOidc
) -> None:
    settings = google_settings(make_settings, migrated_database_url, google_signin_limit_per_ip=2)
    body = {"age_confirmed": True, "accept_terms": True}
    async with browser(settings, fake) as client:
        codes = [(await client.post(START, json=body)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


@pytest.mark.parametrize("bad", ["//evil.example/x", "https://evil.example", "home", "/\\evil"])
async def test_next_must_be_a_path_on_this_site(
    settings: Settings, fake: FakeOidc, bad: str
) -> None:
    async with browser(settings, fake) as client:
        response = await client.post(
            START, json={"age_confirmed": True, "accept_terms": True, "next": bad}
        )
    assert response.status_code == 422


async def test_secrets_never_reach_logs_redirects_or_the_audit_log(
    settings: Settings,
    fake: FakeOidc,
    migrated_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    fake.tamper.claims = {"aud": "another-client"}
    async with browser(settings, fake) as client:
        authorization_url = await start(client)
        callback = await at_google(fake, authorization_url, thapar_email())
        caplog.clear()  # the browser's own trip to Google is not ours to log
        response = await client.get(callback)
    query = parse_qs(urlparse(callback).query)
    code, state = query["code"][0], query["state"][0]
    leaked = [CLIENT_SECRET, code, state]
    audit = str(run_sql(migrated_database_url, "SELECT detail FROM auth_events"))
    for secret in leaked:
        assert secret not in caplog.text
        assert secret not in response.headers["location"]
        assert secret not in audit
    stored = run_sql(migrated_database_url, "SELECT state_hash FROM oauth_states")
    assert all(row["state_hash"] != state for row in stored)


async def test_unused_attempts_are_purged_once_expired(
    settings: Settings, fake: FakeOidc, migrated_database_url: str
) -> None:

    async with browser(settings, fake) as client:
        await start(client)
    run_sql(
        migrated_database_url,
        "UPDATE oauth_states SET expires_at = now() - interval '1 minute'",
    )
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            result = await purge_expired_auth_data(db, settings, datetime.now(UTC))
    finally:
        await engine.dispose()
    assert result.oauth_states >= 1
    assert run_sql(migrated_database_url, "SELECT 1 FROM oauth_states") == []
