"""Scheduled hard deletes and purges, against real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.registry import JobContext
from app.jobs.tasks import HARD_DELETE_ACCOUNTS, PURGE_AUTH_DATA
from app.services.auth.retention import hard_delete_due_accounts, purge_expired_auth_data
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import sign_in

SCHEDULE_DELETION = (
    "UPDATE users SET status = 'pending_deletion', deleted_at = now(), "
    "deletion_scheduled_for = now() + make_interval(mins => :minutes) WHERE email = :e"
)
ROWS_LEFT_FOR_USER = (
    "SELECT (SELECT count(*) FROM users WHERE id = :id) "
    "+ (SELECT count(*) FROM auth_identities WHERE user_id = :id) "
    "+ (SELECT count(*) FROM sessions WHERE user_id = :id) "
    "+ (SELECT count(*) FROM auth_events WHERE user_id = :id) AS remaining"
)


async def _run_job(settings: Settings, kind_handler: Any) -> None:
    """Run a job's handler the way the runner does."""
    engine = create_engine(settings)
    try:
        await kind_handler(
            JobContext(
                job_id=uuid.uuid4(),
                kind="test",
                attempt=1,
                payload={},
                secret=None,
                settings=settings,
                session_factory=create_session_factory(engine),
            )
        )
    finally:
        await engine.dispose()


async def _call(settings: Settings, service: Any) -> Any:
    """Call a retention service function with a fresh session, as its job does."""
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            return await service(db, settings, datetime.now(UTC))
    finally:
        await engine.dispose()


async def _signed_up_user(settings: Settings, delivery: CapturingDelivery) -> tuple[str, str]:
    email = f"ret-{uuid.uuid4().hex[:12]}@example.com"
    async with auth_client(settings, delivery) as client:
        user = (await sign_in(client, delivery, email)).json()
    return email, str(user["id"])


async def test_hard_delete_removes_due_accounts_with_all_their_rows(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    due_email, due_id = await _signed_up_user(auth_settings, delivery)
    waiting_email, _ = await _signed_up_user(auth_settings, delivery)
    run_sql(migrated_database_url, SCHEDULE_DELETION, minutes=-1, e=due_email)
    run_sql(migrated_database_url, SCHEDULE_DELETION, minutes=5 * 24 * 60, e=waiting_email)

    deleted = await _call(auth_settings, hard_delete_due_accounts)
    deleted_again = await _call(auth_settings, hard_delete_due_accounts)

    assert deleted >= 1
    assert deleted_again == 0  # idempotent
    assert run_sql(migrated_database_url, ROWS_LEFT_FOR_USER, id=due_id) == [{"remaining": 0}]
    assert run_sql(migrated_database_url, "SELECT 1 FROM users WHERE email = :e", e=waiting_email)
    audit = run_sql(
        migrated_database_url,
        "SELECT user_id, detail FROM auth_events WHERE event_type = 'account_deleted' "
        "ORDER BY created_at DESC LIMIT 1",
    )
    assert audit[0]["user_id"] is None
    assert len(audit[0]["detail"]["user_ref"]) == 64
    assert due_id not in str(audit[0]["detail"])


async def test_purge_removes_expired_codes_sessions_and_old_events(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    email, user_id = await _signed_up_user(auth_settings, delivery)
    code_email = f"purge-{email}"
    run_sql(
        migrated_database_url,
        "INSERT INTO otp_codes (email, code_hash, expires_at) VALUES "
        "(:e, repeat('a', 64), now() - interval '1 hour'), "
        "(:e, repeat('b', 64), now() + interval '9 minutes')",
        e=code_email,
    )
    run_sql(
        migrated_database_url,
        "INSERT INTO sessions (user_id, token_hash, expires_at) "
        "VALUES (:u, :token_hash, now() - interval '1 day')",
        u=user_id,
        token_hash=uuid.uuid4().hex * 2,
    )
    run_sql(
        migrated_database_url,
        "INSERT INTO auth_events (user_id, event_type, created_at) VALUES "
        "(:u, 'login', now() - interval '91 days'), (:u, 'login', now() - interval '1 day')",
        u=user_id,
    )

    result = await _call(auth_settings, purge_expired_auth_data)

    assert result.otp_codes >= 1
    assert result.sessions >= 1
    assert result.auth_events >= 1
    now = datetime.now(UTC)
    codes = run_sql(
        migrated_database_url, "SELECT expires_at FROM otp_codes WHERE email = :e", e=code_email
    )
    assert [row["expires_at"] > now for row in codes] == [True]
    old_events = run_sql(
        migrated_database_url,
        "SELECT 1 FROM auth_events WHERE user_id = :u AND created_at < now() - interval '90 days'",
        u=user_id,
    )
    assert old_events == []
    sessions = run_sql(
        migrated_database_url, "SELECT 1 FROM sessions WHERE user_id = :u", u=user_id
    )
    assert len(sessions) == 1  # the session from signing in is still valid


async def test_retention_jobs_call_the_retention_services(
    auth_settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    """The scheduled job kinds are wired to the services tested above."""
    due_email, due_id = await _signed_up_user(auth_settings, delivery)
    run_sql(migrated_database_url, SCHEDULE_DELETION, minutes=-1, e=due_email)
    run_sql(
        migrated_database_url,
        "INSERT INTO otp_codes (email, code_hash, expires_at) "
        "VALUES ('wired@example.com', repeat('c', 64), now() - interval '1 hour')",
    )

    await _run_job(auth_settings, HARD_DELETE_ACCOUNTS.handler)
    await _run_job(auth_settings, PURGE_AUTH_DATA.handler)

    assert run_sql(migrated_database_url, ROWS_LEFT_FOR_USER, id=due_id) == [{"remaining": 0}]
    assert (
        run_sql(migrated_database_url, "SELECT 1 FROM otp_codes WHERE email = 'wired@example.com'")
        == []
    )
