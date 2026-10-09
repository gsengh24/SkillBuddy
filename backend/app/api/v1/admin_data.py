"""The admin Data and compliance page (A9). Owners and admins ("Delete users and data");
the audit log CSV is for owners only. Processing a request takes a reason and is audited."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.models import AdminExportKind
from app.schemas.admin_data import (
    AdminExportOut,
    ConsentOut,
    DataPageOut,
    DeletionRequestOut,
    ExportRequestOut,
    RetentionRuleOut,
)
from app.schemas.admin_portal import ReasonIn
from app.schemas.errors import ErrorResponse
from app.services.admin import data
from app.services.admin.permissions import Permission

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}}
_CONFLICT: dict[int | str, dict[str, Any]] = {HTTPStatus.CONFLICT.value: {"model": ErrorResponse}}

router = APIRouter(prefix="/admin/data", tags=["admin"], responses=_ERRORS)

DataManager = Annotated[AdminContext, Depends(require_admin(Permission.DELETE_DATA))]


@router.get("", summary="Data requests, retention, consent and CSV exports")
async def get_data(_: DataManager, db: DbDep, settings: SettingsDep) -> DataPageOut:
    found = await data.consent(db, settings)
    return DataPageOut(
        exports_requested=[
            ExportRequestOut.from_request(item) for item in await data.export_requests(db)
        ],
        deletions_requested=[
            DeletionRequestOut.from_user(user) for user in await data.deletion_requests(db)
        ],
        retention=[
            RetentionRuleOut(data=what, rule=rule) for what, rule in data.retention_rules(settings)
        ],
        consent=ConsentOut(
            terms_version=found.terms_version,
            total=found.total,
            current=found.current,
            older=found.older,
        ),
        csv_exports=[AdminExportOut.from_export(e) for e in await data.exports(db)],
    )


@router.post(
    "/exports/{export_id}/process",
    status_code=HTTPStatus.ACCEPTED,
    summary="Build and email a data download now",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def process_export(
    export_id: uuid.UUID, body: ReasonIn, request: Request, admin: DataManager, db: DbDep
) -> None:
    """The same background job as from the You page. 409 ``cannot_process`` when it's
    already ready or expired."""
    await data.process_export(db, admin.who, export_id, body.reason, client_ip(request))


@router.post(
    "/deletions/{user_id}/process",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete an account that asked to be deleted, now",
    dependencies=[Depends(require_json)],
    responses={**_NOT_FOUND, **_CONFLICT},
)
async def process_deletion(
    user_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    admin: DataManager,
    db: DbDep,
    settings: SettingsDep,
) -> None:
    """Permanent, as at the end of the grace period. 409 ``cannot_process`` unless the
    account is waiting for deletion; ``cannot_act_on_admin`` for admin accounts."""
    await data.process_deletion(db, settings, admin.who, user_id, body.reason, client_ip(request))


@router.post(
    "/csv/{kind}",
    status_code=HTTPStatus.ACCEPTED,
    summary="Start a CSV export (Users or the audit log)",
    responses=_CONFLICT,
)
async def start_csv(
    kind: AdminExportKind, request: Request, admin: DataManager, db: DbDep
) -> AdminExportOut:
    """Built in the background; ready within a minute or two. The audit log is for owners.
    409 ``export_already_running``."""
    export = await data.request_export(db, admin.who, kind, client_ip(request))
    return AdminExportOut.from_export(export)


@router.get(
    "/csv/{export_id}/download",
    summary="Download a ready CSV export (gzip)",
    response_class=Response,
    responses={
        **_NOT_FOUND,
        HTTPStatus.OK.value: {"content": {"application/gzip": {}}},
    },
)
async def download_csv(
    export_id: uuid.UUID, request: Request, admin: DataManager, db: DbDep
) -> Response:
    """Works for 24 hours after it is ready. Each download is audited."""
    filename, payload = await data.download(db, admin.who, export_id, client_ip(request))
    return Response(
        content=payload,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
