"""Request and response models for reports (user side) and moderation (admin side)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import (
    REPORT_DETAILS_MAX_LENGTH,
    REPORT_NOTE_MAX_LENGTH,
    Report,
    ReportReason,
    ReportTarget,
)


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: ReportReason
    details: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=REPORT_DETAILS_MAX_LENGTH)
    ] = Field(default="", description="Optional: anything the moderator should know.")


class ReportReceipt(BaseModel):
    """All the reporter learns: the report was received."""

    id: uuid.UUID
    created_at: datetime


class ReportedMessage(BaseModel):
    """One part of the frozen copy: a chat message, or a labelled part of an intro or a
    profile (``label`` is then e.g. "request", "note", "summary", "offers", "name")."""

    id: uuid.UUID | None
    label: str | None
    sender: Literal["reporter", "reported"]
    body: str
    sent_at: datetime | None

    @classmethod
    def build(cls, item: dict[str, Any]) -> ReportedMessage:
        return cls(
            id=item.get("id"),
            label=item.get("label"),
            sender=item["from"],
            body=item["body"],
            sent_at=item.get("sent_at"),
        )


class ReportOut(BaseModel):
    """The moderator's view. ``messages`` is the frozen copy: for a message report, oldest
    first with the reported message last; for an intro or a profile, its labelled parts.
    Ids are null once that account or connection is deleted."""

    id: uuid.UUID
    reason: ReportReason
    details: str
    status: Literal["open", "resolved"]
    reporter_id: uuid.UUID | None
    reported_id: uuid.UUID | None
    reported_status: Literal["active", "suspended", "pending_deletion"] | None = Field(
        description="The reported account's status now; null once it is deleted."
    )
    connection_id: uuid.UUID | None
    target: ReportTarget
    target_id: uuid.UUID = Field(description="The message, the intro, or the person's id.")
    message_id: uuid.UUID | None = Field(description="Set for message reports only.")
    messages: list[ReportedMessage]
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str

    @classmethod
    def build(cls, report: Report, reported_status: str | None = None) -> ReportOut:
        return cls(
            id=report.id,
            reason=ReportReason(report.reason),
            details=report.details,
            status=report.status,  # type: ignore[arg-type]  # CHECK-constrained column
            reporter_id=report.reporter_id,
            reported_id=report.reported_id,
            reported_status=reported_status,  # type: ignore[arg-type]  # CHECK-constrained column
            connection_id=report.connection_id,
            target=ReportTarget(report.target),
            target_id=report.target_id,
            message_id=report.target_id if report.target == ReportTarget.MESSAGE else None,
            messages=[ReportedMessage.build(item) for item in report.snapshot],
            created_at=report.created_at,
            resolved_at=report.resolved_at,
            resolution_note=report.resolution_note,
        )


class ReportPage(BaseModel):
    items: list[ReportOut] = Field(description="Oldest first.")
    next_cursor: str | None


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=REPORT_NOTE_MAX_LENGTH)
    ] = Field(default="", description="What you did, for your own records.")
