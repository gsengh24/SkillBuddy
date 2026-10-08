"""Reports and safety (A3): the queue, a case, decisions, appeals and block counts. Every
route goes through ``require_admin``; no route returns chat text except attached messages."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.models import AppealStatus, ReportDecision, ReportStatus
from app.schemas.admin_safety import (
    AppealDecisionIn,
    AppealOut,
    AppealPage,
    AttachedMessage,
    BlockStats,
    CaseOut,
    DecisionIn,
    Queue,
    QueueItem,
    StartReviewIn,
)
from app.schemas.errors import ErrorResponse
from app.schemas.reports import shown_messages
from app.services.admin import safety
from app.services.admin.permissions import Permission

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}
_CHANGE_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse},
    HTTPStatus.CONFLICT.value: {"model": ErrorResponse},
}

router = APIRouter(prefix="/admin/safety", tags=["admin"], responses=_ERRORS)

Viewer = Annotated[AdminContext, Depends(require_admin(Permission.VIEW_USERS))]
Reader = Annotated[AdminContext, Depends(require_admin(Permission.READ_REPORTED_MESSAGES))]
Handler = Annotated[AdminContext, Depends(require_admin(Permission.HANDLE_REPORTS))]
Sanctioner = Annotated[AdminContext, Depends(require_admin(Permission.SUSPEND_USERS))]


@router.get("/reports", summary="The report queue")
async def report_queue(
    _: Viewer,
    db: DbDep,
    status: ReportStatus = ReportStatus.OPEN,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=safety.PAGE_MAX)] = 25,
) -> Queue:
    """No message text here; open a case for what the reporter attached."""
    items, people, next_cursor = await safety.queue(db, status, cursor=cursor, limit=limit)
    return Queue(items=[QueueItem.build(item, people) for item in items], next_cursor=next_cursor)


@router.get(
    "/reports/{report_id}",
    summary="One case",
    responses={HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}},
)
async def report_case(report_id: uuid.UUID, _: Reader, db: DbDep) -> CaseOut:
    """The reported person, the reporter, the reason, the messages the reporter attached and
    both people's history counts. No other message text, and no chat view."""
    found = await safety.case(db, report_id)
    people = {u.id: u for u in (found.reporter, found.reported) if u is not None}
    return CaseOut(
        report=QueueItem.build(found.report, people),
        details=found.report.details,
        attached=[AttachedMessage.build(item) for item in shown_messages(found.report)],
        resolution_note=found.report.resolution_note,
        resolved_at=found.report.resolved_at,
        reported_history=found.reported_history,
        reporter_history=found.reporter_history,
    )


@router.post(
    "/reports/{report_id}/start-review",
    summary="Mark a report as in review",
    dependencies=[Depends(require_json)],
    responses=_CHANGE_ERRORS,
)
async def start_review(
    report_id: uuid.UUID, body: StartReviewIn, request: Request, admin: Handler, db: DbDep
) -> QueueItem:
    report = await safety.start_review(db, admin.who, report_id, body.reason, client_ip(request))
    return QueueItem.build(report, {})


@router.post(
    "/reports/{report_id}/decide",
    summary="Decide a report",
    dependencies=[Depends(require_json)],
    responses=_CHANGE_ERRORS,
)
async def decide(
    report_id: uuid.UUID,
    body: DecisionIn,
    request: Request,
    admin: Handler,
    db: DbDep,
    settings: SettingsDep,
) -> QueueItem:
    """Dismiss, warn, suspend for 7 days, or ban. The reporter gets an in-app notice (never
    the outcome); the reported person is emailed for a warning, suspension or ban."""
    report = await safety.decide(
        db,
        settings,
        admin.who,
        report_id,
        ReportDecision(body.decision),
        body.reason,
        client_ip(request),
    )
    return QueueItem.build(report, {})


@router.get("/appeals", summary="Appeals")
async def appeal_queue(
    _: Handler,
    db: DbDep,
    status: AppealStatus = AppealStatus.OPEN,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=safety.PAGE_MAX)] = 25,
) -> AppealPage:
    items, people, next_cursor = await safety.appeals(db, status, cursor=cursor, limit=limit)
    return AppealPage(
        items=[AppealOut.build(item, people) for item in items], next_cursor=next_cursor
    )


@router.post(
    "/appeals/{appeal_id}/decide",
    summary="Uphold or overturn an appeal",
    dependencies=[Depends(require_json)],
    responses=_CHANGE_ERRORS,
)
async def decide_appeal(
    appeal_id: uuid.UUID, body: AppealDecisionIn, request: Request, admin: Sanctioner, db: DbDep
) -> AppealOut:
    """Overturning lifts the suspension or ban. The person is emailed either way."""
    appeal = await safety.decide_appeal(
        db, admin.who, appeal_id, body.outcome == "overturn", body.reason, client_ip(request)
    )
    return AppealOut.build(appeal, {})


@router.get("/blocks", summary="Block counts")
async def blocks(_: Viewer, db: DbDep) -> BlockStats:
    """Aggregates only: totals and the most blocked people in the last 30 days."""
    return BlockStats.model_validate(await safety.block_stats(db))
