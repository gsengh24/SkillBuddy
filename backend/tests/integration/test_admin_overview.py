"""The admin Overview and health (A4). The numbers are checked on a fresh database with a
small fixed data set, so other tests' rows can't change them."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import AdminRole
from app.services.admin import overview
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import admin_with, email, join, two_step

ADMIN = "/api/v1/admin"

SEED = [
    # Four people: two joined in the last 7 days, one 10 days ago, one 20 days ago.
    """INSERT INTO users (id, email, created_at, updated_at, last_login_at) VALUES
       ('00000000-0000-4000-8000-000000000001', 'a@example.com', now() - interval '1 day',
        now(), now() - interval '1 hour'),
       ('00000000-0000-4000-8000-000000000002', 'b@example.com', now() - interval '2 days',
        now(), now() - interval '2 days'),
       ('00000000-0000-4000-8000-000000000003', 'c@example.com', now() - interval '10 days',
        now(), now() - interval '9 days'),
       ('00000000-0000-4000-8000-000000000004', 'd@example.com', now() - interval '20 days',
        now(), NULL)""",
    # Two requests this week, one last week.
    """INSERT INTO match_requests (id, user_id, raw_text, status, created_at, updated_at,
       expires_at) VALUES
       ('10000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001',
        'Looking for a designer.', 'ready', now() - interval '1 day', now(),
        now() + interval '30 days'),
       ('10000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000002',
        'Looking for a developer.', 'ready', now() - interval '2 days', now(),
        now() + interval '30 days'),
       ('10000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000003',
        'Looking for a mentor.', 'ready', now() - interval '9 days', now(),
        now() + interval '30 days')""",
    # Three matches this week.
    """INSERT INTO matches (id, request_id, candidate_id, rank, score, reason, status,
       created_at, updated_at) VALUES
       ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000002', 1, 0.9, 'Fits.', 'intro_sent',
        now() - interval '1 day', now()),
       ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000003', 2, 0.8, 'Fits.', 'shown',
        now() - interval '1 day', now()),
       ('20000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000002',
        '00000000-0000-4000-8000-000000000001', 1, 0.9, 'Fits.', 'intro_sent',
        now() - interval '2 days', now())""",
    # Two intros this week, one accepted.
    """INSERT INTO intros (id, match_id, sender_id, recipient_id, note, status, created_at,
       updated_at, expires_at) VALUES
       ('30000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002', '',
        'accepted', now() - interval '1 day', now(), now() + interval '14 days'),
       ('30000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000003',
        '00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000001', '',
        'pending', now() - interval '2 days', now(), now() + interval '14 days')""",
    """INSERT INTO connections (id, user_a, user_b, created_at) VALUES
       ('40000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000002', now() - interval '1 day')""",
    """INSERT INTO messages (id, connection_id, from_a, body, created_at) VALUES
       (gen_random_uuid(), '40000000-0000-4000-8000-000000000001', true, 'hi',
        now() - interval '1 hour'),
       (gen_random_uuid(), '40000000-0000-4000-8000-000000000001', false, 'hello',
        now() - interval '30 minutes')""",
    """INSERT INTO reports (reporter_id, reported_id, target, target_id, reason, snapshot)
       VALUES ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000003',
       'profile', '00000000-0000-4000-8000-000000000003', 'spam', '[]'::jsonb)""",
]


@pytest.fixture
def fresh_url() -> Iterator[str]:
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        for statement in SEED:
            run_sql(url, statement)
        yield url


@pytest.fixture
async def fresh_db(
    make_settings: SettingsFactory, fresh_url: str
) -> AsyncIterator[tuple[Settings, async_sessionmaker[AsyncSession]]]:
    settings = make_settings(database_url=fresh_url, ai_llm_enabled=False)
    engine = create_engine(settings)
    try:
        yield settings, create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_the_numbers_on_a_fixed_data_set(
    fresh_db: tuple[Settings, async_sessionmaker[AsyncSession]],
) -> None:
    settings, factory = fresh_db
    async with factory() as db:
        week = await overview.build(db, settings, 7)
        month = await overview.build(db, settings, 30)

    kpis = {k.key: (k.value, k.previous) for k in week.kpis}
    assert kpis == {
        "new_signups": (2, 1),
        "active_users": (2, 1),
        "new_requests": (2, 1),
        "matches_made": (3, 0),
        "intro_accept_rate": (50.0, 0.0),
        "messages_sent": (2, 0),
    }
    assert dict(week.funnel) == {
        "requests": 2,
        "matches": 3,
        "intros_sent": 2,
        "intros_accepted": 1,
        "chats_started": 1,
    }
    assert len(week.signups_by_day) == 8
    assert sum(count for _, count in week.signups_by_day) == 2
    assert week.attention["open_reports"] == 1
    assert week.attention["pending_applications"] == 0
    assert set(week.attention) == {
        "open_reports",
        "pending_applications",
        "degraded_ai_providers",
        "due_data_requests",
        "failed_emails",
    }
    assert {k.key: k.value for k in month.kpis}["new_signups"] == 4


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(
        database_url=migrated_database_url,
        admin_owner_emails=[OWNER],
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
    )


OWNER = email("owner")


async def test_every_role_can_view_the_overview_and_health(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    overview._cache.clear()
    async with auth_client(settings, delivery) as client:
        owner = await join(client, settings, delivery, OWNER)
        await two_step(client, owner)
        people = [owner] + [
            await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        ]
        views = [
            (
                await client.get(f"{ADMIN}/overview", params={"days": 30}, headers=p.headers)
            ).status_code
            for p in people
        ]
        health = (await client.get(f"{ADMIN}/health", headers=people[-1].headers)).json()
        wrong_range = await client.get(
            f"{ADMIN}/overview", params={"days": 14}, headers=owner.headers
        )

    assert views == [200, 200, 200, 200]
    assert [check["name"] for check in health["checks"]][:2] == ["api", "database"]
    assert "email" in [check["name"] for check in health["checks"]]
    assert wrong_range.status_code == 422
