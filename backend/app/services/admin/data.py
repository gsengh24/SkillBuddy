"""The admin Data and compliance page (A9): data requests, retention, consent and CSV
exports of the Users list and the audit log (built in the background)."""

from __future__ import annotations

import csv
import gzip
import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import Executable, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.jobs.queue import enqueue
from app.models import (
    AdminAccount,
    AdminAuditEntry,
    AdminExport,
    AdminExportKind,
    AdminExportStatus,
    DataExport,
    DataExportStatus,
    User,
    UserStatus,
)
from app.services.admin.core import AdminIdentity, record, require, role_of
from app.services.admin.permissions import Permission
from app.services.auth.retention import delete_accounts

# Answer data requests within this many days of the request (the page shows the deadline).
DEADLINE_DAYS: Final = 30
LIST_MAX: Final = 50
EXPORT_LINK_HOURS: Final = 24
# Who may download each CSV: the audit log is for owners, like the Team and audit page.
EXPORT_PERMISSION: Final = {
    AdminExportKind.USERS: Permission.DELETE_DATA,
    AdminExportKind.AUDIT: Permission.MANAGE_ADMINS,
}


class DataRequestNotFoundError(NotFoundError):
    code = "data_request_not_found"
    default_message = "That request doesn't exist any more."


class CannotProcessError(ConflictError):
    code = "cannot_process"
    default_message = "This request can't be processed now (it's done, or not waiting)."


class CannotDeleteAdminError(ConflictError):
    code = "cannot_act_on_admin"
    default_message = "Admin accounts, including your own, are managed on the Team page."


class AdminExportNotFoundError(NotFoundError):
    code = "admin_export_not_found"
    default_message = "That export doesn't exist, isn't ready, or its link has expired."


class ExportAlreadyRunningError(ConflictError):
    code = "export_already_running"
    default_message = "An export of this kind is already being built. Wait for it to finish."


# --- data requests -----------------------------------------------------------------------


@dataclass(frozen=True)
class ExportRequest:
    export: DataExport
    email: str | None


async def export_requests(db: AsyncSession) -> list[ExportRequest]:
    """ "Download my data" requests, newest first (rows are kept 90 days)."""
    rows = (
        await db.execute(
            select(DataExport, User.email)
            .outerjoin(User, User.id == DataExport.user_id)
            .order_by(DataExport.created_at.desc())
            .limit(LIST_MAX)
        )
    ).all()
    return [ExportRequest(export=export, email=email) for export, email in rows]


async def deletion_requests(db: AsyncSession) -> list[User]:
    """Accounts waiting for deletion, oldest request first."""
    return list(
        await db.scalars(
            select(User)
            .where(User.status == UserStatus.PENDING_DELETION)
            .order_by(User.deleted_at)
            .limit(LIST_MAX)
        )
    )


async def process_export(
    db: AsyncSession, actor: AdminIdentity, export_id: uuid.UUID, reason: str, ip: str | None
) -> None:
    """Build and email a waiting or failed export now (the same job as from the You page)."""
    from app.jobs.tasks import BUILD_DATA_EXPORT  # the job module imports services

    export = await db.get(DataExport, export_id, with_for_update=True)
    if export is None:
        raise DataRequestNotFoundError
    if export.status not in (DataExportStatus.REQUESTED, DataExportStatus.FAILED):
        raise CannotProcessError
    export.status = DataExportStatus.REQUESTED
    await enqueue(db, BUILD_DATA_EXPORT, {"export_id": str(export.id)})
    record(
        db,
        actor,
        "data.export_processed",
        target_type="data_export",
        target_id=export.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()


async def process_deletion(
    db: AsyncSession,
    settings: Settings,
    actor: AdminIdentity,
    user_id: uuid.UUID,
    reason: str,
    ip: str | None,
) -> None:
    """Delete an account that asked to be deleted now, instead of at the end of its grace
    period: the same permanent deletion the daily job does."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise DataRequestNotFoundError
    if user.status != UserStatus.PENDING_DELETION:
        raise CannotProcessError
    if role_of(settings, user, await db.get(AdminAccount, user.id)) is not None:
        raise CannotDeleteAdminError
    record(
        db,
        actor,
        "data.deletion_processed",
        target_type="user",
        target_id=user.id,
        reason=reason,
        ip=ip,
    )
    await delete_accounts(db, settings, [user.id])
    await db.commit()


# --- retention and consent ---------------------------------------------------------------


def retention_rules(settings: Settings) -> list[tuple[str, str]]:
    """What the code removes and when, from the running settings. Nothing here is aspirational:
    each line is a scheduled or lazy deletion that exists."""
    s = settings
    return [
        ("Sign-in codes", f"Deleted once expired ({s.otp_ttl_minutes} minutes)"),
        (
            "Sessions",
            f"End after {s.session_idle_days} idle days or {s.session_max_days} days; then deleted",
        ),
        ("Sign-in events", f"{s.auth_event_retention_days} days"),
        (
            "Deleted accounts",
            f"Permanently deleted {s.account_deletion_grace_days} days after the request",
        ),
        ("Chat messages", f"{s.message_retention_days} days after sending"),
        ("Match requests and matches", f"{s.match_request_retention_days} days"),
        ("Notifications", f"{s.notification_retention_days} days"),
        ("Pair spaces", f"{s.space_retention_days} days after the connection ends"),
        ("Reports and decided appeals", f"{s.report_retention_days} days after the decision"),
        ("Moderator actions", f"{s.moderation_log_retention_days} days"),
        ("Content flags", "Decided: 90 days after the decision; open: 180 days"),
        ("Signup applications", "Decided: 90 days after the decision; waiting: 180 days"),
        (
            "Data downloads",
            f"File: {s.data_export_link_hours} hours; request: {s.data_export_retention_days} days",
        ),
        ("Admin CSV exports", f"File: {EXPORT_LINK_HOURS} hours; request: 30 days"),
        ("Email send log", "30 days"),
        ("Email counts (for the daily cap)", f"{s.email_log_retention_days} days"),
        ("AI call log", "30 days"),
        (
            "Background jobs",
            f"Done: {s.job_succeeded_retention_days} days; "
            f"failed: {s.job_dead_retention_days} days",
        ),
        ("Banners", "90 days after they end"),
        ("Admin audit log", "Kept without a time limit (append-only)"),
    ]


@dataclass(frozen=True)
class Consent:
    terms_version: str
    total: int
    current: int
    older: int


async def consent(db: AsyncSession, settings: Settings) -> Consent:
    """Accounts (not being deleted) on the current TERMS_VERSION, and on an older one."""
    total, current = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(User.terms_version == settings.terms_version),
            ).where(User.status != UserStatus.PENDING_DELETION)
        )
    ).one()
    return Consent(
        terms_version=settings.terms_version,
        total=int(total),
        current=int(current),
        older=int(total) - int(current),
    )


# --- CSV exports ---------------------------------------------------------------------------


async def exports(db: AsyncSession) -> list[AdminExport]:
    return list(
        await db.scalars(select(AdminExport).order_by(AdminExport.created_at.desc()).limit(20))
    )


async def request_export(
    db: AsyncSession, actor: AdminIdentity, kind: AdminExportKind, ip: str | None
) -> AdminExport:
    """Queue a CSV export; the background job builds it (never on the request path)."""
    from app.jobs.tasks import BUILD_ADMIN_EXPORT

    require(actor, EXPORT_PERMISSION[kind])
    running = await db.scalar(
        select(func.count())
        .select_from(AdminExport)
        .where(
            AdminExport.kind == kind.value,
            AdminExport.status.in_((AdminExportStatus.QUEUED, AdminExportStatus.RUNNING)),
        )
    )
    if running:
        raise ExportAlreadyRunningError
    export = AdminExport(kind=kind.value, requested_by=actor.user.id)
    db.add(export)
    await db.flush()
    await enqueue(db, BUILD_ADMIN_EXPORT, {"export_id": str(export.id)})
    record(
        db,
        actor,
        f"data.csv_export_{kind.value}",
        target_type="admin_export",
        target_id=export.id,
        ip=ip,
    )
    await db.commit()
    await db.refresh(export)
    return export


def _cell(value: object) -> str:
    """One CSV cell. Text that a spreadsheet would run as a formula gets a leading quote."""
    text = "" if value is None else value.isoformat() if isinstance(value, datetime) else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


async def _write_rows(
    db: AsyncSession, write: Callable[[list[str]], object], header: list[str], query: Executable
) -> int:
    """Stream the rows (server-side cursor), so a big table is never all in memory."""
    write(header)
    count = 0
    result = await db.stream(query)
    async for row in result:
        write([_cell(value) for value in row])
        count += 1
    return count


USERS_HEADER: Final = ["id", "email", "status", "created_at", "last_login_at", "terms_version"]
AUDIT_HEADER: Final = [
    "created_at",
    "actor_id",
    "actor_role",
    "action",
    "target_type",
    "target_id",
    "reason",
    "ip",
]


def _query(kind: AdminExportKind) -> Executable:
    if kind is AdminExportKind.USERS:
        # Account fields only: never profile text, requests or messages.
        return select(
            User.id,
            User.email,
            User.status,
            User.created_at,
            User.last_login_at,
            User.terms_version,
        ).order_by(User.created_at, User.id)
    return select(
        AdminAuditEntry.created_at,
        AdminAuditEntry.actor_id,
        AdminAuditEntry.actor_role,
        AdminAuditEntry.action,
        AdminAuditEntry.target_type,
        AdminAuditEntry.target_id,
        AdminAuditEntry.reason,
        AdminAuditEntry.ip,
    ).order_by(AdminAuditEntry.created_at, AdminAuditEntry.id)


async def build_export(db: AsyncSession, export_id: uuid.UUID) -> None:
    """The job: write the CSV, gzip it and keep it in the row for 24 hours. Runs again
    safely (only a queued export is built)."""
    export = await db.get(AdminExport, export_id, with_for_update=True)
    if export is None or export.status != AdminExportStatus.QUEUED:
        return
    export.status = AdminExportStatus.RUNNING
    await db.commit()
    kind = AdminExportKind(export.kind)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = USERS_HEADER if kind is AdminExportKind.USERS else AUDIT_HEADER
    try:
        rows = await _write_rows(db, writer.writerow, header, _query(kind))
    except Exception:
        await db.rollback()
        export = await db.get_one(AdminExport, export_id)
        export.status = AdminExportStatus.FAILED
        await db.commit()
        raise
    payload = gzip.compress(buffer.getvalue().encode())
    now = datetime.now(UTC)
    export = await db.get_one(AdminExport, export_id, with_for_update=True)
    export.status = AdminExportStatus.READY
    export.payload = payload
    export.size_bytes = len(payload)
    export.rows = rows
    export.ready_at = now
    export.expires_at = now + timedelta(hours=EXPORT_LINK_HOURS)
    await db.commit()


async def download(
    db: AsyncSession, actor: AdminIdentity, export_id: uuid.UUID, ip: str | None
) -> tuple[str, bytes]:
    """(file name, gzipped CSV) of a ready export whose link hasn't expired."""
    export = await db.get(AdminExport, export_id)
    now = datetime.now(UTC)
    if (
        export is None
        or export.status != AdminExportStatus.READY
        or export.payload is None
        or (export.expires_at is not None and export.expires_at <= now)
    ):
        raise AdminExportNotFoundError
    kind = AdminExportKind(export.kind)
    require(actor, EXPORT_PERMISSION[kind])
    record(
        db,
        actor,
        f"data.csv_downloaded_{kind.value}",
        target_type="admin_export",
        target_id=export.id,
        ip=ip,
    )
    await db.commit()
    stamp = (export.ready_at or now).strftime("%Y-%m-%d")
    return f"{kind.value}-{stamp}.csv.gz", export.payload
