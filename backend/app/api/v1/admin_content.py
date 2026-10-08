"""The admin Content moderation and Matching and AI pages (A7).

Content: everyone who may view users sees the queue; keep and remove need "Handle reports";
rule switches need "Settings and switches". Matching and AI: "AI and matching" (owners and
admins). Every change takes a reason and is audited."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.ai.status import ai_status
from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.api.v1.moderation import ProbeQueued
from app.jobs.queue import enqueue
from app.jobs.tasks import AI_PROBE
from app.models import ContentRule
from app.schemas.admin_content import (
    AIOverviewOut,
    ContentRulesOut,
    EvalsOut,
    FlagDecisionIn,
    FlagOut,
    FlagPage,
    ProviderOut,
    ProviderSwitchIn,
    QualityOut,
    RerunIn,
    RerunQueuedOut,
    RuleIn,
    RuleStateOut,
)
from app.schemas.errors import ErrorResponse
from app.services.admin import ai, content
from app.services.admin.permissions import Permission
from app.services.auth.rate_limit import RateLimiter
from app.services.matching.requests import DAY_SECONDS

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}}
_CONFLICT: dict[int | str, dict[str, Any]] = {HTTPStatus.CONFLICT.value: {"model": ErrorResponse}}
_LIMITED: dict[int | str, dict[str, Any]] = {
    HTTPStatus.TOO_MANY_REQUESTS.value: {"model": ErrorResponse}
}

router = APIRouter(prefix="/admin", tags=["admin"], responses=_ERRORS)

Viewer = Annotated[AdminContext, Depends(require_admin(Permission.VIEW_USERS))]
Moderator = Annotated[AdminContext, Depends(require_admin(Permission.HANDLE_REPORTS))]
SettingsManager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_SETTINGS))]
AIManager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_AI))]


# --- content moderation ----------------------------------------------------------------------


@router.get("/content/rules", summary="Automatic content rules and whether each is on")
async def get_rules(_: Viewer, db: DbDep) -> ContentRulesOut:
    found = await content.rules(db)
    return ContentRulesOut(rules=[RuleStateOut(key=key, on=on) for key, on in found.items()])


@router.post(
    "/content/rules/{rule}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Turn a content rule on or off",
    dependencies=[Depends(require_json)],
)
async def set_rule(
    rule: ContentRule, body: RuleIn, request: Request, admin: SettingsManager, db: DbDep
) -> None:
    """Rules only flag text for this queue; they never block or change what users see."""
    await content.set_rule(db, admin.who, rule, body.on, body.reason, client_ip(request))


@router.get("/content/flags", summary="Flagged text waiting for a decision, oldest first")
async def list_flags(
    _: Viewer,
    db: DbDep,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=content.PAGE_MAX)] = 20,
) -> FlagPage:
    rows, next_cursor = await content.queue(db, cursor=cursor, limit=limit)
    return FlagPage(items=[FlagOut.from_row(row) for row in rows], next_cursor=next_cursor)


@router.post(
    "/content/flags/{flag_id}/decide",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Keep the text, or remove it",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def decide_flag(
    flag_id: uuid.UUID, body: FlagDecisionIn, request: Request, admin: Moderator, db: DbDep
) -> None:
    """Remove clears that text (an empty bio, a closed request, an intro without a note) and
    sends the person an in-app notice naming the rule. 409 ``flag_already_decided``."""
    await content.decide(
        db,
        admin.who,
        flag_id,
        remove=body.decision == "remove",
        reason=body.reason,
        ip=client_ip(request),
    )


# --- matching and AI -------------------------------------------------------------------------


@router.get("/ai", summary="AI providers, quality numbers and the evaluation set")
async def get_ai(_: AIManager, db: DbDep, settings: SettingsDep) -> AIOverviewOut:
    status = await ai_status(db, settings)
    found = await ai.quality(db)
    return AIOverviewOut(
        llm_enabled=settings.ai_llm_enabled,
        providers=[
            ProviderOut(
                name=row.name,
                role=row.role,  # type: ignore[arg-type]  # "primary" or "fallback"
                on=row.on,
                status=row.status,  # type: ignore[arg-type]  # one of the four states
                p50_ms=row.p50_ms,
                p95_ms=row.p95_ms,
                calls_24h=row.calls_24h,
                error_rate=row.error_rate,
                cost_today=row.cost_today,
                cost_unit=row.cost_unit,
                daily_budget=row.daily_budget,
            )
            for row in await ai.providers(db, settings)
        ],
        fallbacks_today=status.fallbacks,
        quality=QualityOut(
            days=found.days,
            intros_sent=found.intros_sent,
            accept_rate=found.accept_rate,
            ignore_rate=found.ignore_rate,
            report_rate=found.report_rate,
        ),
        evals=EvalsOut(connected=ai.EVALS_CONNECTED, labelled=None, total=None, latest_score=None),
    )


@router.post(
    "/ai/providers",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Switch an AI provider on or off",
    dependencies=[Depends(require_json)],
    responses=_NOT_FOUND,
)
async def switch_provider(
    body: ProviderSwitchIn,
    request: Request,
    admin: AIManager,
    db: DbDep,
    settings: SettingsDep,
) -> None:
    """An off provider is skipped; the next one, or the rule-based fallback, answers."""
    await ai.set_provider(
        db, settings, admin.who, body.provider, body.on, body.reason, client_ip(request)
    )


@router.post(
    "/ai/probe",
    status_code=HTTPStatus.ACCEPTED,
    summary="Test the AI providers (fixed prompt, no user data)",
    responses=_LIMITED,
)
async def probe(
    request: Request, admin: AIManager, db: DbDep, settings: SettingsDep
) -> ProbeQueued:
    """The same background test as the moderation AI page (PR 66): one short fixed prompt to
    each provider on its own. Limited to AI_PROBES_PER_DAY per admin."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=DAY_SECONDS
    )
    await limiter.hit(f"ai-probe:{admin.who.user.id}", limit=settings.ai_probes_per_day)
    await enqueue(db, AI_PROBE)
    await db.commit()
    return ProbeQueued()


@router.post(
    "/ai/rerun",
    status_code=HTTPStatus.ACCEPTED,
    summary="Re-run matching for one person",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT, **_LIMITED},
)
async def rerun(
    body: RerunIn, request: Request, admin: AIManager, db: DbDep, settings: SettingsDep
) -> RerunQueuedOut:
    """Their newest open request is matched again in the background. 409 ``no_open_request``
    or ``request_has_intros``. At most 10 an hour per admin."""
    limiter = RateLimiter(
        request.app.state.session_factory, settings.secret_key, window_seconds=3600
    )
    await limiter.hit(f"ai-rerun:{admin.who.user.id}", limit=ai.RERUNS_PER_HOUR)
    request_id = await ai.rerun_matching(db, admin.who, body.email, body.reason, client_ip(request))
    return RerunQueuedOut(request_id=request_id)
