"""The admin Overview and health (A4). Counts only."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.admin_portal import AuditEntryOut


class KpiOut(BaseModel):
    key: str = Field(
        description="new_signups, active_users, new_requests, matches_made, intro_accept_rate "
        "(percent) or messages_sent (a count; never their text)."
    )
    value: float
    previous: float = Field(description="The same length of time just before.")


class DayCount(BaseModel):
    day: date
    count: int


class FunnelStep(BaseModel):
    step: str
    count: int


class OverviewOut(BaseModel):
    days: int
    generated_at: datetime = Field(description="Cached for up to 60 seconds.")
    kpis: list[KpiOut]
    signups_by_day: list[DayCount]
    funnel: list[FunnelStep]
    attention: dict[str, int] = Field(
        description="open_reports, pending_applications, degraded_ai_providers, "
        "due_data_requests, failed_emails."
    )
    activity: list[AuditEntryOut] = Field(description="The latest admin actions.")


class HealthCheck(BaseModel):
    name: str
    status: str = Field(description='"ok", "warn" or "down".')
    detail: str


class HealthOut(BaseModel):
    checks: list[HealthCheck]
    checked_at: datetime
