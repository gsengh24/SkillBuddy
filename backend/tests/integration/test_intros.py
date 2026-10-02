"""Intros, connections and notifications through the API, against real PostgreSQL."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.services.matching.housekeeping import expire_intros
from app.services.notification_email import send_notification_email
from app.services.notifications import purge_old_notifications
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_profile_api import body as profile_body
from tests.integration.test_profile_api import signed_in


@dataclass
class Person:
    token: str
    id: str

    @property
    def headers(self) -> dict[str, str]:
        return bearer(self.token)


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def join(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, name: str
) -> Person:
    token = await signed_in(client, settings, delivery)
    await client.put(
        "/api/v1/me/profile",
        json=profile_body(display_name=name, links=[f"https://github.com/{name.lower()}"]),
        headers=bearer(token),
    )
    me = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()
    return Person(token=token, id=me["id"])


def matched(url: str, sender: Person, recipient: Person) -> tuple[str, str]:
    """A ready request from ``sender`` with ``recipient`` as match 1. Returns (request, match)."""
    request = run_sql(
        url,
        "INSERT INTO match_requests (user_id, raw_text, status, expires_at) "
        "VALUES (:u, 'Looking for a designer for my app.', 'ready', now() + interval '30 days') "
        "RETURNING id",
        u=sender.id,
    )[0]["id"]
    match = run_sql(
        url,
        "INSERT INTO matches (request_id, candidate_id, rank, score, reason) "
        "VALUES (:r, :c, 1, 0.9, 'They offer design, which you are looking for.') RETURNING id",
        r=request,
        c=recipient.id,
    )[0]["id"]
    return str(request), str(match)


async def send(client: AsyncClient, sender: Person, match: str, note: str = "Hi!") -> Any:
    return await client.post(
        f"/api/v1/matches/{match}/intro", json={"note": note}, headers=sender.headers
    )


def notifications_of(url: str, person: Person) -> list[dict[str, Any]]:
    return run_sql(url, "SELECT kind, intro_id FROM notifications WHERE user_id = :u", u=person.id)


def match_status(url: str, match: str) -> str:
    return str(run_sql(url, "SELECT status FROM matches WHERE id = :m", m=match)[0]["status"])


# --- send ---------------------------------------------------------------------------------


async def test_send_shows_no_name_and_notifies_the_recipient(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(url, asha, ravi)
        sent = await send(client, asha, match, "  Hi Ravi, want to build this?  ")
        inbox = (await client.get("/api/v1/intros?box=received", headers=ravi.headers)).json()
        unread = (
            await client.get("/api/v1/notifications/unread-count", headers=ravi.headers)
        ).json()

    assert sent.status_code == 201, sent.text
    intro = sent.json()
    assert intro["status"] == "pending"
    assert intro["direction"] == "sent"
    assert intro["note"] == "Hi Ravi, want to build this?"
    assert intro["person"]["display_name"] is None
    assert intro["person"]["links"] is None
    received = inbox["items"][0]
    assert received["id"] == intro["id"]
    assert received["direction"] == "received"
    assert received["request_text"] == "Looking for a designer for my app."
    assert received["reason"].startswith("They offer design")
    assert received["person"]["user_id"] == asha.id
    assert received["person"]["display_name"] is None
    assert "Asha" not in str(inbox)
    assert unread == {"unread": 1}
    assert notifications_of(url, ravi) == [
        {"kind": "intro_received", "intro_id": uuid.UUID(intro["id"])}
    ]
    assert match_status(url, match) == "intro_sent"
    jobs = run_sql(
        url, "SELECT 1 FROM jobs WHERE kind = 'send_notification_email' AND status = 'queued'"
    )
    assert jobs


# --- answers ------------------------------------------------------------------------------


async def test_accepting_connects_both_and_shares_names(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(url, asha, ravi)
        intro_id = (await send(client, asha, match)).json()["id"]
        accepted = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": True}, headers=ravi.headers
        )
        seen_by_asha = (await client.get(f"/api/v1/intros/{intro_id}", headers=asha.headers)).json()
        asha_connections = (await client.get("/api/v1/connections", headers=asha.headers)).json()
        ravi_connections = (await client.get("/api/v1/connections", headers=ravi.headers)).json()
        again = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": False}, headers=ravi.headers
        )

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["person"]["display_name"] == "Asha"
    assert accepted.json()["person"]["links"] == ["https://github.com/asha"]
    assert seen_by_asha["status"] == "accepted"
    assert seen_by_asha["person"]["display_name"] == "Ravi"
    assert [c["person"]["display_name"] for c in asha_connections["items"]] == ["Ravi"]
    assert [c["person"]["display_name"] for c in ravi_connections["items"]] == ["Asha"]
    assert {"kind": "intro_accepted", "intro_id": uuid.UUID(intro_id)} in notifications_of(
        url, asha
    )
    assert match_status(url, match) == "accepted"
    assert error_code(again) == "intro_not_pending"


async def test_a_decline_is_silent_to_the_sender(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        request, match = matched(url, asha, ravi)
        intro_id = (await send(client, asha, match)).json()["id"]
        declined = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": False}, headers=ravi.headers
        )
        seen_by_asha = (await client.get(f"/api/v1/intros/{intro_id}", headers=asha.headers)).json()
        matches = (
            await client.get(f"/api/v1/requests/{request}/matches", headers=asha.headers)
        ).json()

    assert declined.json()["status"] == "declined"
    assert seen_by_asha["status"] == "pending"
    assert seen_by_asha["responded_at"] is None
    assert matches["items"][0]["status"] == "intro_sent"
    assert notifications_of(url, asha) == []


async def test_withdraw_removes_the_intro_and_allows_a_new_one(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(url, asha, ravi)
        intro_id = (await send(client, asha, match)).json()["id"]
        not_yours = await client.delete(f"/api/v1/intros/{intro_id}", headers=ravi.headers)
        withdrawn = await client.delete(f"/api/v1/intros/{intro_id}", headers=asha.headers)
        gone = await client.get(f"/api/v1/intros/{intro_id}", headers=ravi.headers)
        resent = await send(client, asha, match)

    assert error_code(not_yours) == "intro_not_found"
    assert withdrawn.status_code == 204
    assert error_code(gone) == "intro_not_found"
    assert resent.status_code == 201
    assert [n["kind"] for n in notifications_of(url, ravi)] == ["intro_received"]


# --- failures -----------------------------------------------------------------------------


async def test_send_failures(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        anonymous = await client.post(f"/api/v1/matches/{uuid.uuid4()}/intro", json={})
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        mina = await join(client, settings, delivery, "Mina")
        _, match = matched(url, asha, ravi)
        not_yours = await send(client, mina, match)
        unknown = await send(client, asha, str(uuid.uuid4()))
        too_long = await send(client, asha, match, "x" * 501)
        first = await send(client, asha, match)
        twice = await send(client, asha, match)
        # Ravi asks too, and Asha is his match: an intro is already open between them.
        _, reverse = matched(url, ravi, asha)
        reverse_intro = await send(client, ravi, reverse)
        await client.post(
            f"/api/v1/intros/{first.json()['id']}/respond",
            json={"accept": True},
            headers=ravi.headers,
        )
        _, after = matched(url, asha, ravi)
        connected = await send(client, asha, after)
        await client.patch(
            "/api/v1/me/profile", json={"visibility": "paused"}, headers=mina.headers
        )
        _, paused = matched(url, asha, mina)
        unavailable = await send(client, asha, paused)

    assert anonymous.status_code == 401
    assert error_code(not_yours) == "match_not_found"
    assert error_code(unknown) == "match_not_found"
    assert too_long.status_code == 422
    assert first.status_code == 201
    assert error_code(twice) == "intro_exists"
    assert error_code(reverse_intro) == "intro_exists"
    assert error_code(connected) == "already_connected"
    assert error_code(unavailable) == "candidate_unavailable"


async def test_answer_failures(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(url, asha, ravi)
        intro_id = (await send(client, asha, match)).json()["id"]
        by_sender = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": True}, headers=asha.headers
        )
        run_sql(
            url,
            "UPDATE intros SET expires_at = now() - interval '1 hour' WHERE id = :i",
            i=intro_id,
        )
        expired = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": True}, headers=ravi.headers
        )
        view = (await client.get(f"/api/v1/intros/{intro_id}", headers=asha.headers)).json()
        bad_body = await client.post(
            f"/api/v1/intros/{intro_id}/respond", json={"accept": "maybe"}, headers=ravi.headers
        )

    assert error_code(by_sender) == "intro_not_found"
    assert error_code(expired) == "intro_not_pending"
    assert view["status"] == "expired"
    assert bad_body.status_code == 422


async def test_daily_and_pending_limits(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    url = migrated_database_url
    settings = make_settings(database_url=url, ai_llm_enabled=False, intros_per_day=2)
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        others = [await join(client, settings, delivery, f"P{i}") for i in range(3)]
        codes = [(await send(client, asha, matched(url, asha, p)[1])).status_code for p in others]
    assert codes == [201, 201, 429]


# --- notifications ------------------------------------------------------------------------


async def test_notifications_list_count_and_mark_read(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        ravi = await join(client, settings, delivery, "Ravi")
        senders = [await join(client, settings, delivery, f"S{i}") for i in range(3)]
        for sender in senders:
            await send(client, sender, matched(url, sender, ravi)[1])
        first = (await client.get("/api/v1/notifications?limit=2", headers=ravi.headers)).json()
        second = (
            await client.get(
                f"/api/v1/notifications?limit=2&cursor={first['next_cursor']}", headers=ravi.headers
            )
        ).json()
        one = await client.post(
            "/api/v1/notifications/read",
            json={"ids": [first["items"][0]["id"]]},
            headers=ravi.headers,
        )
        after_one = (
            await client.get("/api/v1/notifications/unread-count", headers=ravi.headers)
        ).json()
        everything = await client.post("/api/v1/notifications/read", json={}, headers=ravi.headers)
        after_all = (
            await client.get("/api/v1/notifications/unread-count", headers=ravi.headers)
        ).json()
        bad = await client.get("/api/v1/notifications?cursor=nope", headers=ravi.headers)
        anonymous = await client.get("/api/v1/notifications")

    assert first["unread"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert {item["kind"] for item in first["items"]} == {"intro_received"}
    assert one.json() == {"marked": 1}
    assert after_one == {"unread": 2}
    assert everything.json() == {"marked": 2}
    assert after_all == {"unread": 0}
    assert error_code(bad) == "invalid_cursor"
    assert anonymous.status_code == 401


async def test_notification_emails_respect_the_switch_and_the_reserve(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    delivery: CapturingDelivery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    # Other tests fill the shared email log up to the cap; start from an empty one.
    run_sql(url, "DELETE FROM email_log")
    settings = make_settings(database_url=url, ai_llm_enabled=False, email_backend="console")
    async with auth_client(settings, delivery) as client:
        ravi = await join(client, settings, delivery, "Ravi")
        mina = await join(client, settings, delivery, "Mina")
        asha = await join(client, settings, delivery, "Asha")
        await client.patch(
            "/api/v1/me/profile", json={"email_notifications": False}, headers=mina.headers
        )
        await send(client, asha, matched(url, asha, ravi)[1])
        await send(client, asha, matched(url, asha, mina)[1])
    to_ravi = run_sql(url, "SELECT id FROM notifications WHERE user_id = :u", u=ravi.id)[0]["id"]
    to_mina = run_sql(url, "SELECT id FROM notifications WHERE user_id = :u", u=mina.id)[0]["id"]
    tight = make_settings(
        database_url=url,
        ai_llm_enabled=False,
        email_backend="console",
        email_daily_cap=200,
        email_reserve_for_codes=199,
    )

    async with session_factory() as db:
        sent = await send_notification_email(db, settings, to_ravi)
    async with session_factory() as db:
        opted_out = await send_notification_email(db, settings, to_mina)
    run_sql(url, "UPDATE notifications SET read_at = NULL WHERE id = :n", n=to_ravi)
    async with session_factory() as db:
        reserve_only = await send_notification_email(db, tight, to_ravi)

    assert sent is True
    assert opted_out is False
    assert reserve_only is False
    logged = run_sql(url, "SELECT count(*) AS n FROM email_log WHERE purpose = 'notification'")[0][
        "n"
    ]
    assert logged >= 1


async def test_housekeeping_expires_intros_and_purges_notifications(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        intro_id = (await send(client, asha, matched(url, asha, ravi)[1])).json()["id"]
    run_sql(
        url, "UPDATE intros SET expires_at = now() - interval '1 day' WHERE id = :i", i=intro_id
    )
    run_sql(
        url,
        "UPDATE notifications SET created_at = now() - interval '200 days' WHERE user_id = :u",
        u=ravi.id,
    )
    now = datetime.now(UTC)
    async with session_factory() as db:
        expired = await expire_intros(db, now)
        purged = await purge_old_notifications(db, settings, now)
    assert expired >= 1
    assert purged >= 1
    assert run_sql(url, "SELECT status FROM intros WHERE id = :i", i=intro_id) == [
        {"status": "expired"}
    ]
    assert notifications_of(url, ravi) == []
