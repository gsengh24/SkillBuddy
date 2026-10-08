"""Signup and access (A5), against real PostgreSQL.

The signup mode and domain lists are global, so these tests use their own fresh database:
closing signups here must never stop another test from creating accounts.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic import command
from httpx import AsyncClient, Response

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import AdminRole
from app.services.auth.retention import purge_expired_auth_data
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import Person, admin_with, email, join, two_step
from tests.integration.test_auth_codes import error_code, request_code, verify

ADMIN = "/api/v1/admin"
ACCESS = f"{ADMIN}/access"
APPLY = "/api/v1/auth/applications"
METHODS = "/api/v1/auth/methods"
REASON = "Pilot group for the autumn term."
OWNER = email("owner")


@pytest.fixture
def fresh_url() -> Iterator[str]:
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def settings(make_settings: SettingsFactory, fresh_url: str) -> Settings:
    return make_settings(
        database_url=fresh_url,
        admin_owner_emails=[OWNER],
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
        otp_request_limit_per_ip=1000,
        otp_verify_limit_per_ip=1000,
    )


async def owner_of(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Person:
    owner = await join(client, settings, delivery, OWNER)
    await two_step(client, owner)
    return owner


async def set_mode(client: AsyncClient, owner: Person, mode: str) -> Response:
    return await client.post(
        f"{ACCESS}/mode", json={"mode": mode, "reason": REASON}, headers=owner.headers
    )


async def try_join(
    client: AsyncClient, delivery: CapturingDelivery, address: str, invite: str | None = None
) -> Response:
    """Ask for a code and verify it (with an invite code, if given); cookies cleared."""
    assert (await request_code(client, address)).status_code == 202
    code = delivery.last_code(address)
    if invite is None:
        response = await verify(client, address, code)
    else:
        response = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "email": address,
                "code": code,
                "age_confirmed": True,
                "accept_terms": True,
                "invite_code": invite,
            },
        )
    client.cookies.clear()
    return response


def audit_actions(url: str) -> list[str]:
    rows = run_sql(url, "SELECT action FROM admin_audit_log WHERE action LIKE 'signup.%'")
    return sorted(row["action"] for row in rows)


async def test_by_default_signups_are_open_and_applications_closed(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        methods = (await client.get(METHODS)).json()
        joined = await try_join(client, delivery, email("new"))
        applied = await client.post(APPLY, json={"email": email("a"), "source": "friend"})

    assert methods["signup_mode"] == "open"
    assert joined.status_code == 200, joined.text
    assert applied.status_code == 409
    assert error_code(applied) == "applications_closed"


async def test_closed_refuses_new_accounts_but_existing_users_sign_in(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    existing = email("existing")
    newcomer = email("newcomer")
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        assert (await try_join(client, delivery, existing)).status_code == 200
        code = await client.post(
            f"{ACCESS}/codes", json={"max_uses": 5, "reason": REASON}, headers=owner.headers
        )
        changed = await set_mode(client, owner, "closed")
        methods = (await client.get(METHODS)).json()
        refused = await try_join(client, delivery, newcomer)
        with_code = await try_join(client, delivery, newcomer, invite=code.json()["code"])
        again = await try_join(client, delivery, existing)

    assert changed.status_code == 200, changed.text
    assert changed.json()["mode"] == "closed"
    assert methods["signup_mode"] == "closed"
    assert refused.status_code == 403
    assert error_code(refused) == "signups_closed"
    assert error_code(with_code) == "signups_closed"
    assert again.status_code == 200
    assert run_sql(fresh_url, "SELECT 1 FROM users WHERE email = :e", e=newcomer) == []
    refusals = run_sql(
        fresh_url,
        "SELECT detail->>'reason' AS reason FROM auth_events "
        "WHERE event_type = 'login_refused' AND detail->>'reason' = 'signups_closed'",
    )
    assert len(refusals) == 2
    assert audit_actions(fresh_url) == ["signup.invite_code_created", "signup.mode_changed"]


async def test_invite_codes_have_limits_expiry_and_revocation(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        one = await client.post(
            f"{ACCESS}/codes",
            json={"code": "cyn-friends", "max_uses": 1, "expires_in_days": 30, "reason": REASON},
            headers=owner.headers,
        )
        taken = await client.post(
            f"{ACCESS}/codes",
            json={"code": "CYN-FRIENDS", "max_uses": 3, "reason": REASON},
            headers=owner.headers,
        )
        expiring = await client.post(
            f"{ACCESS}/codes",
            json={"max_uses": 5, "expires_in_days": 1, "reason": REASON},
            headers=owner.headers,
        )
        revoked = await client.post(
            f"{ACCESS}/codes", json={"max_uses": 5, "reason": REASON}, headers=owner.headers
        )
        revoke = await client.post(
            f"{ACCESS}/codes/{revoked.json()['id']}/revoke",
            json={"reason": REASON},
            headers=owner.headers,
        )
        revoke_again = await client.post(
            f"{ACCESS}/codes/{revoked.json()['id']}/revoke",
            json={"reason": REASON},
            headers=owner.headers,
        )
        run_sql(
            fresh_url,
            "UPDATE invite_codes SET expires_at = now() - interval '1 minute' WHERE id = :id",
            id=expiring.json()["id"],
        )
        await set_mode(client, owner, "invite_only")

        no_code = await try_join(client, delivery, email("none"))
        wrong = await try_join(client, delivery, email("wrong"), invite="CYN-NOPE")
        first = await try_join(client, delivery, email("first"), invite=" cyn-friends ")
        second = await try_join(client, delivery, email("second"), invite="CYN-FRIENDS")
        expired = await try_join(client, delivery, email("expired"), invite=expiring.json()["code"])
        stopped = await try_join(client, delivery, email("revoked"), invite=revoked.json()["code"])
        codes = (await client.get(f"{ACCESS}/codes", headers=owner.headers)).json()

    assert one.status_code == 201, one.text
    assert one.json()["code"] == "CYN-FRIENDS"
    assert one.json()["created_by"] == OWNER
    assert taken.status_code == 409
    assert error_code(taken) == "invite_code_taken"
    assert expiring.json()["code"].startswith("CYN-")
    assert revoke.status_code == 204
    assert error_code(revoke_again) == "invite_code_revoked"
    assert error_code(no_code) == "invite_required"
    assert error_code(wrong) == "invalid_invite_code"
    assert first.status_code == 200, first.text
    assert error_code(second) == "invalid_invite_code"
    assert error_code(expired) == "invalid_invite_code"
    assert error_code(stopped) == "invalid_invite_code"
    by_code = {item["code"]: item for item in codes["items"]}
    assert by_code["CYN-FRIENDS"]["uses"] == 1
    assert by_code["CYN-FRIENDS"]["status"] == "used_up"
    assert by_code[expiring.json()["code"]]["status"] == "expired"
    assert by_code[revoked.json()["code"]]["status"] == "revoked"


async def test_a_refused_code_can_be_retried_with_an_invite(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    """The sign-in code stays usable, so the person adds an invite code and resubmits."""
    address = email("retry")
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        code = (
            await client.post(
                f"{ACCESS}/codes", json={"max_uses": 2, "reason": REASON}, headers=owner.headers
            )
        ).json()["code"]
        await set_mode(client, owner, "invite_only")
        assert (await request_code(client, address)).status_code == 202
        otp = delivery.last_code(address)
        refused = await verify(client, address, otp)
        accepted = await client.post(
            "/api/v1/auth/otp/verify",
            json={
                "email": address,
                "code": otp,
                "age_confirmed": True,
                "accept_terms": True,
                "invite_code": code,
            },
        )

    assert error_code(refused) == "invite_required"
    assert accepted.status_code == 200, accepted.text


async def test_applications_are_approved_or_rejected(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    approved, rejected, other = email("approved"), email("rejected"), email("other")
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        await set_mode(client, owner, "invite_only")
        for address in (approved, rejected):
            response = await client.post(APPLY, json={"email": address, "source": "college"})
            assert response.status_code == 202, response.text
            assert response.json() == {"status": "received"}
        # Applying twice changes nothing and answers the same.
        twice = await client.post(APPLY, json={"email": approved.upper(), "source": "friend"})
        bad_source = await client.post(APPLY, json={"email": other, "source": "radio"})
        queue = (await client.get(f"{ACCESS}/applications", headers=owner.headers)).json()
        summary = (await client.get(ACCESS, headers=owner.headers)).json()
        ids = {item["email"]: item["id"] for item in queue["items"]}
        approve = await client.post(
            f"{ACCESS}/applications/{ids[approved]}/decide",
            json={"decision": "approve", "reason": REASON},
            headers=owner.headers,
        )
        reject = await client.post(
            f"{ACCESS}/applications/{ids[rejected]}/decide",
            json={"decision": "reject", "reason": REASON},
            headers=owner.headers,
        )
        decide_again = await client.post(
            f"{ACCESS}/applications/{ids[approved]}/decide",
            json={"decision": "reject", "reason": REASON},
            headers=owner.headers,
        )
        app_code = run_sql(
            fresh_url,
            "SELECT code FROM invite_codes WHERE application_id = :id",
            id=ids[approved],
        )[0]["code"]
        # The approved application's code works only for its own address.
        borrowed = await try_join(client, delivery, other, invite=app_code)
        joined = await try_join(client, delivery, approved)
        turned_away = await try_join(client, delivery, rejected)
        codes = (await client.get(f"{ACCESS}/codes", headers=owner.headers)).json()

    assert twice.status_code == 202
    assert bad_source.status_code == 422
    assert [item["email"] for item in queue["items"]] == [approved, rejected]
    assert summary["waitlist"] == 2
    assert approve.status_code == 204, approve.text
    assert reject.status_code == 204
    assert error_code(decide_again) == "application_already_decided"
    assert error_code(borrowed) == "invalid_invite_code"
    assert joined.status_code == 200, joined.text
    assert error_code(turned_away) == "invite_required"
    # One-use application codes are not in the shareable list.
    assert codes["items"] == []
    jobs = run_sql(fresh_url, "SELECT payload FROM jobs WHERE kind = 'send_invite'")
    assert len(jobs) == 1
    assert set(jobs[0]["payload"]) == {"invite_code_id"}
    assert audit_actions(fresh_url) == [
        "signup.application_approved",
        "signup.application_rejected",
        "signup.mode_changed",
    ]


async def test_invite_next_ten_approves_the_oldest(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        await set_mode(client, owner, "invite_only")
        addresses = [email(f"wait{n}") for n in range(12)]
        for address in addresses:
            await client.post(APPLY, json={"email": address, "source": "search"})
        invited = await client.post(
            f"{ACCESS}/applications/invite-next", json={"reason": REASON}, headers=owner.headers
        )
        left = (await client.get(f"{ACCESS}/applications", headers=owner.headers)).json()
        summary = (await client.get(ACCESS, headers=owner.headers)).json()

    assert invited.json() == {"invited": 10}
    assert [item["email"] for item in left["items"]] == addresses[10:]
    assert summary["waitlist"] == 2
    assert audit_actions(fresh_url).count("signup.application_approved") == 10
    assert len(run_sql(fresh_url, "SELECT 1 FROM jobs WHERE kind = 'send_invite'")) == 10


async def test_blocked_and_allowed_domains_apply_to_new_accounts_only(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async def add(client: AsyncClient, owner: Person, kind: str, domain: str) -> Response:
        return await client.post(
            f"{ACCESS}/domains/{kind}",
            json={"domain": domain, "reason": REASON},
            headers=owner.headers,
        )

    async def remove(client: AsyncClient, owner: Person, kind: str, domain: str) -> Response:
        return await client.post(
            f"{ACCESS}/domains/{kind}/remove",
            json={"domain": domain, "reason": REASON},
            headers=owner.headers,
        )

    existing = "early@blocked.example"
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        assert (await try_join(client, delivery, existing)).status_code == 200
        blocked = await add(client, owner, "blocked", "@Blocked.Example ")
        duplicate = await add(client, owner, "blocked", "blocked.example")
        invalid = await add(client, owner, "allowed", "not a domain")
        new_blocked = await try_join(client, delivery, "late@blocked.example")
        still_in = await try_join(client, delivery, existing)
        allowed = await add(client, owner, "allowed", "allowed.example")
        outside = await try_join(client, delivery, "someone@elsewhere.example")
        inside = await try_join(client, delivery, "someone@allowed.example")
        summary = (await client.get(ACCESS, headers=owner.headers)).json()
        removed = await remove(client, owner, "allowed", "allowed.example")
        missing = await remove(client, owner, "allowed", "allowed.example")
        anywhere = await try_join(client, delivery, "again@elsewhere.example")

    assert blocked.status_code == 201, blocked.text
    assert blocked.json() == {"domain": "blocked.example"}
    assert error_code(duplicate) == "domain_already_listed"
    assert error_code(invalid) == "invalid_domain"
    assert error_code(new_blocked) == "email_not_allowed"
    assert still_in.status_code == 200
    assert allowed.status_code == 201
    assert error_code(outside) == "email_not_allowed"
    assert inside.status_code == 200, inside.text
    assert summary["allowed_domains"] == ["allowed.example"]
    assert summary["blocked_domains"] == ["blocked.example"]
    assert removed.status_code == 204
    assert error_code(missing) == "domain_not_listed"
    assert anywhere.status_code == 200
    assert audit_actions(fresh_url) == [
        "signup.domain_allowed_added",
        "signup.domain_allowed_removed",
        "signup.domain_blocked_added",
    ]


async def test_changes_need_a_reason_and_only_owners_and_admins_manage_access(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        people = {
            role: await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        }
        no_reason = await client.post(
            f"{ACCESS}/mode", json={"mode": "closed", "reason": "short"}, headers=owner.headers
        )
        views = {
            role.value: (await client.get(ACCESS, headers=person.headers)).status_code
            for role, person in people.items()
        }
        admin_change = await set_mode(client, people[AdminRole.ADMIN], "invite_only")
        moderator_change = await set_mode(client, people[AdminRole.MODERATOR], "closed")
        mode = (await client.get(METHODS)).json()["signup_mode"]

    assert no_reason.status_code == 422
    assert views == {"admin": 200, "moderator": 403, "readonly": 403}
    assert admin_change.status_code == 200
    assert moderator_change.status_code == 403
    assert mode == "invite_only"
    rows: list[dict[str, Any]] = run_sql(
        fresh_url,
        "SELECT actor_role, target_id, reason FROM admin_audit_log "
        "WHERE action = 'signup.mode_changed'",
    )
    assert rows == [{"actor_role": "admin", "target_id": "invite_only", "reason": REASON}]


async def test_old_applications_and_ended_codes_are_purged(
    settings: Settings, fresh_url: str
) -> None:
    run_sql(
        fresh_url,
        """INSERT INTO signup_applications (email, source, status, created_at, decided_at)
           VALUES ('old-decided@example.com', 'friend', 'rejected', now() - interval '200 days',
                   now() - interval '91 days'),
                  ('new-decided@example.com', 'friend', 'approved', now() - interval '20 days',
                   now() - interval '10 days'),
                  ('old-pending@example.com', 'friend', 'pending', now() - interval '181 days',
                   NULL),
                  ('new-pending@example.com', 'friend', 'pending', now() - interval '30 days',
                   NULL)""",
    )
    run_sql(
        fresh_url,
        """INSERT INTO invite_codes (code, max_uses, revoked_at, expires_at) VALUES
           ('CYN-GONE1', 5, now() - interval '181 days', NULL),
           ('CYN-GONE2', 5, NULL, now() - interval '181 days'),
           ('CYN-KEPT1', 5, now() - interval '10 days', NULL),
           ('CYN-KEPT2', 5, NULL, NULL)""",
    )
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            result = await purge_expired_auth_data(db, settings, datetime.now(UTC))
            again = await purge_expired_auth_data(
                db, settings, datetime.now(UTC) + timedelta(seconds=1)
            )
    finally:
        await engine.dispose()

    assert (result.signup_applications, result.invite_codes) == (2, 2)
    assert (again.signup_applications, again.invite_codes) == (0, 0)
    left = run_sql(fresh_url, "SELECT email FROM signup_applications ORDER BY email")
    assert [row["email"] for row in left] == ["new-decided@example.com", "new-pending@example.com"]
    codes = run_sql(fresh_url, "SELECT code FROM invite_codes ORDER BY code")
    assert [row["code"] for row in codes] == ["CYN-KEPT1", "CYN-KEPT2"]
