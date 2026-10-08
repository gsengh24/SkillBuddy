"""Banners, the email send log, retry and template tests (A8), against real PostgreSQL.

Banners are global, so these tests use their own fresh database and clear the banner
cache before and after each test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import AdminRole
from app.services import banners
from app.services.email import EmailDeliveryError, EmailMessage
from app.services.email.send_log import LoggedSender
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import Person, admin_with, email, join, two_step
from tests.integration.test_auth_codes import error_code

COMMS = "/api/v1/admin/comms"
BANNER = "/api/v1/banner"
REASON = "Planned database maintenance tonight."
OWNER = email("owner")


@pytest.fixture(autouse=True)
def fresh_cache() -> Iterator[None]:
    banners.cache.invalidate()
    yield
    banners.cache.invalidate()


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


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def owner_of(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Person:
    owner = await join(client, settings, delivery, OWNER)
    await two_step(client, owner)
    return owner


async def test_a_banner_is_shown_until_it_ends(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        none_yet = await client.get(BANNER)
        published = await client.post(
            f"{COMMS}/banners",
            json={
                "announcement": "<b>Down</b> on Sunday 2:00 to 2:30 AM IST.",
                "kind": "maintenance",
                "reason": REASON,
            },
            headers=owner.headers,
        )
        shown = await client.get(BANNER)
        too_long = await client.post(
            f"{COMMS}/banners",
            json={"announcement": "x" * 161, "kind": "info", "reason": REASON},
            headers=owner.headers,
        )
        in_the_past = await client.post(
            f"{COMMS}/banners",
            json={
                "announcement": "Old news",
                "kind": "info",
                "ends_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                "reason": REASON,
            },
            headers=owner.headers,
        )
        ended = await client.post(
            f"{COMMS}/banners/{published.json()['id']}/end",
            json={"reason": REASON},
            headers=owner.headers,
        )
        gone = (await client.get(BANNER)).json()
        end_again = await client.post(
            f"{COMMS}/banners/{published.json()['id']}/end",
            json={"reason": REASON},
            headers=owner.headers,
        )

    assert none_yet.json() == {"banner": None}
    assert published.status_code == 201, published.text
    assert shown.headers["Cache-Control"] == "public, max-age=60"
    banner = shown.json()["banner"]
    # Plain text, exactly as written: clients never render it as HTML.
    assert banner["announcement"] == "<b>Down</b> on Sunday 2:00 to 2:30 AM IST."
    assert banner["kind"] == "maintenance"
    assert banner["ends_at"] is None
    assert too_long.status_code == 422
    assert error_code(in_the_past) == "invalid_banner_end"
    assert ended.status_code == 204
    assert gone == {"banner": None}
    assert error_code(end_again) == "banner_ended"
    audit = run_sql(
        fresh_url,
        "SELECT action FROM admin_audit_log WHERE action LIKE 'comms.%' ORDER BY created_at",
    )
    assert [row["action"] for row in audit] == ["comms.banner_published", "comms.banner_ended"]


async def test_an_expired_banner_is_not_shown(
    session_factory: async_sessionmaker[AsyncSession], fresh_url: str
) -> None:
    run_sql(
        fresh_url,
        "INSERT INTO banners (message, kind, ends_at) VALUES "
        "('Expired', 'warning', now() - interval '1 minute'), "
        "('Live', 'info', now() + interval '1 hour')",
    )
    async with session_factory() as db:
        live = await banners.active(db)
    assert live is not None
    assert live.message == "Live"

    run_sql(fresh_url, "UPDATE banners SET ends_at = now() - interval '1 second'")
    now = [1000.0]
    original = banners.cache.clock
    banners.cache.clock = lambda: now[0]
    try:
        banners.cache.invalidate()
        async with session_factory() as db:
            # Every banner has ended once the cache reloads.
            assert await banners.active(db) is None
    finally:
        banners.cache.clock = original


class FakeSender:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    @property
    def provider(self) -> str:
        return "fake"

    async def send(self, message: EmailMessage) -> str | None:
        if self.fail:
            raise EmailDeliveryError("SMTP 421 try later\nsecond line with details")
        return "id-1"


async def test_the_send_log_records_delivered_and_failed_emails(
    session_factory: async_sessionmaker[AsyncSession], fresh_url: str
) -> None:
    message = EmailMessage(to="sam@example.com", subject="Hi", text="Body text", html="<p>Body</p>")
    async with session_factory() as db:
        ok = LoggedSender(
            FakeSender(fail=False),
            db,
            template="invite",
            retry_kind="send_invite",
            retry_payload={"invite_code_id": "x"},
        )
        assert await ok.send(message) == "id-1"
        await db.commit()  # the caller commits after sending
        failing = LoggedSender(
            FakeSender(fail=True), db, template="login_code", retry_kind=None, retry_payload=None
        )
        with pytest.raises(EmailDeliveryError):
            await failing.send(message)

    rows = run_sql(
        fresh_url,
        "SELECT to_email, template, status, error, retry_kind FROM email_sends ORDER BY created_at",
    )
    assert rows == [
        {
            "to_email": "sam@example.com",
            "template": "invite",
            "status": "delivered",
            "error": None,
            "retry_kind": "send_invite",
        },
        {
            "to_email": "sam@example.com",
            "template": "login_code",
            "status": "failed",
            "error": "EmailDeliveryError: SMTP 421 try later",
            "retry_kind": None,
        },
    ]
    assert "Body" not in str(run_sql(fresh_url, "SELECT * FROM email_sends"))


async def test_retry_queues_the_sending_job_once(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    rows = run_sql(
        fresh_url,
        """INSERT INTO email_sends (to_email, template, status, error, retry_kind, retry_payload)
           VALUES ('a@example.com', 'safety_notice:warn', 'failed', 'Boom', 'send_safety_notice',
                   '{"user_id": "00000000-0000-4000-8000-000000000001", "kind": "warn"}'),
                  ('b@example.com', 'login_code', 'failed', 'Boom', NULL, NULL),
                  ('c@example.com', 'invite', 'delivered', NULL, 'send_invite',
                   '{"invite_code_id": "00000000-0000-4000-8000-000000000002"}')
           RETURNING id, template""",
    )
    ids = {row["template"]: str(row["id"]) for row in rows}
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        log = (await client.get(f"{COMMS}/emails?status=failed", headers=owner.headers)).json()

        async def retry(key: str) -> Response:
            return await client.post(
                f"{COMMS}/emails/{ids[key]}/retry", json={"reason": REASON}, headers=owner.headers
            )

        first = await retry("safety_notice:warn")
        again = await retry("safety_notice:warn")
        code = await retry("login_code")
        delivered = await retry("invite")

    assert {item["template"]: item["retryable"] for item in log["items"]} == {
        "safety_notice:warn": True,
        "login_code": False,
    }
    assert first.status_code == 202
    for refused in (again, code, delivered):
        assert error_code(refused) == "email_not_retryable"
    jobs = run_sql(fresh_url, "SELECT payload FROM jobs WHERE kind = 'send_safety_notice'")
    assert [job["payload"] for job in jobs] == [
        {"user_id": "00000000-0000-4000-8000-000000000001", "kind": "warn"}
    ]


async def test_template_tests_and_permissions(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        people = {
            role: await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        }
        page = (await client.get(COMMS, headers=owner.headers)).json()
        views = {
            role.value: (await client.get(COMMS, headers=person.headers)).status_code
            for role, person in people.items()
        }
        sent = await client.post(f"{COMMS}/templates/invite/test", headers=owner.headers)
        unknown = await client.post(f"{COMMS}/templates/nonsense/test", headers=owner.headers)
        moderator = await client.post(
            f"{COMMS}/banners",
            json={"announcement": "Hi", "kind": "info", "reason": REASON},
            headers=people[AdminRole.MODERATOR].headers,
        )
        limited = [
            (await client.post(f"{COMMS}/templates/invite/test", headers=owner.headers)).status_code
            for _ in range(10)
        ]

    assert "login_code" in [t["key"] for t in page["templates"]]
    assert views == {"admin": 200, "moderator": 403, "readonly": 403}
    assert sent.status_code == 202
    assert error_code(unknown) == "template_not_found"
    assert moderator.status_code == 403
    # Ten an hour per admin: two above (one unknown), then eight more, then 429.
    assert limited == [202] * 8 + [429] * 2
    owner_id = run_sql(fresh_url, "SELECT id FROM users WHERE email = :e", e=OWNER)[0]["id"]
    jobs = run_sql(fresh_url, "SELECT payload FROM jobs WHERE kind = 'send_test_email'")
    assert {"template": "invite", "user_id": str(owner_id)} in [job["payload"] for job in jobs]
