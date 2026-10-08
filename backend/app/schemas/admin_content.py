"""Requests and responses for the admin Content moderation and Matching and AI pages (A7).
User-written text is returned as plain data, never as HTML."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import EMAIL_MAX_LENGTH, ContentRule, FlaggedItem
from app.schemas.admin_portal import Reason
from app.services.admin.content import QueueRow

_REQUEST = ConfigDict(extra="forbid")


class RuleStateOut(BaseModel):
    key: ContentRule
    on: bool


class ContentRulesOut(BaseModel):
    rules: list[RuleStateOut]


class RuleIn(BaseModel):
    model_config = _REQUEST

    on: bool
    reason: Reason


class FlagOut(BaseModel):
    id: uuid.UUID
    rule: ContentRule
    item_type: FlaggedItem
    item_id: uuid.UUID
    user_id: uuid.UUID
    email: str | None
    flagged_text: str | None = Field(
        description="The text as it is now (plain text); null if the item no longer exists."
    )
    created_at: datetime

    @classmethod
    def from_row(cls, row: QueueRow) -> FlagOut:
        flag = row.flag
        return cls(
            id=flag.id,
            rule=ContentRule(flag.rule),
            item_type=FlaggedItem(flag.item_type),
            item_id=flag.item_id,
            user_id=flag.user_id,
            email=row.email,
            flagged_text=row.text,
            created_at=flag.created_at,
        )


class FlagPage(BaseModel):
    items: list[FlagOut]
    next_cursor: str | None


class FlagDecisionIn(BaseModel):
    model_config = _REQUEST

    decision: Literal["keep", "remove"]
    reason: Reason


class ProviderOut(BaseModel):
    name: str
    role: Literal["primary", "fallback"]
    on: bool
    status: Literal["ok", "degraded", "idle", "off"]
    p50_ms: int | None = Field(description="Median call time, last 24 hours.")
    p95_ms: int | None
    calls_24h: int
    error_rate: float | None = Field(description="Failed calls / all calls, last 24 hours.")
    cost_today: int
    cost_unit: str
    daily_budget: int


class QualityOut(BaseModel):
    days: int
    intros_sent: int
    accept_rate: float | None
    ignore_rate: float | None = Field(description="Intros that expired unanswered.")
    report_rate: float | None


class EvalsOut(BaseModel):
    connected: bool = Field(description="False: the evaluation set isn't available to the API.")
    labelled: int | None
    total: int | None
    latest_score: float | None


class AIOverviewOut(BaseModel):
    llm_enabled: bool = Field(description="The server kill switch (AI_LLM_ENABLED).")
    providers: list[ProviderOut]
    fallbacks_today: dict[str, int]
    quality: QualityOut
    evals: EvalsOut


class ProviderSwitchIn(BaseModel):
    model_config = _REQUEST

    provider: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    on: bool
    reason: Reason


class RerunIn(BaseModel):
    model_config = _REQUEST

    email: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=EMAIL_MAX_LENGTH)
    ]
    reason: Reason


class RerunQueuedOut(BaseModel):
    request_id: uuid.UUID
    status: Literal["queued"] = "queued"
