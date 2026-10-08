"""The admin Overview (A4): KPIs with the change on the previous period, the daily sign-up
series, the funnel, what needs attention, system health and recent admin activity.

Aggregates only, never message text. Each figure is one indexed query (created_at ranges;
BRIN on the big append-mostly tables). Results are cached in this process for 60 seconds
per range, so the page never adds load however often it is opened.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.status import ai_status
from app.core.config import Settings
from app.models import (
    AdminAuditEntry,
    Connection,
    DataExport,
    DataExportStatus,
    EmailLog,
    Intro,
    IntroStatus,
    Job,
    JobStatus,
    Match,
    MatchRequest,
    Message,
    Report,
    ReportStatus,
    User,
    UserStatus,
)
from app.services.email.budget import remaining

CACHE_SECONDS: Final = 60
RANGES: Final = (7, 30, 90)
EMAIL_JOBS: Final = (
    "send_login_code",
    "send_notification_email",
    "build_data_export",
    "send_safety_notice",
)
RECENT_ACTIVITY: Final = 6


@dataclass(frozen=True)
class Kpi:
    key: str
    value: float
    previous: float


@dataclass
class Overview:
    days: int
    generated_at: datetime
    kpis: list[Kpi]
    signups_by_day: list[tuple[date, int]]
    funnel: list[tuple[str, int]]
    attention: dict[str, int]
    activity: list[AdminAuditEntry] = field(default_factory=list)


async def _count_pair(
    db: AsyncSession, model: Any, column: Any, start: datetime, middle: datetime, *where: Any
) -> tuple[int, int]:
    """(this period, previous period) in one query over the two adjacent ranges."""
    row = (
        await db.execute(
            select(
                func.count().filter(column >= middle),
                func.count().filter(column < middle),
            )
            .select_from(model)
            .where(column >= start, *where)
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


async def build(db: AsyncSession, settings: Settings, days: int) -> Overview:
    now = datetime.now(UTC)
    middle = now - timedelta(days=days)
    start = middle - timedelta(days=days)
    signups = await _count_pair(db, User, User.created_at, start, middle)
    active = await _count_pair(db, User, User.last_login_at, start, middle)
    requests = await _count_pair(db, MatchRequest, MatchRequest.created_at, start, middle)
    matches = await _count_pair(db, Match, Match.created_at, start, middle)
    messages = await _count_pair(db, Message, Message.created_at, start, middle)
    intros_row = (
        await db.execute(
            select(
                func.count().filter(Intro.created_at >= middle),
                func.count().filter(
                    Intro.created_at >= middle, Intro.status == IntroStatus.ACCEPTED
                ),
                func.count().filter(Intro.created_at < middle),
                func.count().filter(
                    Intro.created_at < middle, Intro.status == IntroStatus.ACCEPTED
                ),
            ).where(Intro.created_at >= start)
        )
    ).one()
    sent_now, accepted_now, sent_before, accepted_before = (int(v or 0) for v in intros_row)
    connections_now = (await _count_pair(db, Connection, Connection.created_at, start, middle))[0]

    def rate(accepted: int, sent: int) -> float:
        return round(accepted / sent * 100, 1) if sent else 0.0

    kpis = [
        Kpi("new_signups", *signups),
        Kpi("active_users", *active),
        Kpi("new_requests", *requests),
        Kpi("matches_made", *matches),
        Kpi("intro_accept_rate", rate(accepted_now, sent_now), rate(accepted_before, sent_before)),
        Kpi("messages_sent", *messages),
    ]

    day = cast(func.timezone("UTC", User.created_at), Date)
    rows = await db.execute(
        select(day, func.count()).where(User.created_at >= middle).group_by(day)
    )
    by_day: dict[date, int] = {row[0]: int(row[1]) for row in rows}
    first = middle.date()
    series = [
        (first + timedelta(days=offset), int(by_day.get(first + timedelta(days=offset), 0)))
        for offset in range(days + 1)
    ]

    funnel = [
        ("requests", requests[0]),
        ("matches", matches[0]),
        ("intros_sent", sent_now),
        ("intros_accepted", accepted_now),
        ("chats_started", connections_now),
    ]

    attention_row = (
        await db.execute(
            select(
                select(func.count())
                .select_from(Report)
                .where(Report.status.in_([ReportStatus.OPEN, ReportStatus.IN_REVIEW]))
                .scalar_subquery(),
                select(func.count())
                .select_from(User)
                .where(User.status == UserStatus.PENDING)
                .scalar_subquery(),
                select(func.count())
                .select_from(DataExport)
                .where(DataExport.status == DataExportStatus.REQUESTED)
                .scalar_subquery(),
                select(func.count())
                .select_from(Job)
                .where(
                    Job.status == JobStatus.DEAD,
                    Job.kind.in_(EMAIL_JOBS),
                    Job.finished_at >= now - timedelta(days=7),
                )
                .scalar_subquery(),
            )
        )
    ).one()
    status = await ai_status(db, settings)
    degraded = sum(
        1
        for provider in status.providers
        if sum(v for k, v in provider.calls.items() if k != "ok") > provider.calls.get("ok", 0)
    )
    attention = {
        "open_reports": int(attention_row[0] or 0),
        "pending_applications": int(attention_row[1] or 0),
        "degraded_ai_providers": degraded,
        "due_data_requests": int(attention_row[2] or 0),
        "failed_emails": int(attention_row[3] or 0),
    }
    activity = list(
        await db.scalars(
            select(AdminAuditEntry)
            .order_by(AdminAuditEntry.created_at.desc(), AdminAuditEntry.id.desc())
            .limit(RECENT_ACTIVITY)
        )
    )
    return Overview(
        days=days,
        generated_at=now,
        kpis=kpis,
        signups_by_day=series,
        funnel=funnel,
        attention=attention,
        activity=activity,
    )


_cache: dict[int, tuple[float, Overview]] = {}


async def cached(db: AsyncSession, settings: Settings, days: int) -> Overview:
    now = time.monotonic()
    hit = _cache.get(days)
    if hit and hit[0] > now:
        return hit[1]
    overview = await build(db, settings, days)
    _cache[days] = (now + CACHE_SECONDS, overview)
    return overview


# --- health --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok", "warn" or "down"
    detail: str


async def health(db: AsyncSession, settings: Settings) -> list[Check]:
    """API, database, AI providers (from today's recorded calls; no provider is called)
    and email."""
    checks = [Check("api", "ok", "Answering")]
    started = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        took = (time.perf_counter() - started) * 1000
        checks.append(Check("database", "ok" if took < 500 else "warn", f"{took:.0f} ms"))
    except Exception:  # report the database as down rather than fail the page
        checks.append(Check("database", "down", "Not answering"))
        return checks
    status = await ai_status(db, settings)
    if not status.enabled:
        checks.append(Check("ai", "warn", "AI is switched off; the template answers"))
    for provider in status.providers:
        ok = provider.calls.get("ok", 0)
        failed = sum(v for k, v in provider.calls.items() if k != "ok")
        state = "ok" if failed <= ok else "warn"
        checks.append(Check(f"ai:{provider.name}", state, f"{ok} ok, {failed} failed today"))
    left = await remaining(db, settings)
    last = await db.scalar(select(func.max(EmailLog.created_at)))
    email_state = "ok" if left > settings.email_reserve_for_codes else "warn"
    detail = f"{left} of {settings.email_daily_cap} left today"
    if last:
        detail += f"; last sent {last:%Y-%m-%d %H:%M} UTC"
    checks.append(Check("email", email_state, detail))
    return checks


_health_cache: tuple[float, list[Check]] | None = None


async def cached_health(db: AsyncSession, settings: Settings) -> list[Check]:
    global _health_cache  # a one-minute cache for this process
    now = time.monotonic()
    if _health_cache and _health_cache[0] > now:
        return _health_cache[1]
    checks = await health(db, settings)
    _health_cache = (now + CACHE_SECONDS, checks)
    return checks
