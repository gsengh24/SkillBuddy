"""Requests to download your own data (Prompt 12C).

A request is a row; a background job builds the file (gzipped JSON, kept in the row for a
short window), then emails a link with a one-time-shown token. Only the token's hash is
stored. The file is dropped when the link expires; the row is kept a while longer so the
admin Data page can list requests, then deleted (docs/storage-budget.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.auth import DIGEST_LENGTH


class DataExportStatus(StrEnum):
    REQUESTED = "requested"
    READY = "ready"
    # The link ran out; the file is gone.
    EXPIRED = "expired"
    # It couldn't be built or emailed; the person can ask again.
    FAILED = "failed"


class DataExport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_exports"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{status.value}'" for status in DataExportStatus) + ")",
            name="status_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=DataExportStatus.REQUESTED,
        server_default=text(f"'{DataExportStatus.REQUESTED}'"),
    )
    # When it was asked for.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    ready_at: Mapped[datetime | None]
    # When the link stops working and the file is dropped.
    expires_at: Mapped[datetime | None]
    downloaded_at: Mapped[datetime | None]
    token_hash: Mapped[str | None] = mapped_column(String(DIGEST_LENGTH), unique=True)
    # gzip of the JSON file; null once expired.
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    size_bytes: Mapped[int | None]
