"""Sign-in with one-time email codes, against real PostgreSQL and Valkey."""

from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response

from app.core.config import Settings
from app.main import create_app
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    AUTH_VALKEY_DB,
    CapturingDelivery,
    auth_client,
    redis_url_with_db,
    run_sql,
)

REQUEST = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"


def new_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def request_code(client: AsyncClient, email: str) -> Response:
    return await client.post(REQUEST, json={"email": email})


async def verify(
    client: AsyncClient,
    email: str,
    code: str,
    *,
    consent: bool = True,
    age_confirmed: bool | None = None,
    accept_terms: bool | None = None,
) -> Response:
    """``consent`` sets both boxes; ``age_confirmed``/``accept_terms`` override one each."""
    return await client.post(
        VERIFY,
        json={
            "email": email,
            "code": code,
            "age_confirmed": consent if age_confirmed is None else age_confirmed,
            "accept_terms": consent if accept_terms is None else accept_terms,
        },
    )


async def sign_in(client: AsyncClient, delivery: CapturingDelivery, email: str) -> Response:
    assert (await request_code(client, email)).status_code == 202
    response = await verify(client, email, delivery.last_code(email))
    assert response.status_code == 200, response.text
    return response


def wrong_code(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def error_code(response: Response) -> Any:
    return response.json()["error"]["code"]


# --- happy path -------------------------------------------------------------------------


async def test_first_sign_in_creates_account_identity_and_session(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        requested = await request_code(client, email)
        signed_in = await verify(client, email, delivery.last_code(email))
        me = await client.get("/api/v1/auth/me")

    assert requested.status_code == 202
    assert requested.json()["expires_in_seconds"] == 600
    assert signed_in.status_code == 200
    user = signed_in.json()
    assert user["email"] == email
    assert user["terms_version"] == auth_settings.terms_version
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]

    identities = run_sql(
        migrated_database_url,
        "SELECT provider, subject FROM auth_identities WHERE user_id = :id",
        id=user["id"],
    )
    assert identities == [{"provider": "email", "subject": email}]
    events = run_sql(
        migrated_database_url,
        "SELECT event_type FROM auth_events WHERE user_id = :id",
        id=user["id"],
    )
    assert {"event_type": "signup"} in events


async def test_existing_account_signs_in_without_consent_again(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        first = await sign_in(client, delivery, email)
        await request_code(client, email)
        second = await verify(client, email, delivery.last_code(email), consent=False)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_email_is_case_insensitive(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        first = await sign_in(client, delivery, email)
        await request_code(client, email.upper())
        second = await verify(client, email.upper(), delivery.last_code(email), consent=False)

    assert second.json()["id"] == first.json()["id"]


# --- enumeration safety -----------------------------------------------------------------


async def test_request_response_is_identical_for_known_and_unknown_addresses(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    known = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, known)
        for_known = await request_code(client, known)
        for_unknown = await request_code(client, new_email())

    assert for_known.status_code == for_unknown.status_code == 202
    assert for_known.json() == for_unknown.json()
    for header in ("content-type", "content-length", "set-cookie"):
        assert for_known.headers.get(header) == for_unknown.headers.get(header)


# --- code rules -------------------------------------------------------------------------


async def test_new_account_requires_age_and_terms_and_keeps_code_usable(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        code = delivery.last_code(email)
        without_consent = await verify(client, email, code, consent=False)
        with_consent = await verify(client, email, code, consent=True)

    assert without_consent.status_code == 400
    assert error_code(without_consent) == "consent_required"
    assert with_consent.status_code == 200


async def test_sign_up_fails_without_the_age_box_and_succeeds_with_it(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        code = delivery.last_code(email)
        terms_only = await verify(client, email, code, age_confirmed=False, accept_terms=True)
        age_only = await verify(client, email, code, age_confirmed=True, accept_terms=False)
        both = await verify(client, email, code, age_confirmed=True, accept_terms=True)

    assert terms_only.status_code == age_only.status_code == 400
    assert error_code(terms_only) == error_code(age_only) == "consent_required"
    assert both.status_code == 200
    rows = run_sql(
        migrated_database_url,
        "SELECT age_confirmed_at, terms_accepted_at FROM users WHERE id = :id",
        id=both.json()["id"],
    )
    assert rows[0]["age_confirmed_at"] is not None
    assert rows[0]["terms_accepted_at"] is not None


async def test_account_without_age_confirmation_must_confirm_on_next_sign_in(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        user_id = (await sign_in(client, delivery, email)).json()["id"]
        run_sql(
            migrated_database_url,
            "UPDATE users SET age_confirmed_at = NULL WHERE id = :id",
            id=user_id,
        )
        await request_code(client, email)
        code = delivery.last_code(email)
        refused = await verify(client, email, code, consent=False)
        confirmed = await verify(client, email, code, age_confirmed=True, accept_terms=False)
        await request_code(client, email)
        later = await verify(client, email, delivery.last_code(email), consent=False)

    assert refused.status_code == 400
    assert error_code(refused) == "consent_required"
    assert confirmed.status_code == 200  # the same code still works; terms are not re-asked
    assert confirmed.json()["id"] == user_id
    rows = run_sql(
        migrated_database_url, "SELECT age_confirmed_at FROM users WHERE id = :id", id=user_id
    )
    assert rows[0]["age_confirmed_at"] is not None
    assert later.status_code == 200  # confirmed once; not asked again


async def test_wrong_code_is_rejected_and_five_attempts_lock_the_code(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        code = delivery.last_code(email)
        attempts = [await verify(client, email, wrong_code(code)) for _ in range(5)]
        correct_after_lock = await verify(client, email, code)

    assert [error_code(r) for r in attempts] == ["invalid_code"] * 4 + ["code_locked"]
    assert all(r.status_code == 400 for r in attempts)
    assert error_code(correct_after_lock) == "code_locked"
    stored = run_sql(
        migrated_database_url, "SELECT attempts FROM otp_codes WHERE email = :e", e=email
    )
    assert stored == [{"attempts": 5}]


async def test_expired_code_is_rejected(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        run_sql(
            migrated_database_url,
            "UPDATE otp_codes SET expires_at = now() - interval '1 second' WHERE email = :e",
            e=email,
        )
        response = await verify(client, email, delivery.last_code(email))

    assert response.status_code == 400
    assert error_code(response) == "invalid_code"


async def test_code_expires_after_ten_minutes(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)

    rows = run_sql(
        migrated_database_url,
        "SELECT extract(epoch FROM expires_at - created_at) AS ttl FROM otp_codes WHERE email = :e",
        e=email,
    )
    assert 599 <= float(rows[0]["ttl"]) <= 601


async def test_code_is_single_use(auth_settings: Settings, delivery: CapturingDelivery) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        code = delivery.last_code(email)
        first = await verify(client, email, code)
        reused = await verify(client, email, code)

    assert first.status_code == 200
    assert reused.status_code == 400
    assert error_code(reused) == "invalid_code"


async def test_new_request_invalidates_the_previous_code(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
        old_code = delivery.last_code(email)
        await request_code(client, email)
        new_code = delivery.last_code(email)
        with_old = await verify(client, email, old_code) if old_code != new_code else None
        with_new = await verify(client, email, new_code)

    if with_old is not None:
        assert error_code(with_old) == "invalid_code"
    assert with_new.status_code == 200


async def test_codes_are_stored_only_as_hmac(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await request_code(client, email)
    code = delivery.last_code(email)

    rows = run_sql(migrated_database_url, "SELECT * FROM otp_codes WHERE email = :e", e=email)
    assert len(rows) == 1
    assert re.fullmatch(r"[0-9a-f]{64}", rows[0]["code_hash"])
    assert code not in {str(value) for value in rows[0].values()}


# --- validation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email"},
        {"email": "a" * 250 + "@example.com"},
        {"email": "ok@example.com", "extra": "field"},
    ],
)
async def test_request_rejects_invalid_input(
    auth_settings: Settings, delivery: CapturingDelivery, payload: dict[str, str]
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await client.post(REQUEST, json=payload)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_code_must_be_six_digits(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await verify(client, new_email(), "12345")

    assert response.status_code == 422


async def test_endpoints_require_a_json_body(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await client.post(REQUEST, data={"email": new_email()})

    assert response.status_code == 415
    assert error_code(response) == "unsupported_media_type"


# --- rate limits ------------------------------------------------------------------------


async def test_code_requests_are_rate_limited_per_email(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url=redis_url_with_db(AUTH_VALKEY_DB),
        otp_request_limit_per_email=2,
    )
    email = new_email()
    async with auth_client(settings, delivery) as client:
        allowed = [await request_code(client, email) for _ in range(2)]
        limited = await request_code(client, email)
        other_address = await request_code(client, new_email())

    assert [r.status_code for r in allowed] == [202, 202]
    assert limited.status_code == 429
    assert error_code(limited) == "rate_limited"
    assert 0 < int(limited.headers["Retry-After"]) <= settings.rate_limit_window_seconds
    assert other_address.status_code == 202


async def test_code_requests_are_rate_limited_per_ip(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url=redis_url_with_db(AUTH_VALKEY_DB),
        otp_request_limit_per_ip=3,
    )
    async with auth_client(settings, delivery, client_ip="203.0.113.7") as client:
        allowed = [await request_code(client, new_email()) for _ in range(3)]
        limited = await request_code(client, new_email())

    assert [r.status_code for r in allowed] == [202] * 3
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


async def test_verification_is_rate_limited(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url=redis_url_with_db(AUTH_VALKEY_DB),
        otp_verify_limit_per_email=3,
    )
    email = new_email()
    async with auth_client(settings, delivery) as client:
        await request_code(client, email)
        code = delivery.last_code(email)
        attempts = [await verify(client, email, wrong_code(code)) for _ in range(3)]
        limited = await verify(client, email, code)

    assert all(error_code(r) == "invalid_code" for r in attempts)
    assert limited.status_code == 429
    assert error_code(limited) == "rate_limited"


async def test_rate_limiter_fails_closed_when_valkey_is_down(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url="redis://127.0.0.1:1/0",  # nothing listens on port 1
    )
    app = create_app(settings)
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app, client=("198.51.100.20", 40000))
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await request_code(client, new_email())

    assert response.status_code == 503
    assert error_code(response) == "service_unavailable"


# --- delivery and logging ---------------------------------------------------------------


async def test_code_is_queued_for_the_worker(auth_settings: Settings) -> None:
    async with auth_client(auth_settings, delivery=None) as client:
        response = await request_code(client, new_email())

    queue = await create_pool(RedisSettings.from_dsn(auth_settings.redis_url.unicode_string()))
    try:
        jobs = await queue.queued_jobs()
    finally:
        await queue.aclose()
    assert response.status_code == 202
    assert [job.function for job in jobs] == ["send_login_code"]


async def test_codes_tokens_and_addresses_are_never_logged(
    auth_settings: Settings, delivery: CapturingDelivery, capsys: pytest.CaptureFixture[str]
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        signed_in = await sign_in(client, delivery, email)
        token = client.cookies[auth_settings.session_cookie_name]

    output = capsys.readouterr().out
    assert signed_in.status_code == 200
    assert "login_code_requested" in output  # logging did happen
    assert f'"{delivery.last_code(email)}"' not in output
    assert token not in output
    assert email not in output
