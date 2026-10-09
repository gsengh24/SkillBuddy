"""Reports and safety (A3). The only message text is ``AttachedMessage.body``: what a
reporter chose to send with their report. Everything user-written is plain data."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import APPEAL_TEXT_MAX_LENGTH, Appeal, Report, User

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]


class Person(BaseModel):
    id: uuid.UUID
    email: str
    status: str

    @classmethod
    def of(cls, user: User | None) -> Person | None:
        return cls(id=user.id, email=user.email, status=user.status) if user else None


class QueueItem(BaseModel):
    id: uuid.UUID
    status: Literal["open", "in_review", "resolved"]
    reason: str
    target: str = Field(description="What was reported: message, intro, profile, goal, note.")
    created_at: datetime
    decision: str | None
    reported: Person | None
    reporter: Person | None

    @classmethod
    def build(cls, report: Report, people: dict[uuid.UUID, User]) -> QueueItem:
        return cls(
            id=report.id,
            status=report.status,  # type: ignore[arg-type]  # CHECK-constrained column
            reason=report.reason,
            target=report.target,
            created_at=report.created_at,
            decision=report.decision,
            reported=Person.of(people.get(report.reported_id) if report.reported_id else None),
            reporter=Person.of(people.get(report.reporter_id) if report.reporter_id else None),
        )


class Queue(BaseModel):
    items: list[QueueItem] = Field(description="Oldest first.")
    next_cursor: str | None


class AttachedMessage(BaseModel):
    """A chat message the reporter chose to attach (or, for an intro, profile or pair-space
    report, a labelled part of what they reported). Nothing else from a chat is shown."""

    label: str | None = Field(description='Set for non-chat parts, e.g. "summary", "note".')
    sender: Literal["reporter", "reported"]
    body: str = Field(description="Plain text.")
    sent_at: datetime | None

    @classmethod
    def build(cls, item: dict[str, Any]) -> AttachedMessage:
        return cls(
            label=item.get("label"),
            sender=item["from"],
            body=item["body"],
            sent_at=item.get("sent_at"),
        )


class CaseOut(BaseModel):
    report: QueueItem
    details: str = Field(description="What the reporter wrote. Plain text.")
    attached: list[AttachedMessage]
    resolution_note: str
    resolved_at: datetime | None
    reported_history: dict[str, int] = Field(
        description="reports_against, reports_filed, times_blocked, upheld_reports."
    )
    reporter_history: dict[str, int]


class StartReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["dismiss", "warn", "suspend", "ban"]
    reason: Reason


class AppealOut(BaseModel):
    id: uuid.UUID
    person: Person | None
    against: str = Field(description='"suspended" or "banned".')
    appeal: str = Field(description="What they wrote. Plain text.")
    status: Literal["open", "upheld", "overturned"]
    created_at: datetime
    decided_at: datetime | None

    @classmethod
    def build(cls, appeal: Appeal, people: dict[uuid.UUID, User]) -> AppealOut:
        return cls(
            id=appeal.id,
            person=Person.of(people.get(appeal.user_id)),
            against=appeal.against,
            appeal=appeal.body,
            status=appeal.status,  # type: ignore[arg-type]  # CHECK-constrained column
            created_at=appeal.created_at,
            decided_at=appeal.decided_at,
        )


class AppealPage(BaseModel):
    items: list[AppealOut]
    next_cursor: str | None


class AppealDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["uphold", "overturn"]
    reason: Reason


class SafetyCounts(BaseModel):
    open: int = Field(description="Reports nobody has started on.")
    in_review: int
    open_appeals: int


class BlockedPerson(BaseModel):
    user_id: uuid.UUID
    email: str
    status: str
    times: int


class BlockStats(BaseModel):
    total: int
    last_30_days: int
    people_blocked: int = Field(description="Different people blocked by anyone, ever.")
    blocked_often: int = Field(description="People blocked by three or more others.")
    most_blocked: list[BlockedPerson] = Field(description="Last 30 days, most first (10).")


class AppealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, StringConstraints(min_length=10, max_length=300)]
    appeal: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=APPEAL_TEXT_MAX_LENGTH),
    ]


class AppealReceipt(BaseModel):
    created_at: datetime
