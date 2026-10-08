"""Responses for "Download my data" (Prompt 12C)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import DataExport


class DataExportOut(BaseModel):
    id: uuid.UUID
    status: Literal["requested", "ready", "expired", "failed"] = Field(
        description=(
            "`requested`: being built; `ready`: the link was emailed; `expired`: the link ran "
            "out; `failed`: it couldn't be built or emailed, ask again."
        )
    )
    requested_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None = Field(description="When the emailed link stops working.")
    downloaded_at: datetime | None

    @classmethod
    def from_export(cls, export: DataExport) -> DataExportOut:
        return cls(
            id=export.id,
            status=export.status,  # type: ignore[arg-type]  # CHECK keeps it to these values
            requested_at=export.created_at,
            ready_at=export.ready_at,
            expires_at=export.expires_at,
            downloaded_at=export.downloaded_at,
        )


class DataExportList(BaseModel):
    items: list[DataExportOut] = Field(description="The latest requests, newest first.")
