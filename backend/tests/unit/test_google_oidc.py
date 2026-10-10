"""Google ID token checks against the fake OIDC provider (no real Google, no database)."""

from __future__ import annotations

import logging
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest

from app.core.config import Settings
from app.services.auth import google as google_module
from app.services.auth.google import (
    GoogleOidcClient,
    GoogleSignInError,
    nonce_for,
    picture_url_from,
)
from app.services.auth.policy import SignInMethod, is_email_allowed
from tests.conftest import SettingsFactory
from tests.fake_oidc import FakeOidc

ISSUER = "http://fake-oidc.test"
CLIENT_ID = "client-123.apps.googleusercontent.com"
CLIENT_SECRET = "fake-secret-value-for-tests"
REDIRECT = "https://web.test/api/v1/auth/google/callback"


@pytest.fixture
def fake() -> FakeOidc:
    google_module._jwks_cache.clear()
    return FakeOidc(issuer=ISSUER, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)


@pytest.fixture
def settings(make_settings: SettingsFactory) -> Settings:
    return make_settings(
        google_signin_enabled=True,
        google_oauth_client_id=CLIENT_ID,
        google_oauth_client_secret=CLIENT_SECRET,
        google_oauth_redirect_uri=REDIRECT,
        google_oidc_authorization_url=f"{ISSUER}/authorize",
        google_oidc_token_url=f"{ISSUER}/token",
        google_oidc_jwks_url=f"{ISSUER}/jwks",
        google_oidc_issuers=[ISSUER],
        allowed_email_domains=["thapar.edu"],
    )


def client(settings: Settings, fake: FakeOidc) -> GoogleOidcClient:
    return GoogleOidcClient(settings, transport=httpx.ASGITransport(app=fake.app))


async def authorize(oidc: GoogleOidcClient, fake: FakeOidc, email: str, state: str) -> str:
    """Follow our authorization URL on the fake, as the browser would; returns the code."""
    url = oidc.authorization_url(state)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fake.app)) as http:
        response = await http.get(f"{url}&{urlencode({'login_hint': email})}")
    assert response.status_code == 302, response.text
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["state"] == [state]
    return query["code"][0]


async def sign_in(settings: Settings, fake: FakeOidc, email: str = "asha@thapar.edu") -> object:
    oidc = client(settings, fake)
    code = await authorize(oidc, fake, email, "state-1")
    return await oidc.sign_in(code, "state-1")


async def rejected(settings: Settings, fake: FakeOidc, email: str = "asha@thapar.edu") -> str:
    with pytest.raises(GoogleSignInError) as caught:
        await sign_in(settings, fake, email)
    return caught.value.reason


def test_authorization_url_asks_only_for_basic_scopes_with_pkce(
    settings: Settings, fake: FakeOidc
) -> None:
    query = parse_qs(urlparse(client(settings, fake).authorization_url("s")).query)
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["hd"] == ["thapar.edu"]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["nonce"] == [nonce_for(settings, "s")]
    assert "client_secret" not in query


async def test_happy_path(settings: Settings, fake: FakeOidc) -> None:
    identity = await sign_in(settings, fake, "Asha@Thapar.edu")
    assert identity.email == "asha@thapar.edu"  # type: ignore[attr-defined]  # GoogleIdentity
    assert identity.hosted_domain == "thapar.edu"  # type: ignore[attr-defined]  # GoogleIdentity
    assert identity.picture_url is None  # type: ignore[attr-defined]  # GoogleIdentity


async def test_the_account_picture_address_is_read(settings: Settings, fake: FakeOidc) -> None:
    picture = "https://lh3.googleusercontent.com/a/ACg8ocFakePicture_-x=s96-c"
    fake.tamper.claims = {"picture": picture}
    identity = await sign_in(settings, fake)
    assert identity.picture_url == picture  # type: ignore[attr-defined]  # GoogleIdentity


@pytest.mark.parametrize(
    "claim",
    [
        None,
        42,
        "",
        "http://lh3.googleusercontent.com/a/plain-http",
        "https://evil.example/a/picture.png",
        "https://lh3.googleusercontent.com.evil.example/a/picture",
        "https://evil.example/?https://lh3.googleusercontent.com/a/picture",
        "https://lh3.googleusercontent.com/a/with space",
        'https://lh3.googleusercontent.com/a/quote"onerror=',
        "https://lh3.googleusercontent.com/" + "a" * 300,
    ],
)
def test_a_picture_address_that_is_not_googles_is_ignored(claim: object) -> None:
    assert picture_url_from(claim) is None


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        ({"aud": "someone-elses-client"}, "wrong_audience"),
        ({"iss": "https://evil.example"}, "wrong_issuer"),
        ({"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200}, "token_expired"),
        ({"nonce": "not-the-nonce"}, "nonce_mismatch"),
        ({"email_verified": False}, "email_not_verified"),
        ({"email_verified": "true"}, "email_not_verified"),
        ({"hd": "gmail.com"}, "hosted_domain_mismatch"),
    ],
)
async def test_tampered_claims_are_rejected(
    settings: Settings, fake: FakeOidc, tamper: dict[str, object], reason: str
) -> None:
    fake.tamper.claims = tamper
    assert await rejected(settings, fake) == reason


async def test_a_token_signed_with_another_key_is_rejected(
    settings: Settings, fake: FakeOidc
) -> None:
    fake.tamper.sign_with_foreign_key = True
    assert await rejected(settings, fake) == "bad_signature"


async def test_missing_nonce_or_hd_is_rejected(settings: Settings, fake: FakeOidc) -> None:
    fake.tamper.drop_claims = {"nonce"}
    assert await rejected(settings, fake) == "nonce_mismatch"
    fake.tamper.drop_claims = {"hd"}
    assert await rejected(settings, fake) == "hosted_domain_mismatch"


async def test_hd_of_thapar_with_another_email_domain_is_rejected(
    settings: Settings, fake: FakeOidc
) -> None:
    fake.tamper.claims = {"hd": "thapar.edu"}
    assert await rejected(settings, fake, "asha@gmail.com") == "hosted_domain_mismatch"


async def test_a_consumer_account_without_hd_is_rejected(
    settings: Settings, fake: FakeOidc
) -> None:
    assert await rejected(settings, fake, "asha@gmail.com") == "hosted_domain_mismatch"


async def test_wrong_pkce_verifier_or_reused_code_fails_the_exchange(
    settings: Settings, fake: FakeOidc
) -> None:
    oidc = client(settings, fake)
    code = await authorize(oidc, fake, "asha@thapar.edu", "state-1")
    with pytest.raises(GoogleSignInError) as caught:
        await oidc.sign_in(code, "another-state")  # a different verifier and nonce
    assert caught.value.reason == "token_exchange_failed"
    code = await authorize(oidc, fake, "asha@thapar.edu", "state-2")
    await oidc.sign_in(code, "state-2")
    with pytest.raises(GoogleSignInError):
        await oidc.sign_in(code, "state-2")


async def test_keys_are_refetched_once_when_google_rotates_them(
    settings: Settings, fake: FakeOidc
) -> None:
    await sign_in(settings, fake)
    rotated = FakeOidc(issuer=ISSUER, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    await sign_in(settings, rotated)  # new kid: the cached key set is refreshed


async def test_secrets_never_reach_logs_or_errors(
    settings: Settings, fake: FakeOidc, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    oidc = client(settings, fake)
    code = await authorize(oidc, fake, "asha@thapar.edu", "state-1")
    caplog.clear()  # the browser's own request to Google is not ours to log
    fake.tamper.claims = {"aud": "other"}
    with pytest.raises(GoogleSignInError) as caught:
        await oidc.sign_in(code, "state-1")
    token = fake.id_token("asha@thapar.edu", None)
    for secret in (CLIENT_SECRET, code, token[:40], "state-1"):
        assert secret not in caplog.text
        assert secret not in str(caught.value)
        assert secret not in repr(caught.value)


@pytest.mark.parametrize(
    ("email", "method", "allowed"),
    [
        ("asha@thapar.edu", SignInMethod.GOOGLE, True),
        ("asha@evilthapar.edu", SignInMethod.GOOGLE, False),
        ("asha@thapar.edu.evil.com", SignInMethod.GOOGLE, False),
        ("asha@mail.thapar.edu", SignInMethod.GOOGLE, False),
        ("owner@gmail.com", SignInMethod.GOOGLE, False),  # exceptions are email-code only
        ("owner@gmail.com", SignInMethod.EMAIL_CODE, True),
        ("someone@gmail.com", SignInMethod.EMAIL_CODE, False),
        ("asha@thapar.edu", SignInMethod.EMAIL_CODE, True),
        ("blocked@thapar.edu", SignInMethod.GOOGLE, False),
        ("blocked@thapar.edu", SignInMethod.EMAIL_CODE, False),
    ],
)
def test_email_policy(
    make_settings: SettingsFactory, email: str, method: SignInMethod, allowed: bool
) -> None:
    settings = make_settings(
        allowed_email_domains="Thapar.edu",
        allowed_emails="Owner@Gmail.com",
        blocked_emails="blocked@thapar.edu",
    )
    assert is_email_allowed(settings, email, method) is allowed


def test_empty_lists_allow_every_email_code_but_no_google(make_settings: SettingsFactory) -> None:
    settings = make_settings()
    assert is_email_allowed(settings, "anyone@example.com", SignInMethod.EMAIL_CODE)
    assert not is_email_allowed(settings, "asha@thapar.edu", SignInMethod.GOOGLE)
    assert not settings.google_signin_available


@pytest.mark.parametrize("bad", ["@thapar.edu", "*.thapar.edu", "thapar", "thapar.edu/x"])
def test_domain_list_must_be_plain_domains(make_settings: SettingsFactory, bad: str) -> None:
    with pytest.raises(ValueError, match="ALLOWED_EMAIL_DOMAINS"):
        make_settings(allowed_email_domains=bad)


def test_deployed_environments_refuse_endpoint_overrides(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValueError, match="GOOGLE_OIDC"):
        make_settings(
            environment="staging",
            email_backend="smtp",
            embedding_backend="fastembed",
            google_oidc_token_url="http://fake-oidc:9000/token",
        )
