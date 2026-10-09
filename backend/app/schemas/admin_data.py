"""Responses for the admin Data and compliance page (A9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from app.models import AdminExport, AdminExportKind, AdminExportStatus, DataExportStatus, User
from app.services.admin.data import DEADLINE_DAYS, ExportRequest


class ExportRequestOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None
    status: DataExportStatus
    requested_at: datetime
    deadline: datetime = Field(description=f"{DEADLINE_DAYS} days after the request.")
    ready_at: datetime | None
    processable: bool = Field(description="Waiting or failed: Process builds and emails it.")

    @classmethod
    def from_request(cls, item: ExportRequest) -> ExportRequestOut:
        export = item.export
        status = DataExportStatus(export.status)
        return cls(
            id=export.id,
            user_id=export.user_id,
            email=item.email,
            status=status,
            requested_at=export.created_at,
            deadline=export.created_at + timedelta(days=DEADLINE_DAYS),
            ready_at=export.ready_at,
            processable=status in (DataExportStatus.REQUESTED, DataExportStatus.FAILED),
        )


class DeletionRequestOut(BaseModel):
    user_id: uuid.UUID
    email: str
    requested_at: datetime | None
    deadline: datetime | None = Field(description=f"{DEADLINE_DAYS} days after the request.")
    scheduled_for: datetime | None = Field(description="When the daily job deletes it anyway.")

    @classmethod
    def from_user(cls, user: User) -> DeletionRequestOut:
        return cls(
            user_id=user.id,
            email=user.email,
            requested_at=user.deleted_at,
            deadline=user.deleted_at + timedelta(days=DEADLINE_DAYS) if user.deleted_at else None,
            scheduled_for=user.deletion_scheduled_for,
        )


class RetentionRuleOut(BaseModel):
    data: str
    rule: str


class ConsentOut(BaseModel):
    terms_version: str
    total: int = Field(description="Accounts, not counting those being deleted.")
    current: int
    older: int


class AdminExportOut(BaseModel):
    id: uuid.UUID
    kind: AdminExportKind
    status: AdminExportStatus
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    rows: int | None
    size_bytes: int | None

    @classmethod
    def from_export(cls, export: AdminExport) -> AdminExportOut:
        return cls(
            id=export.id,
            kind=AdminExportKind(export.kind),
            status=AdminExportStatus(export.status),
            created_at=export.created_at,
            ready_at=export.ready_at,
            expires_at=export.expires_at,
            rows=export.rows,
            size_bytes=export.size_bytes,
        )


class DataPageOut(BaseModel):
    exports_requested: list[ExportRequestOut] = Field(description='"Download my data" requests.')
    deletions_requested: list[DeletionRequestOut]
    retention: list[RetentionRuleOut]
    consent: ConsentOut
    csv_exports: list[AdminExportOut]
