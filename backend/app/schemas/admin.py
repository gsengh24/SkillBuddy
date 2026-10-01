"""Response models for operator-only endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TableSize(BaseModel):
    name: str
    bytes: int


class StorageReport(BaseModel):
    status: Literal["ok", "warning", "critical"] = Field(
        description="warning at the warn threshold; critical pauses sign-ups and optional writes."
    )
    database_bytes: int
    limit_bytes: int
    used_percent: float
    warn_at_percent: int
    pause_at_percent: int
    largest_tables: list[TableSize]
    checked_at: datetime
