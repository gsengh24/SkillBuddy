"""Request and response models for reports (user side) and moderation (admin side)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import (
    MAX_ATTACHED_MESSAGES,
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


class PersonReportIn(ReportIn):
    """Reporting someone, optionally from a chat with them."""

    message_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=MAX_ATTACHED_MESSAGES,
        description="Up to 5 messages of your chat with them to send with the report. Only "
        "these are copied; the team sees no other message text.",
    )


def shown_messages(report: Report) -> list[dict[str, Any]]:
    """What the team may see of a report's copy (A3): the messages the reporter attached
    (for a message report, the reported message itself) and the labelled parts of an intro,
    a profile or a pair-space entry. Reports filed before A3 also hold earlier messages as
    context; those are never shown."""
    return [
        item
        for item in report.snapshot
        if item.get("label")
        or item.get("attached")
        or (report.target == ReportTarget.MESSAGE and item.get("id") == str(report.target_id))
    ]


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
    status: Literal["open", "in_review", "resolved"]
    reporter_id: uuid.UUID | None
    reported_id: uuid.UUID | None
    reported_status: (
        Literal["active", "paused", "pending", "suspended", "banned", "pending_deletion"] | None
    ) = Field(description="The reported account's status now; null once it is deleted.")
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
            messages=[ReportedMessage.build(item) for item in shown_messages(report)],
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
