"""Response models for the health endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "fail"]


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = Field(description="Product name, from the APP_NAME setting.")
    version: str
    environment: str


class DependencyCheck(BaseModel):
    status: CheckStatus
    latency_ms: float
    detail: str | None = Field(
        default=None, description="Short, non-sensitive reason when the check fails."
    )


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, DependencyCheck]
