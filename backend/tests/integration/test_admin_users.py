"""The admin Users page (A2), against real PostgreSQL: list, search and filters, the detail,
and every account action with its one audit entry."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.models import AdminRole
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_admin_portal import Person, admin_with, email, join, two_step
from tests.integration.test_auth_codes import error_code, request_code, verify
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_chat import connect
from tests.integration.test_profile_api import body as profile_body

USERS = "/api/v1/admin/users"
REASON = {"reason": "Reported for spam several times this week."}


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
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
        ai_llm_enabled=False,
        # The suspend and ban test signs the same person in several times.
        otp_request_limit_per_email=10,
    )


async def owner_of(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, address: str
) -> Person:
    owner = await join(client, settings, delivery, address)
    await two_step(client, owner)
    return owner


async def member(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, name: str, **profile: Any
) -> tuple[Person, str]:
    person = await join(client, settings, delivery, email(name.lower()))
    await client.put(
        "/api/v1/me/profile",
        json=profile_body(display_name=name),
        headers=bearer(person.token),
    )
    if profile:
        await client.patch("/api/v1/me/profile", json=profile, headers=bearer(person.token))
    me = (await client.get("/api/v1/auth/me", headers=bearer(person.token))).json()
    return person, me["id"]


def audit_count(settings: Settings, user_id: str, action: str) -> int:
    return int(
        run_sql(
            settings.database_url.unicode_string(),
            "SELECT count(*) AS n FROM admin_audit_log WHERE target_id = :t AND action = :a",
            t=user_id,
            a=action,
        )[0]["n"]
    )


async def test_search_filters_paging_and_a_cached_total(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    url = settings.database_url.unicode_string()
    tag = uuid.uuid4().hex[:8]
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        _, zara = await member(client, settings, delivery, f"Zara{tag}", intents=["mentor"])
        _, omar = await member(client, settings, delivery, f"Omar{tag}")
        _, ira = await member(client, settings, delivery, f"Ira{tag}", intents=["mentor"])
        run_sql(
            url,
            "INSERT INTO reports (reporter_id, reported_id, target, target_id, reason, snapshot) "
            "VALUES (NULL, :u, 'profile', :u, 'spam', '[]'::jsonb)",
            u=omar,
        )
        by_name = (
            await client.get(USERS, params={"q": f"zara{tag}"}, headers=owner.headers)
        ).json()
        by_tag = (await client.get(USERS, params={"q": tag}, headers=owner.headers)).json()
        mentors = (
            await client.get(USERS, params={"q": tag, "intent": "mentor"}, headers=owner.headers)
        ).json()
        flagged = (
            await client.get(USERS, params={"q": tag, "flagged": True}, headers=owner.headers)
        ).json()
        first = (
            await client.get(USERS, params={"q": tag, "limit": 2}, headers=owner.headers)
        ).json()
        second = (
            await client.get(
                USERS,
                params={"q": tag, "limit": 2, "cursor": first["next_cursor"]},
                headers=owner.headers,
            )
        ).json()
        wildcard = (await client.get(USERS, params={"q": "%"}, headers=owner.headers)).json()
        too_many = await client.get(USERS, params={"limit": 51}, headers=owner.headers)

    assert [row["id"] for row in by_name["items"]] == [zara]
    assert by_name["items"][0]["name"] == f"Zara{tag}"
    assert {row["id"] for row in by_tag["items"]} == {zara, omar, ira}
    assert by_tag["total"] == 3
    assert {row["id"] for row in mentors["items"]} == {zara, ira}
    assert [row["id"] for row in flagged["items"]] == [omar]
    assert flagged["items"][0]["flagged"] is True
    # Newest first, two then one.
    assert [row["id"] for row in first["items"]] == [ira, omar]
    assert [row["id"] for row in second["items"]] == [zara]
    assert second["next_cursor"] is None
    # "%" is a character to search for, not a wildcard.
    assert wildcard["items"] == []
    assert too_many.status_code == 422


async def test_detail_shows_profile_counts_timeline_and_notes(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        _, mina = await member(client, settings, delivery, "Mina", headline="Builds bots")
        note = await client.post(
            f"{USERS}/{mina}/notes",
            json={"body": "Asked about the rules twice."},
            headers=owner.headers,
        )
        found = (await client.get(f"{USERS}/{mina}", headers=owner.headers)).json()
        missing = await client.get(f"{USERS}/{uuid.uuid4()}", headers=owner.headers)

    assert note.status_code == 201
    assert found["profile"]["display_name"] == "Mina"
    assert found["profile"]["headline"] == "Builds bots"
    assert found["sign_in_methods"] == ["email"]
    assert set(found["counts"]) == {
        "requests",
        "matched_as_candidate",
        "connections",
        "reports_against",
        "open_reports_against",
    }
    assert [n["body"] for n in found["notes"]] == ["Asked about the rules twice."]
    events = [item["event"] for item in found["timeline"]]
    assert "user.note_added" in events
    assert "account.signup" in events
    assert events[-1] == "account.created"
    assert error_code(missing) == "user_not_found"
    assert audit_count(settings, mina, "user.note_added") == 1


async def test_suspend_ban_and_their_reversals_each_write_one_audit_entry(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    url = settings.database_url.unicode_string()
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        person, user_id = await member(client, settings, delivery, "Sam")
        address = (await client.get("/api/v1/auth/me", headers=bearer(person.token))).json()[
            "email"
        ]

        suspended = await client.post(
            f"{USERS}/{user_id}/suspend", json=REASON, headers=owner.headers
        )
        session_after = await client.get("/api/v1/auth/me", headers=bearer(person.token))
        await request_code(client, address)
        refused = await verify(client, address, delivery.last_code(address), consent=False)
        again = await client.post(f"{USERS}/{user_id}/suspend", json=REASON, headers=owner.headers)
        status_row = run_sql(
            url,
            "SELECT status, suspended_until > now() + interval '6 days' AS week FROM users "
            "WHERE id = :u",
            u=user_id,
        )[0]

        # When the 7 days are up, signing in lifts it.
        run_sql(
            url,
            "UPDATE users SET suspended_until = now() - interval '1 minute' WHERE id = :u",
            u=user_id,
        )
        await request_code(client, address)
        lifted = await verify(client, address, delivery.last_code(address), consent=False)
        client.cookies.clear()

        banned = await client.post(f"{USERS}/{user_id}/ban", json=REASON, headers=owner.headers)
        await request_code(client, address)
        refused_ban = await verify(client, address, delivery.last_code(address), consent=False)
        unbanned = await client.post(f"{USERS}/{user_id}/unban", json=REASON, headers=owner.headers)
        suspended_again = await client.post(
            f"{USERS}/{user_id}/suspend", json=REASON, headers=owner.headers
        )
        unsuspended = await client.post(
            f"{USERS}/{user_id}/unsuspend", json=REASON, headers=owner.headers
        )
        short = await client.post(
            f"{USERS}/{user_id}/ban", json={"reason": "spam"}, headers=owner.headers
        )

    assert suspended.status_code == 204
    assert session_after.status_code == 401
    assert error_code(refused) == "account_suspended"
    assert error_code(again) == "invalid_status_change"
    assert status_row == {"status": "suspended", "week": True}
    assert lifted.status_code == 200
    assert banned.status_code == 204
    assert error_code(refused_ban) == "account_banned"
    assert (unbanned.status_code, suspended_again.status_code, unsuspended.status_code) == (
        204,
        204,
        204,
    )
    assert short.status_code == 422
    assert (
        run_sql(url, "SELECT status FROM users WHERE id = :u", u=user_id)[0]["status"] == "active"
    )
    assert audit_count(settings, user_id, "user.suspend") == 2
    assert audit_count(settings, user_id, "user.ban") == 1
    assert audit_count(settings, user_id, "user.unban") == 1
    assert audit_count(settings, user_id, "user.unsuspend") == 1


async def test_sign_out_clear_bio_and_schedule_deletion(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    url = settings.database_url.unicode_string()
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        person, user_id = await member(client, settings, delivery, "Lee")
        out = await client.post(f"{USERS}/{user_id}/sign-out", json=REASON, headers=owner.headers)
        after_out = await client.get("/api/v1/auth/me", headers=bearer(person.token))
        cleared = await client.post(
            f"{USERS}/{user_id}/clear-bio", json=REASON, headers=owner.headers
        )
        deleted = await client.post(
            f"{USERS}/{user_id}/schedule-deletion", json=REASON, headers=owner.headers
        )
        twice = await client.post(
            f"{USERS}/{user_id}/schedule-deletion", json=REASON, headers=owner.headers
        )
        no_profile_person = await join(client, settings, delivery, email("bare"))
        bare = (
            await client.get("/api/v1/auth/me", headers=bearer(no_profile_person.token))
        ).json()["id"]
        no_profile = await client.post(
            f"{USERS}/{bare}/clear-bio", json=REASON, headers=owner.headers
        )

    assert (out.status_code, after_out.status_code) == (204, 401)
    assert cleared.status_code == 204
    profile = run_sql(
        url, "SELECT raw_about_text, parse_status FROM profiles WHERE user_id = :u", u=user_id
    )[0]
    assert profile == {"raw_about_text": "", "parse_status": "empty"}
    assert deleted.status_code == 204
    account = run_sql(
        url,
        "SELECT status, deletion_scheduled_for > now() + interval '29 days' AS later FROM users "
        "WHERE id = :u",
        u=user_id,
    )[0]
    assert account == {"status": "pending_deletion", "later": True}
    assert error_code(twice) == "invalid_status_change"
    assert error_code(no_profile) == "no_profile"
    for action in ("user.sign-out", "user.clear-bio", "user.schedule-deletion"):
        assert audit_count(settings, user_id, action) == 1


async def test_roles_and_admin_accounts_are_protected(
    settings: Settings, delivery: CapturingDelivery, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        moderator = await admin_with(client, settings, delivery, owner, AdminRole.MODERATOR)
        readonly = await admin_with(client, settings, delivery, owner, AdminRole.READONLY)
        _, user_id = await member(client, settings, delivery, "Kit")
        owner_id = (await client.get("/api/v1/admin/me", headers=owner.headers)).json()["user_id"]
        mod_id = (await client.get("/api/v1/admin/me", headers=moderator.headers)).json()["user_id"]

        mod_delete = await client.post(
            f"{USERS}/{user_id}/schedule-deletion", json=REASON, headers=moderator.headers
        )
        mod_suspend = await client.post(
            f"{USERS}/{user_id}/suspend", json=REASON, headers=moderator.headers
        )
        read_list = await client.get(USERS, headers=readonly.headers)
        read_act = await client.post(
            f"{USERS}/{user_id}/unsuspend", json=REASON, headers=readonly.headers
        )
        read_note = await client.post(
            f"{USERS}/{user_id}/notes", json={"body": "Hello"}, headers=readonly.headers
        )
        on_owner = await client.post(
            f"{USERS}/{owner_id}/ban", json=REASON, headers=moderator.headers
        )
        on_self = await client.post(
            f"{USERS}/{mod_id}/sign-out", json=REASON, headers=moderator.headers
        )

    assert error_code(mod_delete) == "admin_permission_denied"
    assert mod_suspend.status_code == 204
    assert read_list.status_code == 200
    assert error_code(read_act) == "admin_permission_denied"
    assert error_code(read_note) == "admin_permission_denied"
    assert error_code(on_owner) == "cannot_act_on_admin"
    assert error_code(on_self) == "cannot_act_on_admin"
    assert audit_count(settings, user_id, "user.schedule-deletion") == 0


async def test_suspended_and_banned_people_leave_other_peoples_lists(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        asha, ravi, _ = await connect(client, settings, delivery, migrated_database_url)
        sent = {"box": "sent"}
        before = (await client.get("/api/v1/connections", headers=asha.headers)).json()["items"]
        sent_before = (await client.get("/api/v1/intros", params=sent, headers=asha.headers)).json()
        await client.post(f"{USERS}/{ravi.id}/ban", json=REASON, headers=owner.headers)
        banned = (await client.get("/api/v1/connections", headers=asha.headers)).json()["items"]
        sent_banned = (await client.get("/api/v1/intros", params=sent, headers=asha.headers)).json()
        await client.post(f"{USERS}/{ravi.id}/unban", json=REASON, headers=owner.headers)
        back = (await client.get("/api/v1/connections", headers=asha.headers)).json()["items"]

    assert len(before) == 1
    assert len(sent_before["items"]) == 1
    assert banned == []
    assert sent_banned["items"] == []
    assert len(back) == 1
