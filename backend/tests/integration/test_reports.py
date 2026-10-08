"""Reports of chat messages and the moderator's admin API, against real PostgreSQL."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.services import blocks
from app.services.reports import purge_resolved_reports, send_report_alert
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_chat import clear_of_minute_boundary, connect, say
from tests.integration.test_intros import Person, join, matched, send

TOKEN = "moderator-token-for-tests-only-0123456789abcdef"  # test value
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture
def make(make_settings: SettingsFactory, migrated_database_url: str) -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "database_url": migrated_database_url,
            "ai_llm_enabled": False,
            "admin_api_token": TOKEN,
        }
        return make_settings(**(values | overrides))

    return build


@pytest.fixture
def settings(make: Callable[..., Settings]) -> Settings:
    return make()


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def report(
    client: AsyncClient, person: Person, message_id: str, reason: str = "harassment", **extra: Any
) -> Any:
    return await client.post(
        f"/api/v1/messages/{message_id}/report",
        json={"reason": reason, **extra},
        headers=person.headers,
    )


# --- filing a report ----------------------------------------------------------------------


async def test_report_keeps_a_copy_of_the_reported_message_only(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        for number in range(12):
            speaker = asha if number % 2 else ravi
            last = (await say(client, speaker, connection, f"message {number}")).json()
        # The last one (number 11) is from Asha; Ravi reports it.
        filed = await report(client, ravi, last["id"], details="  Keeps insulting me.  ")
        notices = (await client.get("/api/v1/notifications", headers=asha.headers)).json()
        listed = await client.get("/api/v1/admin/reports", headers=ADMIN)

    assert filed.status_code == 201, filed.text
    assert set(filed.json()) == {"id", "created_at"}  # nothing else for the reporter
    # The reported person is not told: their only notice is the accepted intro.
    assert [item["kind"] for item in notices["items"]] == ["intro_accepted"]
    mine = next(item for item in listed.json()["items"] if item["id"] == filed.json()["id"])
    assert mine["reason"] == "harassment"
    assert mine["details"] == "Keeps insulting me."
    assert mine["status"] == "open"
    assert mine["reporter_id"] == ravi.id
    assert mine["reported_id"] == asha.id
    assert mine["connection_id"] == connection
    # Only what the reporter chose: the reported message, none of the ones before it (A3).
    assert [item["body"] for item in mine["messages"]] == ["message 11"]
    assert mine["messages"][0]["sender"] == "reported"
    stored = run_sql(
        url, "SELECT snapshot::text AS s FROM reports WHERE id = :r", r=filed.json()["id"]
    )
    assert "message 10" not in stored[0]["s"]


async def test_report_rules(
    make: Callable[..., Settings], delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    settings = make(reports_per_day=2)
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        theirs = [(await say(client, asha, connection, f"m{n}")).json()["id"] for n in range(3)]
        mine = (await say(client, ravi, connection, "mine")).json()["id"]
        mallory = await join(client, settings, delivery, "Mallory")

        own = await report(client, ravi, mine)
        outsider = await report(client, mallory, theirs[0])
        unknown = await report(client, ravi, str(uuid.uuid4()))
        bad_reason = await report(client, ravi, theirs[0], reason="rude")
        too_long = await report(client, ravi, theirs[0], details="x" * 501)
        anonymous = await client.post(
            f"/api/v1/messages/{theirs[0]}/report", json={"reason": "spam"}
        )
        first = await report(client, ravi, theirs[0])
        again = await report(client, ravi, theirs[0])
        over_limit = await report(client, ravi, theirs[1])

    assert own.status_code == 409
    assert error_code(own) == "cannot_report_own_message"
    for response in (outsider, unknown):
        assert response.status_code == 404
        assert error_code(response) == "message_not_found"
    assert bad_reason.status_code == 422
    assert too_long.status_code == 422
    assert anonymous.status_code == 401
    assert first.status_code == 201
    assert again.status_code == 409
    assert error_code(again) == "already_reported"
    assert over_limit.status_code == 429


async def test_reporting_still_works_after_a_block(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        message = (await say(client, asha, connection, "Threat")).json()

        async def everyone_blocked(_db: Any, _user_id: uuid.UUID) -> frozenset[uuid.UUID]:
            return frozenset({uuid.UUID(asha.id), uuid.UUID(ravi.id)})

        monkeypatch.setattr(blocks, "blocked_with", everyone_blocked)
        filed = await report(client, ravi, message["id"], reason="safety")

    assert filed.status_code == 201


async def test_report_survives_account_deletion_and_the_message_purge(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        message = (await say(client, asha, connection, "Evidence")).json()
        filed = (await report(client, ravi, message["id"])).json()
    run_sql(url, "DELETE FROM users WHERE id = :u", u=asha.id)

    row = run_sql(
        url,
        "SELECT reporter_id, reported_id, connection_id, snapshot FROM reports WHERE id = :r",
        r=filed["id"],
    )[0]
    assert str(row["reporter_id"]) == ravi.id
    assert row["reported_id"] is None
    assert row["connection_id"] is None
    assert row["snapshot"][-1]["body"] == "Evidence"


# --- the admin API ------------------------------------------------------------------------


async def test_admin_reports_need_the_token(
    make: Callable[..., Settings], delivery: CapturingDelivery
) -> None:
    disabled = make(admin_api_token=None)
    async with auth_client(disabled, delivery) as client:
        off = await client.get("/api/v1/admin/reports", headers=ADMIN)
    async with auth_client(make(), delivery) as client:
        missing = await client.get("/api/v1/admin/reports")
        wrong = await client.get("/api/v1/admin/reports", headers={"X-Admin-Token": "x" * 40})
        right = await client.get("/api/v1/admin/reports", headers=ADMIN)

    assert off.status_code == 404
    # No token and no session is anonymous (ADR 0015); a wrong token is refused.
    assert missing.status_code == 401
    assert wrong.status_code == 403
    assert right.status_code == 200


async def test_admin_requests_are_rate_limited_before_the_token_check(
    make: Callable[..., Settings], delivery: CapturingDelivery
) -> None:
    settings = make(admin_requests_per_minute=3)
    async with auth_client(settings, delivery) as client:
        await clear_of_minute_boundary()
        statuses = [
            (
                await client.get("/api/v1/admin/reports", headers={"X-Admin-Token": "guess"})
            ).status_code
            for _ in range(4)
        ]
        right = await client.get("/api/v1/admin/reports", headers=ADMIN)

    assert statuses == [403, 403, 403, 429]
    assert right.status_code == 429


async def test_the_admin_token_is_never_logged(
    settings: Settings, delivery: CapturingDelivery, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    async with auth_client(settings, delivery) as client:
        await client.get("/api/v1/admin/reports", headers=ADMIN)
        await client.get("/api/v1/admin/reports", headers={"X-Admin-Token": TOKEN[:-1] + "!"})

    for record in caplog.records:
        assert TOKEN not in record.getMessage()
        assert TOKEN not in str(record.__dict__)
        assert TOKEN[:-1] not in str(record.__dict__)


async def test_moderator_reads_and_resolves_a_report(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, migrated_database_url)
        message = (await say(client, asha, connection, "Buy my course")).json()
        filed = (await report(client, ravi, message["id"], reason="spam")).json()
        one = await client.get(f"/api/v1/admin/reports/{filed['id']}", headers=ADMIN)
        missing = await client.get(f"/api/v1/admin/reports/{uuid.uuid4()}", headers=ADMIN)
        resolved = await client.post(
            f"/api/v1/admin/reports/{filed['id']}/resolve",
            json={"note": "Warned them."},
            headers=ADMIN,
        )
        twice = await client.post(
            f"/api/v1/admin/reports/{filed['id']}/resolve", json={}, headers=ADMIN
        )
        still_open = (await client.get("/api/v1/admin/reports", headers=ADMIN)).json()
        done = (
            await client.get("/api/v1/admin/reports", params={"status": "resolved"}, headers=ADMIN)
        ).json()

    assert one.status_code == 200
    assert one.json()["messages"][-1]["body"] == "Buy my course"
    assert missing.status_code == 404
    assert error_code(missing) == "report_not_found"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolution_note"] == "Warned them."
    assert resolved.json()["resolved_at"] is not None
    assert twice.status_code == 409
    assert error_code(twice) == "report_already_resolved"
    assert filed["id"] not in {item["id"] for item in still_open["items"]}
    assert filed["id"] in {item["id"] for item in done["items"]}


# --- alert email and retention --------------------------------------------------------------


async def test_alert_email_carries_only_counts_and_goes_once(
    make: Callable[..., Settings],
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    capsys: pytest.CaptureFixture[str],
) -> None:
    url = migrated_database_url
    run_sql(url, "DELETE FROM email_log")  # other tests fill the shared log up to the cap
    settings = make(email_backend="console", moderator_email="moderator@example.com")
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        first = (await say(client, asha, connection, "secret insult one")).json()
        second = (await say(client, asha, connection, "secret insult two")).json()
        a = (await report(client, ravi, first["id"])).json()
        b = (await report(client, ravi, second["id"], reason="scam")).json()
    capsys.readouterr()

    async with session_factory() as db:
        covered = await send_report_alert(db, settings, datetime.now(UTC))
    out = capsys.readouterr().out
    async with session_factory() as db:
        again = await send_report_alert(db, settings, datetime.now(UTC))

    assert covered >= 2
    assert again == 0
    assert "moderator@example.com" in out
    assert "secret insult" not in out
    for private in ("scam", "harassment", "Asha", "Ravi"):
        assert private not in out
    alerted = run_sql(
        url, "SELECT alerted_at FROM reports WHERE id IN (:a, :b)", a=a["id"], b=b["id"]
    )
    assert all(row["alerted_at"] is not None for row in alerted)


async def test_no_alert_without_a_moderator_address(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as db:
        assert await send_report_alert(db, settings, datetime.now(UTC)) == 0


async def test_resolved_reports_are_purged_after_180_days(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        ids = []
        for body in ("old resolved", "recent resolved", "old open"):
            message = (await say(client, asha, connection, body)).json()
            ids.append((await report(client, ravi, message["id"])).json()["id"])
    old_resolved, recent_resolved, old_open = ids
    run_sql(
        url,
        "UPDATE reports SET status = 'resolved', resolved_at = now() - interval '181 days' "
        "WHERE id = :r",
        r=old_resolved,
    )
    run_sql(
        url,
        "UPDATE reports SET status = 'resolved', resolved_at = now() - interval '10 days' "
        "WHERE id = :r",
        r=recent_resolved,
    )
    run_sql(
        url, "UPDATE reports SET created_at = now() - interval '400 days' WHERE id = :r", r=old_open
    )

    async with session_factory() as db:
        await purge_resolved_reports(db, settings, datetime.now(UTC))

    left = {str(row["id"]) for row in run_sql(url, "SELECT id FROM reports")}
    assert old_resolved not in left
    assert recent_resolved in left
    assert old_open in left


# --- intros and profiles ------------------------------------------------------------------


async def test_the_recipient_can_report_an_intro(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        _, match = matched(url, asha, ravi)
        intro = (await send(client, asha, match, "Send me your bank details")).json()
        by_sender = await client.post(
            f"/api/v1/intros/{intro['id']}/report", json={"reason": "scam"}, headers=asha.headers
        )
        filed = await client.post(
            f"/api/v1/intros/{intro['id']}/report", json={"reason": "scam"}, headers=ravi.headers
        )
        again = await client.post(
            f"/api/v1/intros/{intro['id']}/report", json={"reason": "spam"}, headers=ravi.headers
        )
        shown = await client.get(f"/api/v1/admin/reports/{filed.json()['id']}", headers=ADMIN)

    assert by_sender.status_code == 404
    assert error_code(by_sender) == "intro_not_found"
    assert filed.status_code == 201, filed.text
    assert again.status_code == 409
    report = shown.json()
    assert report["target"] == "intro"
    assert report["target_id"] == intro["id"]
    assert report["message_id"] is None
    assert report["reported_id"] == asha.id
    parts = {item["label"]: item["body"] for item in report["messages"]}
    assert parts == {
        "request": "Looking for a designer for my app.",
        "note": "Send me your bank details",
    }


async def test_a_profile_report_copies_only_what_the_reporter_could_see(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        stranger = await join(client, settings, delivery, "Stranger")
        matched(url, asha, ravi)  # Asha saw Ravi as a match: contact, but not connected
        # Profiles shown as matches are parsed; parsing runs as a job, so set it here.
        run_sql(
            url,
            "UPDATE profiles SET structured = CAST(:s AS jsonb) WHERE user_id = :u",
            s='{"summary": "Designs mobile apps.", "offers": ["UI design"]}',
            u=ravi.id,
        )
        as_match = await client.post(
            f"/api/v1/people/{ravi.id}/report", json={"reason": "other"}, headers=asha.headers
        )
        no_contact = await client.post(
            f"/api/v1/people/{stranger.id}/report", json={"reason": "other"}, headers=asha.headers
        )
        myself = await client.post(
            f"/api/v1/people/{asha.id}/report", json={"reason": "other"}, headers=asha.headers
        )
        sender, recipient, _ = await connect(client, settings, delivery, url)
        connected = await client.post(
            f"/api/v1/people/{sender.id}/report",
            json={"reason": "inappropriate"},
            headers=recipient.headers,
        )
        unmatched = await client.get(
            f"/api/v1/admin/reports/{as_match.json()['id']}", headers=ADMIN
        )
        named = await client.get(f"/api/v1/admin/reports/{connected.json()['id']}", headers=ADMIN)

    assert as_match.status_code == 201, as_match.text
    for response in (no_contact, myself):
        assert response.status_code == 404
        assert error_code(response) == "person_not_found"
    first = unmatched.json()
    assert first["target"] == "profile"
    assert first["target_id"] == ravi.id
    labels = {item["label"] for item in first["messages"]}
    assert "summary" in labels
    assert not {"name", "links"} & labels  # not connected: no name or links in the copy
    assert "Ravi" not in str(first["messages"])
    second = {item["label"]: item["body"] for item in named.json()["messages"]}
    assert (
        second["name"] == "Asha"
    )  # connected: the copy has the name (connect() names the sender Asha)


async def test_reporting_a_profile_that_was_never_processed_still_works(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    """A profile whose description hasn't been read yet has nothing structured to copy: the
    report is still accepted, with an empty copy, instead of failing."""
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        asha = await join(client, settings, delivery, "Asha")
        ravi = await join(client, settings, delivery, "Ravi")
        matched(url, asha, ravi)
        run_sql(
            url,
            "UPDATE profiles SET structured = '{}'::jsonb, parse_status = 'pending' "
            "WHERE user_id = :u",
            u=ravi.id,
        )
        filed = await client.post(
            f"/api/v1/people/{ravi.id}/report", json={"reason": "other"}, headers=asha.headers
        )
        shown = await client.get(f"/api/v1/admin/reports/{filed.json()['id']}", headers=ADMIN)
        listed = await client.get("/api/v1/admin/reports", headers=ADMIN)

    assert filed.status_code == 201, filed.text
    assert shown.status_code == 200
    assert shown.json()["target"] == "profile"
    assert shown.json()["messages"] == []
    assert listed.status_code == 200
