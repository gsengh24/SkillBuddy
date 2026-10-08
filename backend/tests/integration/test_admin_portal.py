"""The admin portal's security core (ADR 0015), against real PostgreSQL.

Every route under /api/v1/admin is found from the app itself, so a new route is covered
without editing this file: anonymous gets 401, a normal user 403, and each role 403
wherever the permission table says no.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pyotp
import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy.exc import DBAPIError

from app.api.admin_deps import PERMISSION_OF
from app.core.config import Settings
from app.main import create_app
from app.models import AdminRole
from app.services.admin.permissions import Permission, allows
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code, sign_in
from tests.integration.test_auth_sessions import bearer

ADMIN = "/api/v1/admin"
TEAM = f"{ADMIN}/team"
ADMIN_TOKEN = "test-admin-token-with-more-than-32-characters"
TICK_TOKEN = "test-tick-token-with-more-than-32-characters"
REASON = "Helps with the reports queue this term."


def email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def owner_email() -> str:
    return email("owner")


@pytest.fixture
def settings(
    make_settings: SettingsFactory, migrated_database_url: str, owner_email: str
) -> Settings:
    return make_settings(
        database_url=migrated_database_url,
        admin_owner_emails=[owner_email],
        admin_api_token=ADMIN_TOKEN,
        jobs_tick_token=TICK_TOKEN,
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
    )


@dataclass
class Person:
    email: str
    token: str
    admin_token: str | None = None
    recovery_codes: list[str] | None = None

    @property
    def headers(self) -> dict[str, str]:
        extra = {"X-Admin-Session": self.admin_token} if self.admin_token else {}
        return bearer(self.token) | extra


async def join(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, address: str
) -> Person:
    await sign_in(client, delivery, address)
    token = client.cookies[settings.session_cookie_name]
    client.cookies.clear()
    return Person(email=address, token=token)


async def two_step(client: AsyncClient, person: Person) -> pyotp.TOTP:
    """Set up and confirm two-step login; the person gets an admin session."""
    setup = await client.post(f"{ADMIN}/two-step/setup", headers=person.headers)
    assert setup.status_code == 200, setup.text
    totp = pyotp.TOTP(setup.json()["secret"])
    confirm = await client.post(
        f"{ADMIN}/two-step/confirm", json={"code": totp.now()}, headers=person.headers
    )
    assert confirm.status_code == 200, confirm.text
    person.admin_token = confirm.cookies["admin_session"]
    person.recovery_codes = confirm.json()["recovery_codes"]
    client.cookies.clear()
    return totp


async def admin_with(
    client: AsyncClient,
    settings: Settings,
    delivery: CapturingDelivery,
    owner: Person,
    role: AdminRole,
) -> Person:
    person = await join(client, settings, delivery, email(role.value))
    granted = await client.post(
        TEAM,
        json={"email": person.email, "role": role.value, "reason": REASON},
        headers=owner.headers,
    )
    assert granted.status_code == 201, granted.text
    await two_step(client, person)
    return person


# --- every admin route ---------------------------------------------------------------------


def _flat_routes(routes: list[Any]) -> Iterator[Any]:
    """Every endpoint, with its full path. FastAPI 0.142 keeps included routers nested
    (their effective routes carry the full path and the dependency tree)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()


def _admin_routes(settings: Settings) -> Iterator[tuple[str, str, Permission | None]]:
    def permission(dependant: Dependant) -> Permission | None:
        if dependant.call in PERMISSION_OF:
            return PERMISSION_OF[dependant.call]
        for sub in dependant.dependencies:
            found = permission(sub)
            if found is not None:
                return found
        return None

    for route in _flat_routes(create_app(settings).routes):
        if route.path.startswith(ADMIN):
            for method in sorted(route.methods or ()):
                yield method, route.path, permission(route.dependant)


@pytest.fixture
def routes(settings: Settings) -> list[tuple[str, str, Permission | None]]:
    return list(_admin_routes(settings))


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


async def call(client: AsyncClient, method: str, path: str, headers: dict[str, str]) -> Any:
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return await client.request(method, concrete(path), headers=headers, json={})
    return await client.request(method, concrete(path), headers=headers)


def test_the_route_list_is_not_empty(
    settings: Settings, routes: list[tuple[str, str, Permission | None]]
) -> None:
    paths = {path for _, path, _ in routes}
    # Nothing in the public API description is missing from the list these tests walk.
    schema_paths = {p for p in create_app(settings).openapi()["paths"] if p.startswith(ADMIN)}
    assert schema_paths <= paths
    assert {f"{ADMIN}/me", f"{ADMIN}/audit", f"{ADMIN}/jobs/tick", f"{ADMIN}/storage"} <= paths
    # Only the two-step routes may skip a permission (they work before the second step).
    assert {path for _, path, p in routes if p is None} == {
        f"{ADMIN}/two-step",
        f"{ADMIN}/two-step/setup",
        f"{ADMIN}/two-step/confirm",
        f"{ADMIN}/two-step/verify",
    }


async def test_every_admin_route_refuses_anonymous_and_normal_users(
    settings: Settings,
    delivery: CapturingDelivery,
    routes: list[tuple[str, str, Permission | None]],
) -> None:
    async with auth_client(settings, delivery) as client:
        normal = await join(client, settings, delivery, email("normal"))
        anonymous = [(m, p, (await call(client, m, p, {})).status_code) for m, p, _ in routes]
        users = [
            (m, p, (await call(client, m, p, normal.headers)).status_code) for m, p, _ in routes
        ]

    assert [r for r in anonymous if r[2] != 401] == []
    assert [r for r in users if r[2] != 403] == []


async def test_each_role_is_held_to_the_permission_table(
    settings: Settings,
    delivery: CapturingDelivery,
    owner_email: str,
    routes: list[tuple[str, str, Permission | None]],
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)
        people = {
            role: await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        }
        people[AdminRole.OWNER] = owner
        wrong: list[tuple[str, str, str, int]] = []
        for role, person in people.items():
            for method, path, permission in routes:
                if permission is None or (method != "GET" and allows(role, permission)):
                    continue  # writes are only tried where they must be refused
                status = (await call(client, method, path, person.headers)).status_code
                refused = status in {401, 403}
                if allows(role, permission) == refused:
                    wrong.append((role.value, method, path, status))

    assert wrong == []


# --- the second step -----------------------------------------------------------------------


async def test_two_step_login_with_codes_and_recovery_codes(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        before = await client.get(f"{ADMIN}/two-step", headers=owner.headers)
        no_session = await client.get(f"{ADMIN}/me", headers=owner.headers)
        early = await client.post(
            f"{ADMIN}/two-step/verify", json={"code": "123456"}, headers=owner.headers
        )
        totp = await two_step(client, owner)
        setup_again = await client.post(f"{ADMIN}/two-step/setup", headers=owner.headers)
        me = await client.get(f"{ADMIN}/me", headers=owner.headers)

        signed_out = Person(email=owner.email, token=owner.token)
        replay = await client.post(
            f"{ADMIN}/two-step/verify", json={"code": totp.now()}, headers=signed_out.headers
        )
        wrong = await client.post(
            f"{ADMIN}/two-step/verify", json={"code": "000000"}, headers=signed_out.headers
        )
        assert owner.recovery_codes
        recovery = owner.recovery_codes[0]
        with_recovery = await client.post(
            f"{ADMIN}/two-step/verify", json={"code": recovery}, headers=signed_out.headers
        )
        recovery_twice = await client.post(
            f"{ADMIN}/two-step/verify", json={"code": recovery}, headers=signed_out.headers
        )
        new_session = Person(
            email=owner.email, token=owner.token, admin_token=with_recovery.cookies["admin_session"]
        )
        me_again = await client.get(f"{ADMIN}/me", headers=new_session.headers)
        out = await client.post(f"{ADMIN}/sign-out", json={}, headers=new_session.headers)
        after_out = await client.get(f"{ADMIN}/me", headers=new_session.headers)
        normal_still = await client.get("/api/v1/auth/me", headers=bearer(owner.token))

    assert before.json() == {"role": "owner", "two_step_enabled": False}
    assert error_code(no_session) == "admin_two_step_required"
    assert error_code(early) == "two_step_not_set_up"
    assert error_code(setup_again) == "two_step_already_enabled"
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert "manage_admins" in me.json()["permissions"]
    assert len(owner.recovery_codes) == 10
    # The code used to turn it on can't open a second session.
    assert error_code(replay) == "invalid_two_step_code"
    assert error_code(wrong) == "invalid_two_step_code"
    assert with_recovery.status_code == 200
    assert error_code(recovery_twice) == "invalid_two_step_code"
    assert me_again.status_code == 200
    assert out.status_code == 204
    assert error_code(after_out) == "admin_two_step_required"
    assert normal_still.status_code == 200
    # Recovery codes and the secret are stored only as hashes / encrypted.
    stored = run_sql(
        settings.database_url.unicode_string(),
        "SELECT a.totp_secret, array_agg(r.code_hash) AS hashes FROM admin_accounts a "
        "JOIN users u ON u.id = a.user_id JOIN admin_recovery_codes r ON r.user_id = a.user_id "
        "WHERE u.email = :e GROUP BY a.totp_secret",
        e=owner.email,
    )[0]
    assert totp.secret not in stored["totp_secret"]
    assert recovery not in stored["hashes"]


async def test_two_step_attempts_are_rate_limited(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    delivery: CapturingDelivery,
    owner_email: str,
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        admin_owner_emails=[owner_email],
        admin_two_step_attempts=3,
    )
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)
        guesser = Person(email=owner.email, token=owner.token)
        statuses = [
            (
                await client.post(
                    f"{ADMIN}/two-step/verify", json={"code": "111111"}, headers=guesser.headers
                )
            ).status_code
            for _ in range(3)
        ]

    # The confirm call counted as the first attempt in the window.
    assert statuses == [400, 400, 429]


async def test_no_one_is_an_admin_without_admin_owner_emails(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(database_url=migrated_database_url)
    assert settings.admin_owner_emails == []
    async with auth_client(settings, delivery) as client:
        person = await join(client, settings, delivery, email("hopeful"))
        status = await client.get(f"{ADMIN}/two-step", headers=person.headers)
    assert error_code(status) == "not_admin"


# --- admin sessions ------------------------------------------------------------------------


async def test_the_admin_session_ends_after_30_idle_minutes_and_12_hours(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    url = settings.database_url.unicode_string()
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)
        user_id = (await client.get(f"{ADMIN}/me", headers=owner.headers)).json()["user_id"]

        # Used 2 minutes ago: still alive, and the idle expiry moves on.
        run_sql(
            url,
            "UPDATE admin_sessions SET last_seen_at = now() - interval '2 minutes', "
            "expires_at = now() + interval '5 minutes' WHERE user_id = :u",
            u=user_id,
        )
        alive = await client.get(f"{ADMIN}/me", headers=owner.headers)
        slid = run_sql(
            url,
            "SELECT expires_at > now() + interval '29 minutes' AS moved FROM admin_sessions "
            "WHERE user_id = :u",
            u=user_id,
        )[0]["moved"]

        # 31 minutes without use: gone.
        run_sql(
            url,
            "UPDATE admin_sessions SET last_seen_at = now() - interval '31 minutes', "
            "expires_at = now() - interval '1 minute' WHERE user_id = :u",
            u=user_id,
        )
        idle = await client.get(f"{ADMIN}/me", headers=owner.headers)

        # A fresh one, but started 13 hours ago: gone too, whatever its idle expiry says.
        signed_out = Person(email=owner.email, token=owner.token)
        assert owner.recovery_codes
        again = await client.post(
            f"{ADMIN}/two-step/verify",
            json={"code": owner.recovery_codes[1]},
            headers=signed_out.headers,
        )
        owner.admin_token = again.cookies["admin_session"]
        run_sql(
            url,
            "UPDATE admin_sessions SET created_at = now() - interval '13 hours' WHERE user_id = :u",
            u=user_id,
        )
        too_old = await client.get(f"{ADMIN}/me", headers=owner.headers)

    assert alive.status_code == 200
    assert slid is True
    assert error_code(idle) == "admin_two_step_required"
    assert error_code(too_old) == "admin_two_step_required"


# --- the audit log -------------------------------------------------------------------------


async def test_the_audit_log_is_append_only(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    url = settings.database_url.unicode_string()
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)

    for statement in (
        "UPDATE admin_audit_log SET reason = 'changed afterwards' WHERE true",
        "DELETE FROM admin_audit_log WHERE true",
        "TRUNCATE admin_audit_log",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            run_sql(url, statement)
    assert run_sql(url, "SELECT count(*) AS n FROM admin_audit_log")[0]["n"] >= 2


async def test_team_changes_need_a_reason_and_are_audited_with_keyset_paging(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)
        helper = await join(client, settings, delivery, email("helper"))
        short = await client.post(
            TEAM,
            json={"email": helper.email, "role": "moderator", "reason": "ok"},
            headers=owner.headers,
        )
        unknown = await client.post(
            TEAM,
            json={"email": email("nobody"), "role": "moderator", "reason": REASON},
            headers=owner.headers,
        )
        make_owner = await client.post(
            TEAM,
            json={"email": helper.email, "role": "owner", "reason": REASON},
            headers=owner.headers,
        )
        change_owner = await client.post(
            TEAM,
            json={"email": owner.email, "role": "readonly", "reason": REASON},
            headers=owner.headers,
        )
        granted = await client.post(
            TEAM,
            json={"email": helper.email, "role": "moderator", "reason": REASON},
            headers=owner.headers,
        )
        team = (await client.get(TEAM, headers=owner.headers)).json()["items"]
        helper_id = granted.json()["user_id"]
        removed = await client.post(
            f"{TEAM}/{helper_id}/remove",
            json={"reason": "Finished helping this term."},
            headers=owner.headers,
        )
        removed_again = await client.post(
            f"{TEAM}/{helper_id}/remove",
            json={"reason": "Finished helping this term."},
            headers=owner.headers,
        )
        # Other tests share the log, so page through this owner's entries only.
        owner_id = (await client.get(f"{ADMIN}/me", headers=owner.headers)).json()["user_id"]
        first = (
            await client.get(
                f"{ADMIN}/audit",
                params={"limit": 2, "actor_id": owner_id},
                headers=owner.headers,
            )
        ).json()
        second = (
            await client.get(
                f"{ADMIN}/audit",
                params={"limit": 2, "cursor": first["next_cursor"], "actor_id": owner_id},
                headers=owner.headers,
            )
        ).json()
        filtered = (
            await client.get(
                f"{ADMIN}/audit", params={"target_id": helper_id}, headers=owner.headers
            )
        ).json()
        too_many = await client.get(f"{ADMIN}/audit", params={"limit": 51}, headers=owner.headers)

    assert short.status_code == 422
    assert error_code(unknown) == "user_not_found"
    assert make_owner.status_code == 422  # owner isn't a role you can give
    assert error_code(change_owner) == "cannot_change_owner"
    assert granted.status_code == 201
    mine = [m for m in team if m["email"] in {owner.email, helper.email}]
    assert [(m["email"], m["role"], m["from_environment"]) for m in mine] == [
        (owner.email, "owner", True),
        (helper.email, "moderator", False),
    ]
    assert removed.status_code == 204
    assert error_code(removed_again) == "admin_not_found"
    assert [item["action"] for item in first["items"]] == [
        "admin.role_removed",
        "admin.role_granted.moderator",
    ]
    assert first["items"][0]["reason"] == "Finished helping this term."
    # Turning two-step on and the first sign-in share one transaction (one timestamp).
    assert {item["action"] for item in second["items"]} == {
        "admin.two_step_enabled",
        "admin.signed_in",
    }
    assert {item["id"] for item in first["items"]}.isdisjoint(
        item["id"] for item in second["items"]
    )
    assert [item["action"] for item in filtered["items"]] == [
        "admin.role_removed",
        "admin.role_granted.moderator",
    ]
    assert too_many.status_code == 422


async def test_the_permission_table_matches_the_reference(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, owner_email)
        await two_step(client, owner)
        table = (await client.get(f"{ADMIN}/permissions", headers=owner.headers)).json()

    rows = {row["label"]: row["roles"] for row in table["rows"]}
    assert rows == {
        "View dashboards": ["owner", "admin", "moderator", "readonly"],
        "View users": ["owner", "admin", "moderator", "readonly"],
        "Suspend / ban users": ["owner", "admin", "moderator"],
        "Handle reports": ["owner", "admin", "moderator"],
        "Read messages attached to reports": ["owner", "admin", "moderator"],
        "Signup and invites": ["owner", "admin"],
        "Settings and switches": ["owner", "admin"],
        "AI and matching": ["owner", "admin"],
        "Manage admins": ["owner"],
        "Delete users and data": ["owner", "admin"],
    }
