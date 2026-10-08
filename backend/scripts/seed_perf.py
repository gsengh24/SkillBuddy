"""Fill a LOCAL database with 100,000 fake people, then time the admin Users queries.

    cd backend && uv run python -m scripts.seed_perf      # after alembic upgrade head

It refuses to run unless DATABASE_URL points at localhost: never run it against staging or
production. Everyone it creates is synthetic (``perf-<n>@example.com``). It prints EXPLAIN
ANALYZE for the list, search and filter queries (built by the same code the API uses) and
fails if any takes 200 ms or more. The "Admin performance" workflow runs it in CI on a
throwaway database.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from typing import Any, Final

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Dialect, make_url

from app.core.config import get_settings
from app.db.engine import create_engine as create_async_db_engine
from app.db.session import create_session_factory
from app.models import User, UserStatus
from app.services.admin import overview
from app.services.admin.users import PAGE_DEFAULT, Filters, list_query

LIMIT_MS: Final = 200.0
LOCAL_HOSTS: Final = {"localhost", "127.0.0.1", "::1"}

SEED = """
INSERT INTO users (id, email, status, created_at, updated_at, last_login_at)
SELECT gen_random_uuid(), 'perf-' || n || '@example.com',
       CASE WHEN n % 100 = 0 THEN 'suspended' WHEN n % 250 = 0 THEN 'banned' ELSE 'active' END,
       now() - (n || ' minutes')::interval, now(), now() - ((n % 30) || ' days')::interval
FROM generate_series(1, :users) AS n;

INSERT INTO profiles (user_id, display_name, raw_about_text, intents, created_at, updated_at)
SELECT u.id, 'Person ' || substr(u.email, 6, length(u.email) - 17),
       'I build things and want to learn more. Synthetic profile for timing only.',
       ARRAY[(ARRAY['build_together','skill_exchange','interest_buddy','accountability',
                    'mentor','explore'])[(1 + abs(hashtext(u.email)::bigint) % 6)::int]]::varchar[],
       now(), now()
FROM users u WHERE u.email LIKE 'perf-%@example.com';

INSERT INTO match_requests (id, user_id, raw_text, status, created_at, updated_at, expires_at)
SELECT gen_random_uuid(), u.id, 'Looking for someone to build an app with.', 'ready',
       now(), now(), now() + interval '30 days'
FROM users u WHERE u.email LIKE 'perf-%@example.com' AND abs(hashtext(u.email)::bigint) % 5 = 0;

INSERT INTO matches (id, request_id, candidate_id, rank, score, reason, status,
                     created_at, updated_at)
SELECT gen_random_uuid(), r.id, c.id, g.rank, 0.5, 'Both build apps.', 'shown', now(), now()
FROM match_requests r
CROSS JOIN LATERAL generate_series(1, 5) AS g(rank)
CROSS JOIN LATERAL (
    -- A different person for each of a request's five ranks (7919 is prime).
    SELECT id FROM users WHERE email = 'perf-'
        || (1 + (abs(hashtext(r.id::text)::bigint) + g.rank * 7919) % :users) || '@example.com'
) AS c
WHERE r.raw_text = 'Looking for someone to build an app with.';

INSERT INTO reports (id, reported_id, target, target_id, reason, snapshot, status, created_at)
SELECT gen_random_uuid(), u.id, 'profile', u.id, 'spam', '[]'::jsonb, 'open', now()
FROM users u WHERE u.email LIKE 'perf-%@example.com' AND abs(hashtext(u.email)::bigint) % 50 = 0;

ANALYZE;
"""

CASES: Final[dict[str, Filters]] = {
    "newest first (no filter)": Filters(),
    "search by name": Filters(q="person 4242"),
    "search by email": Filters(q="perf-99999"),
    "status filter (suspended)": Filters(status=UserStatus.SUSPENDED),
    "intent filter (mentor)": Filters(intent="mentor"),
    "flagged (open reports)": Filters(flagged=True),
    "search + intent": Filters(q="person 12", intent="explore"),
}


def _say(line: str = "") -> None:
    sys.stdout.write(line + "\n")


def _refuse_unless_local(url: str) -> None:
    host = make_url(url).host or ""
    if host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to run: the database host is {host!r}, not localhost.")


def _compiled(filters: Filters, dialect: Dialect) -> tuple[str, dict[str, Any]]:
    query = (
        list_query(filters).order_by(User.created_at.desc(), User.id.desc()).limit(PAGE_DEFAULT + 1)
    )
    compiled = query.compile(dialect=dialect)
    return str(compiled), dict(compiled.params)


def _time(connection: Connection, sql: str, params: dict[str, Any]) -> float:
    runs = []
    for _ in range(5):
        started = time.perf_counter()
        connection.exec_driver_sql(sql, params).fetchall()
        runs.append((time.perf_counter() - started) * 1000)
    return statistics.median(runs)


async def _time_overview() -> list[tuple[str, float]]:
    """The admin Overview (A4), built without its cache, for each range, and health."""
    settings = get_settings()
    async_engine = create_async_db_engine(settings)
    factory = create_session_factory(async_engine)
    slow: list[tuple[str, float]] = []
    try:
        for days in overview.RANGES:
            runs = []
            for _ in range(3):
                async with factory() as db:
                    started = time.perf_counter()
                    await overview.build(db, settings, days)
                    runs.append((time.perf_counter() - started) * 1000)
            median = statistics.median(runs)
            _say(f"## overview, {days} days (all its queries, uncached): median {median:.1f} ms")
            if median >= LIMIT_MS:
                slow.append((f"overview {days}", median))
        async with factory() as db:
            started = time.perf_counter()
            await overview.health(db, settings)
            took = (time.perf_counter() - started) * 1000
        _say(f"## health (uncached): {took:.1f} ms")
    finally:
        await async_engine.dispose()
    return slow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=100_000)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "")
    _refuse_unless_local(url)
    engine = create_engine(url)
    with engine.begin() as connection:
        existing = connection.scalar(
            text("SELECT count(*) FROM users WHERE email LIKE 'perf-%@example.com'")
        )
        if not existing:
            started = time.perf_counter()
            for statement in SEED.split(";\n"):
                if statement.strip():
                    connection.execute(text(statement), {"users": args.users})
            _say(f"Seeded {args.users} people in {time.perf_counter() - started:.1f} s")
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM users) AS users, "
                "(SELECT count(*) FROM matches) AS matches, "
                "(SELECT count(*) FROM reports WHERE status = 'open') AS open_reports"
            )
        ).one()
        _say(
            f"Rows: {counts.users} users, {counts.matches} matches, "
            f"{counts.open_reports} open reports\n"
        )

    slow = []
    with engine.connect() as connection:
        for name, filters in CASES.items():
            sql, params = _compiled(filters, engine.dialect)
            plan: list[str] = list(
                connection.exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS) " + sql, params).scalars()
            )
            median = _time(connection, sql, params)
            _say(f"## {name}: median {median:.1f} ms over 5 runs")
            _say("\n".join(plan))
            _say()
            if median >= LIMIT_MS:
                slow.append((name, median))
    engine.dispose()
    slow += asyncio.run(_time_overview())
    if slow:
        _say(f"Slower than {LIMIT_MS:.0f} ms: {slow}")
        return 1
    _say(f"Every query under {LIMIT_MS:.0f} ms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
