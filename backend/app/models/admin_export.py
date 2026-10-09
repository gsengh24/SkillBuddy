"""CSV exports for admins (A9): the Users list and the audit log, built in the background.

The gzipped CSV is kept in the row until its link expires (24 hours), then dropped; the row
goes 30 days after it was asked for. Downloads need an admin session with the permission
for that export.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, LargeBinary, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


def _in(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class AdminExportKind(StrEnum):
    USERS = "users"
    AUDIT = "audit"


class AdminExportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class AdminExport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admin_exports"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in(AdminExportKind)})", name="kind_valid"),
        CheckConstraint(f"status IN ({_in(AdminExportStatus)})", name="status_valid"),
    )

    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default=AdminExportStatus.QUEUED, server_default=text("'queued'")
    )
    requested_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    ready_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    rows: Mapped[int | None]
    size_bytes: Mapped[int | None]
    # gzip of the CSV; null until ready and again once expired.
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
