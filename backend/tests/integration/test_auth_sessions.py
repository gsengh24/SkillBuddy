"""Sessions, cookies, CSRF and account deletion, against real PostgreSQL and Valkey."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy.exc
from httpx import AsyncClient, Response

from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    AUTH_VALKEY_DB,
    CapturingDelivery,
    auth_client,
    redis_url_with_db,
    run_sql,
)
from tests.integration.test_auth_codes import error_code, new_email, request_code, sign_in, verify

ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"
LOGOUT_ALL = "/api/v1/auth/logout-all"
ACCOUNT = "/api/v1/me"


def csrf_headers(client: AsyncClient, settings: Settings) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies[settings.csrf_cookie_name]}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def set_cookie_header(response: Response, name: str) -> str:
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}="))


def session_rows(database_url: str, email: str) -> list[dict[str, object]]:
    return run_sql(
        database_url,
        "SELECT s.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE u.email = :e",
        e=email,
    )


# --- cookies ----------------------------------------------------------------------------


async def test_session_and_csrf_cookie_flags(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await sign_in(client, delivery, new_email())

    session = set_cookie_header(response, auth_settings.session_cookie_name).lower()
    csrf = set_cookie_header(response, auth_settings.csrf_cookie_name).lower()
    for attribute in ("secure", "samesite=lax", "path=/"):
        assert attribute in session
        assert attribute in csrf
    assert "httponly" in session
    assert "httponly" not in csrf
    max_age = int(re.search(r"max-age=(\d+)", session).group(1))  # type: ignore[union-attr]
    assert 90 * 86400 - 120 <= max_age <= 90 * 86400


async def test_cookie_is_not_secure_on_the_plain_http_dev_stack(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        redis_url=redis_url_with_db(AUTH_VALKEY_DB),
        session_cookie_secure=False,
    )
    async with auth_client(settings, delivery, base_url="http://testserver") as client:
        response = await sign_in(client, delivery, new_email())
        me = await client.get(ME)

    assert "secure" not in set_cookie_header(response, settings.session_cookie_name).lower()
    assert me.status_code == 200


# --- session lifetime -------------------------------------------------------------------


async def test_me_requires_a_session(auth_settings: Settings, delivery: CapturingDelivery) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await client.get(ME)

    assert response.status_code == 401
    assert error_code(response) == "authentication_required"


async def test_expired_session_is_rejected_and_removed(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        run_sql(
            migrated_database_url,
            "UPDATE sessions SET expires_at = now() - interval '1 second' "
            "WHERE user_id = (SELECT id FROM users WHERE email = :e)",
            e=email,
        )
        response = await client.get(ME)

    assert response.status_code == 401
    assert session_rows(migrated_database_url, email) == []


async def test_activity_slides_the_idle_expiry(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        run_sql(
            migrated_database_url,
            "UPDATE sessions SET created_at = now() - interval '5 days', "
            "last_seen_at = now() - interval '2 hours', expires_at = now() + interval '1 day' "
            "WHERE user_id = (SELECT id FROM users WHERE email = :e)",
            e=email,
        )
        response = await client.get(ME)

    assert response.status_code == 200
    expires_at = session_rows(migrated_database_url, email)[0]["expires_at"]
    assert isinstance(expires_at, datetime)
    assert expires_at - datetime.now(UTC) > timedelta(days=29)


async def test_sliding_never_passes_the_absolute_maximum(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        run_sql(
            migrated_database_url,
            "UPDATE sessions SET created_at = now() - interval '89 days', "
            "last_seen_at = now() - interval '2 hours', expires_at = now() + interval '1 hour' "
            "WHERE user_id = (SELECT id FROM users WHERE email = :e)",
            e=email,
        )
        response = await client.get(ME)

    assert response.status_code == 200
    expires_at = session_rows(migrated_database_url, email)[0]["expires_at"]
    assert isinstance(expires_at, datetime)
    assert expires_at - datetime.now(UTC) <= timedelta(days=1)


async def test_overlong_bearer_token_is_rejected(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await client.get(ME, headers=bearer("x" * 500))

    assert response.status_code == 401


# --- logout -----------------------------------------------------------------------------


async def test_logout_revokes_the_session_and_clears_cookies(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        token = client.cookies[auth_settings.session_cookie_name]
        response = await client.post(LOGOUT, headers=csrf_headers(client, auth_settings))
        reuse = await client.get(ME, headers=bearer(token))

    assert response.status_code == 204
    assert "max-age=0" in set_cookie_header(response, auth_settings.session_cookie_name).lower()
    assert reuse.status_code == 401
    assert session_rows(migrated_database_url, email) == []


async def test_logout_all_revokes_every_session(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as laptop:
        await sign_in(laptop, delivery, email)
        laptop_token = laptop.cookies[auth_settings.session_cookie_name]
    async with auth_client(auth_settings, delivery) as phone:
        await request_code(phone, email)
        await verify(phone, email, delivery.last_code(email), consent=False)
        phone_token = phone.cookies[auth_settings.session_cookie_name]
        response = await phone.post(LOGOUT_ALL, headers=csrf_headers(phone, auth_settings))
        laptop_after = await phone.get(ME, headers=bearer(laptop_token))
        phone_after = await phone.get(ME, headers=bearer(phone_token))

    assert response.status_code == 204
    assert laptop_after.status_code == 401
    assert phone_after.status_code == 401


# --- CSRF -------------------------------------------------------------------------------


@pytest.mark.parametrize("csrf_value", [None, "", "not-the-token"])
async def test_cookie_authenticated_writes_require_the_csrf_token(
    auth_settings: Settings, delivery: CapturingDelivery, csrf_value: str | None
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, new_email())
        headers = {} if csrf_value is None else {"X-CSRF-Token": csrf_value}
        rejected = await client.post(LOGOUT, headers=headers)
        still_signed_in = await client.get(ME)

    assert rejected.status_code == 403
    assert error_code(rejected) == "csrf_failed"
    assert still_signed_in.status_code == 200


async def test_csrf_token_from_another_session_is_rejected(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as other:
        await sign_in(other, delivery, new_email())
        foreign_token = other.cookies[auth_settings.csrf_cookie_name]
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, new_email())
        response = await client.post(LOGOUT, headers={"X-CSRF-Token": foreign_token})

    assert response.status_code == 403


async def test_bearer_clients_do_not_need_csrf(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as browser:
        await sign_in(browser, delivery, new_email())
        token = browser.cookies[auth_settings.session_cookie_name]
    async with auth_client(auth_settings, delivery) as app_client:
        me = await app_client.get(ME, headers=bearer(token))
        logout = await app_client.post(LOGOUT, headers=bearer(token))

    assert me.status_code == 200
    assert logout.status_code == 204


async def test_me_reissues_the_csrf_cookie(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, new_email())
        expected = client.cookies[auth_settings.csrf_cookie_name]
        client.cookies.delete(auth_settings.csrf_cookie_name)
        response = await client.get(ME)

    assert response.cookies[auth_settings.csrf_cookie_name] == expected


# --- account status and deletion --------------------------------------------------------


async def test_suspended_account_cannot_use_or_start_a_session(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        run_sql(
            migrated_database_url, "UPDATE users SET status = 'suspended' WHERE email = :e", e=email
        )
        me = await client.get(ME)
        await request_code(client, email)
        login = await verify(client, email, delivery.last_code(email))

    assert me.status_code == 401
    assert login.status_code == 403
    assert error_code(login) == "account_suspended"


async def test_delete_account_starts_the_grace_period_and_refuses_sign_in(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = new_email()
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, email)
        token = client.cookies[auth_settings.session_cookie_name]
        without_csrf = await client.delete(ACCOUNT)
        deleted = await client.delete(ACCOUNT, headers=csrf_headers(client, auth_settings))
        old_session = await client.get(ME, headers=bearer(token))
        requested = await request_code(client, email)
        login = await verify(client, email, delivery.last_code(email))

    assert without_csrf.status_code == 403
    assert deleted.status_code == 202
    scheduled = datetime.fromisoformat(deleted.json()["deletion_scheduled_for"])
    assert timedelta(days=29, hours=23) < scheduled - datetime.now(UTC) <= timedelta(days=30)
    assert old_session.status_code == 401
    assert requested.status_code == 202  # still indistinguishable from any other address
    assert login.status_code == 403
    assert error_code(login) == "account_pending_deletion"
    assert scheduled.date().isoformat() in login.json()["error"]["message"]

    user = run_sql(
        migrated_database_url,
        "SELECT status, deleted_at, deletion_scheduled_for FROM users WHERE email = :e",
        e=email,
    )[0]
    assert user["status"] == "pending_deletion"
    assert user["deleted_at"] is not None
    assert session_rows(migrated_database_url, email) == []


async def test_delete_account_requires_a_session(
    auth_settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        response = await client.delete(ACCOUNT)

    assert response.status_code == 401


async def test_auth_events_are_append_only(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(auth_settings, delivery) as client:
        await sign_in(client, delivery, new_email())

    with pytest.raises(sqlalchemy.exc.DBAPIError, match="append-only"):
        run_sql(migrated_database_url, "UPDATE auth_events SET ip = '0.0.0.0'")
