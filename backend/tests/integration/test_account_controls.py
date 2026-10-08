"""Account controls (Prompt 12C): pause, signed-in devices, download my data. Real Postgres;
the export email goes through real SMTP to Mailpit."""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.services.data_exports import build_export, purge
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.mailpit import wait_for_message
from tests.integration.test_auth_codes import error_code, request_code, sign_in, verify
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_chat import connect, say
from tests.integration.test_intros import join, matched, send

ME = "/api/v1/auth/me"
SESSIONS = "/api/v1/auth/sessions"
EXPORTS = "/api/v1/me/data-exports"
CHROME_ON_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(
        database_url=migrated_database_url,
        ai_llm_enabled=False,
        email_backend="smtp",
        smtp_host=os.environ.get("SMTP_HOST", "localhost"),
        smtp_port=int(os.environ.get("SMTP_PORT", "1025")),
        smtp_security="none",
        email_from_address="no-reply@example.com",
        web_app_url="https://app.example",
    )


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


# --- pause ------------------------------------------------------------------------------


async def test_pause_hides_from_new_intros_but_keeps_sign_in_and_chats(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        anonymous = await client.post("/api/v1/me/pause")
        asha, ravi, connection = await connect(client, settings, delivery, url)
        paused = await client.post("/api/v1/me/pause", headers=ravi.headers)
        twice = await client.post("/api/v1/me/pause", headers=ravi.headers)
        me = await client.get(ME, headers=ravi.headers)
        to_paused = await say(client, asha, connection, "Still there?")
        from_paused = await say(client, ravi, connection, "Yes, just paused.")
        mina = await join(client, settings, delivery, "Mina")
        intro = await send(client, mina, matched(url, mina, ravi)[1])
        # Signing in again works while paused.
        email = me.json()["email"]
        await request_code(client, email)
        again = await verify(client, email, delivery.last_code(email), consent=False)
        resumed = await client.post("/api/v1/me/resume", headers=ravi.headers)
        not_paused = await client.post("/api/v1/me/resume", headers=ravi.headers)

    assert anonymous.status_code == 401
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert error_code(twice) == "cannot_pause"
    assert me.json()["status"] == "paused"
    assert (to_paused.status_code, from_paused.status_code) == (201, 201)
    assert error_code(intro) == "candidate_unavailable"
    assert again.status_code == 200
    assert resumed.json()["status"] == "active"
    assert error_code(not_paused) == "not_paused"
    events = run_sql(
        url,
        "SELECT event_type FROM auth_events WHERE user_id = :u AND event_type LIKE 'account_%'"
        " ORDER BY created_at",
        u=ravi.id,
    )
    assert [e["event_type"] for e in events] == ["account_paused", "account_resumed"]


# --- devices ----------------------------------------------------------------------------


async def test_devices_are_listed_and_signed_out_one_by_one_or_all_others(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email = f"devices-{os.urandom(6).hex()}@example.com"
    tokens: list[str] = []
    for _ in range(3):
        async with auth_client(settings, delivery) as client:
            client.headers["user-agent"] = CHROME_ON_WINDOWS
            if not tokens:
                await sign_in(client, delivery, email)
            else:
                await request_code(client, email)
                await verify(client, email, delivery.last_code(email), consent=False)
            tokens.append(client.cookies[settings.session_cookie_name])
    phone = tokens[2]

    async with auth_client(settings, delivery) as client:
        anonymous = await client.get(SESSIONS)
        listed = (await client.get(SESSIONS, headers=bearer(phone))).json()["items"]
        current = next(item for item in listed if item["current"])
        others = [item for item in listed if not item["current"]]
        one = await client.delete(f"{SESSIONS}/{others[0]['id']}", headers=bearer(phone))
        again = await client.delete(f"{SESSIONS}/{others[0]['id']}", headers=bearer(phone))
        alive = [(await client.get(ME, headers=bearer(t))).status_code for t in tokens]
        rest = await client.post("/api/v1/auth/logout-others", headers=bearer(phone))
        after = [(await client.get(ME, headers=bearer(t))).status_code for t in tokens]
        stranger = await join(client, settings, delivery, "Stranger")
        not_yours = await client.delete(f"{SESSIONS}/{current['id']}", headers=stranger.headers)

    assert anonymous.status_code == 401
    assert len(listed) == 3
    assert {item["device"] for item in listed} == {"Chrome on Windows"}
    assert set(current) == {"id", "device", "current", "created_at", "last_seen_at"}
    assert one.status_code == 204
    assert error_code(again) == "session_not_found"
    assert sorted(alive) == [200, 200, 401]
    assert rest.status_code == 204
    assert after == [401, 401, 200]
    assert error_code(not_yours) == "session_not_found"


# --- download my data -------------------------------------------------------------------


def _link(message: dict[str, Any]) -> tuple[str, str]:
    match = re.search(r"https://app\.example/you/download\?\S+", str(message.get("Text", "")))
    assert match, "no download link in the email"
    query = parse_qs(urlparse(match.group(0)).query)
    return query["export"][0], query["token"][0]


async def test_data_export_is_built_in_a_job_emailed_and_downloaded(
    settings: Settings,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    url = migrated_database_url
    run_sql(url, "DELETE FROM email_log")
    async with auth_client(settings, delivery) as client:
        asha, ravi, connection = await connect(client, settings, delivery, url)
        await say(client, asha, connection, "Hello from Asha")
        await say(client, ravi, connection, "Hello from Ravi")
        email = (await client.get(ME, headers=asha.headers)).json()["email"]
        anonymous = await client.post(EXPORTS)
        requested = await client.post(EXPORTS, headers=asha.headers)
        too_soon = await client.post(EXPORTS, headers=asha.headers)
        export_id = requested.json()["id"]
        queued = run_sql(
            url,
            "SELECT count(*) AS n FROM jobs WHERE kind = 'build_data_export'"
            " AND payload->>'export_id' = :e",
            e=export_id,
        )[0]["n"]

        async with session_factory() as db:
            await build_export(db, settings, uuid.UUID(export_id))
        message = await wait_for_message(email)
        link_export, token = _link(message)
        download = await client.get(
            f"{EXPORTS}/{link_export}/download", params={"token": token}, headers=asha.headers
        )
        wrong_token = await client.get(
            f"{EXPORTS}/{link_export}/download", params={"token": "x" * 43}, headers=asha.headers
        )
        not_hers = await client.get(
            f"{EXPORTS}/{link_export}/download", params={"token": token}, headers=ravi.headers
        )
        listed = (await client.get(EXPORTS, headers=asha.headers)).json()["items"]

        run_sql(url, "UPDATE data_exports SET expires_at = now() - interval '1 minute'")
        async with session_factory() as db:
            counts = await purge(db, settings)
        expired = await client.get(
            f"{EXPORTS}/{link_export}/download", params={"token": token}, headers=asha.headers
        )

    assert anonymous.status_code == 401
    assert requested.status_code == 202
    assert requested.json()["status"] == "requested"
    assert error_code(too_soon) == "data_export_recent"
    assert queued == 1
    assert link_export == export_id
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")
    data = json.loads(download.content)
    assert data["account"]["email"] == email
    assert data["profile"]["display_name"] == "Asha"
    assert [(m["from"], m["text"]) for m in data["messages"]] == [
        ("you", "Hello from Asha"),
        ("them", "Hello from Ravi"),
    ]
    assert data["connections"][0]["other_display_name"] == "Ravi"
    assert data["intros"][0]["direction"] == "sent"
    assert error_code(wrong_token) == "data_export_unavailable"
    assert error_code(not_hers) == "data_export_not_found"
    assert listed[0]["status"] == "ready"
    assert listed[0]["downloaded_at"] is not None
    assert counts["expired"] >= 1
    assert error_code(expired) == "data_export_unavailable"
    row = run_sql(url, "SELECT status, payload FROM data_exports WHERE id = :e", e=export_id)[0]
    assert (row["status"], row["payload"]) == ("expired", None)
    # The token is stored only as a hash.
    assert token not in json.dumps(
        run_sql(url, "SELECT token_hash FROM data_exports WHERE id = :e", e=export_id)[0]
    )


async def test_an_export_that_cannot_be_emailed_fails_and_can_be_asked_again(
    make_settings: SettingsFactory,
    delivery: CapturingDelivery,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    no_link = make_settings(
        database_url=migrated_database_url, ai_llm_enabled=False, web_app_url=None
    )
    async with auth_client(no_link, delivery) as client:
        person = await join(client, no_link, delivery, "Ivy")
        first = (await client.post(EXPORTS, headers=person.headers)).json()
        async with session_factory() as db:
            await build_export(db, no_link, uuid.UUID(first["id"]))
        listed = (await client.get(EXPORTS, headers=person.headers)).json()["items"]
        second = await client.post(EXPORTS, headers=person.headers)

    assert listed[0]["status"] == "failed"
    assert second.status_code == 202
