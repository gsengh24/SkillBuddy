"""The admin Matching and AI page (A7): providers, quality numbers, the evaluation set and
re-running matching for one person. Built from the AI status counters (PR 66) and the AI
call log; no prompt or response text is ever read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import configured_providers
from app.ai.status import ai_status
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.jobs.queue import enqueue
from app.models import (
    AiCall,
    AppSetting,
    Intro,
    IntroStatus,
    Match,
    MatchRequest,
    Report,
    ReportTarget,
    RequestStatus,
    User,
)
from app.services import app_settings
from app.services.admin.core import AdminIdentity, record
from app.services.auth.codes import normalise_email

QUALITY_DAYS: Final = 30
LATENCY_HOURS: Final = 24
RERUNS_PER_HOUR: Final = 10


class ProviderNotFoundError(NotFoundError):
    code = "provider_not_found"
    default_message = "That AI provider isn't configured."


class RerunUserNotFoundError(NotFoundError):
    code = "user_not_found"
    default_message = "No account uses that email."


class NoOpenRequestError(ConflictError):
    code = "no_open_request"
    default_message = "This person has no open match request to re-run."


class RequestHasIntrosError(ConflictError):
    code = "request_has_intros"
    default_message = (
        "Intros were already sent from this request's matches; re-running would remove them."
    )


@dataclass(frozen=True)
class ProviderRow:
    name: str
    role: str  # "primary" or "fallback"
    on: bool
    status: str  # "ok", "degraded", "idle" or "off"
    p50_ms: int | None
    p95_ms: int | None
    calls_24h: int
    error_rate: float | None
    cost_today: int
    cost_unit: str
    daily_budget: int


async def providers(db: AsyncSession, settings: Settings) -> list[ProviderRow]:
    status = {p.name: p for p in (await ai_status(db, settings)).providers}
    since = datetime.now(UTC) - timedelta(hours=LATENCY_HOURS)
    stats = {
        name: (p50, p95, total, errors)
        for name, p50, p95, total, errors in (
            await db.execute(
                select(
                    AiCall.provider,
                    func.percentile_cont(0.5).within_group(AiCall.duration_ms),
                    func.percentile_cont(0.95).within_group(AiCall.duration_ms),
                    func.count(),
                    func.count().filter(AiCall.outcome != "ok"),
                )
                .where(AiCall.created_at >= since, AiCall.kind != "probe")
                .group_by(AiCall.provider)
            )
        ).tuples()
    }
    rows: list[ProviderRow] = []
    for index, configured in enumerate(configured_providers(settings)):
        on = await app_settings.switch(db, f"{app_settings.PROVIDER_PREFIX}{configured.name}", True)
        p50, p95, total, errors = stats.get(configured.name, (None, None, 0, 0))
        today = status.get(configured.name)
        ok = today.calls.get("ok", 0) if today else 0
        failed = sum(v for k, v in today.calls.items() if k != "ok") if today else 0
        if not on:
            state = "off"
        elif ok + failed == 0:
            state = "idle"
        else:
            state = "degraded" if failed > ok else "ok"
        rows.append(
            ProviderRow(
                name=configured.name,
                role="primary" if index == 0 else "fallback",
                on=on,
                status=state,
                p50_ms=round(p50) if p50 is not None else None,
                p95_ms=round(p95) if p95 is not None else None,
                calls_24h=int(total),
                error_rate=round(int(errors) / int(total), 3) if total else None,
                cost_today=today.used_today if today else 0,
                cost_unit=configured.unit,
                daily_budget=configured.daily_budget,
            )
        )
    return rows


async def set_provider(
    db: AsyncSession,
    settings: Settings,
    actor: AdminIdentity,
    name: str,
    on: bool,
    reason: str,
    ip: str | None,
) -> None:
    if name not in {p.name for p in configured_providers(settings)}:
        raise ProviderNotFoundError
    key = f"{app_settings.PROVIDER_PREFIX}{name}"
    await db.execute(
        insert(AppSetting)
        .values(key=key, value=on, updated_by=actor.user.id)
        .on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={"value": on, "updated_by": actor.user.id, "updated_at": datetime.now(UTC)},
        )
    )
    record(
        db,
        actor,
        "ai.provider_on" if on else "ai.provider_off",
        target_type="ai_provider",
        target_id=name[:64],
        reason=reason,
        ip=ip,
    )
    await db.commit()
    app_settings.cache.invalidate()


@dataclass(frozen=True)
class Quality:
    days: int
    intros_sent: int
    accept_rate: float | None
    ignore_rate: float | None
    report_rate: float | None


async def quality(db: AsyncSession) -> Quality:
    """Intros sent in the last 30 days: accepted, left unanswered (expired), reported."""
    since = datetime.now(UTC) - timedelta(days=QUALITY_DAYS)
    sent, accepted, ignored = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Intro.status == IntroStatus.ACCEPTED),
                func.count().filter(Intro.status == IntroStatus.EXPIRED),
            ).where(Intro.created_at >= since)
        )
    ).one()
    reported = await db.scalar(
        select(func.count(func.distinct(Report.target_id))).where(
            Report.target == ReportTarget.INTRO,
            Report.target_id.in_(select(Intro.id).where(Intro.created_at >= since)),
        )
    )

    def rate(part: int | None) -> float | None:
        return round(int(part or 0) / int(sent), 3) if sent else None

    return Quality(
        days=QUALITY_DAYS,
        intros_sent=int(sent),
        accept_rate=rate(accepted),
        ignore_rate=rate(ignored),
        report_rate=rate(reported),
    )


async def rerun_matching(
    db: AsyncSession, actor: AdminIdentity, raw_email: str, reason: str, ip: str | None
) -> uuid.UUID:
    """Queue the person's newest open match request again (in the background). Refused
    when intros were sent from its matches: re-running replaces the matches."""
    from app.jobs.tasks import MATCH_REQUEST  # the job module imports services

    user = await db.scalar(select(User).where(User.email == normalise_email(raw_email)))
    if user is None:
        raise RerunUserNotFoundError
    request = await db.scalar(
        select(MatchRequest)
        .where(
            MatchRequest.user_id == user.id,
            MatchRequest.status.in_((RequestStatus.PENDING, RequestStatus.READY)),
        )
        .order_by(MatchRequest.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if request is None:
        raise NoOpenRequestError
    with_intros = await db.scalar(
        select(func.count())
        .select_from(Intro)
        .join(Match, Match.id == Intro.match_id)
        .where(Match.request_id == request.id)
    )
    if with_intros:
        raise RequestHasIntrosError
    request.status = RequestStatus.PENDING
    await enqueue(db, MATCH_REQUEST, {"request_id": str(request.id)})
    record(
        db,
        actor,
        "ai.rerun_matching",
        target_type="user",
        target_id=user.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    return request.id


# The evaluation set lives in backend/evals, which the API image doesn't contain (the
# Dockerfile copies only app/ and migrations/), so the page shows it as not connected.
EVALS_CONNECTED: Final = False
