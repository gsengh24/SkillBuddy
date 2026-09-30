"""The single error envelope returned by every failing API response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable, machine-readable error code, e.g. 'not_found'.")
    message: str = Field(description="Human-readable explanation; safe to show to users.")
    request_id: str | None = Field(description="Correlates the response with server logs.")
    details: list[dict[str, Any]] | None = Field(
        default=None, description="Optional structured context, e.g. field validation errors."
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail
