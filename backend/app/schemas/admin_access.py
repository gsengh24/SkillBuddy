"""Requests and responses for the admin Signup and access page (A5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import ApplicationSource, SignupApplication, SignupMode
from app.models.signup import (
    DOMAIN_MAX_LENGTH,
    INVITE_CODE_MAX_LENGTH,
    INVITE_MAX_USES,
)
from app.schemas.admin_portal import Reason
from app.services.admin.access import MAX_CODE_DAYS, CodeRow

_REQUEST = ConfigDict(extra="forbid")

Domain = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=DOMAIN_MAX_LENGTH + 1)
]


class AccessOut(BaseModel):
    mode: SignupMode
    waitlist: int = Field(description="Applications waiting for a decision.")
    allowed_domains: list[str] = Field(description="Empty: any domain may sign up.")
    blocked_domains: list[str]


class ModeIn(BaseModel):
    model_config = _REQUEST

    mode: SignupMode
    reason: Reason


class ApplicationOut(BaseModel):
    id: uuid.UUID
    email: str
    source: ApplicationSource
    created_at: datetime

    @classmethod
    def from_application(cls, application: SignupApplication) -> ApplicationOut:
        return cls(
            id=application.id,
            email=application.email,
            source=ApplicationSource(application.source),
            created_at=application.created_at,
        )


class ApplicationPage(BaseModel):
    items: list[ApplicationOut]
    next_cursor: str | None


class ApplicationDecisionIn(BaseModel):
    model_config = _REQUEST

    decision: Literal["approve", "reject"]
    reason: Reason


class InvitedOut(BaseModel):
    invited: int = Field(description="How many applications were approved (at most 10).")


class InviteCodeOut(BaseModel):
    id: uuid.UUID
    code: str
    uses: int
    max_uses: int
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    created_by: str | None = Field(description="The creating admin's email, if still known.")
    status: Literal["active", "used_up", "expired", "revoked"]

    @classmethod
    def from_row(cls, row: CodeRow, now: datetime) -> InviteCodeOut:
        code = row.code
        status: Literal["active", "used_up", "expired", "revoked"] = "active"
        if code.revoked_at is not None:
            status = "revoked"
        elif code.uses >= code.max_uses:
            status = "used_up"
        elif code.expires_at is not None and code.expires_at <= now:
            status = "expired"
        return cls(
            id=code.id,
            code=code.code,
            uses=code.uses,
            max_uses=code.max_uses,
            expires_at=code.expires_at,
            revoked_at=code.revoked_at,
            created_at=code.created_at,
            created_by=row.created_by_email,
            status=status,
        )


class InviteCodePage(BaseModel):
    items: list[InviteCodeOut]
    next_cursor: str | None


class InviteCodeIn(BaseModel):
    model_config = _REQUEST

    code: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, max_length=INVITE_CODE_MAX_LENGTH),
        ]
        | None
    ) = Field(
        default=None,
        description="4 to 32 letters, digits or hyphens (stored upper case). Empty: generated.",
    )
    max_uses: int = Field(ge=1, le=INVITE_MAX_USES)
    expires_in_days: int | None = Field(
        default=None, ge=1, le=MAX_CODE_DAYS, description="Empty: never expires."
    )
    reason: Reason


class DomainIn(BaseModel):
    model_config = _REQUEST

    domain: Domain
    reason: Reason


class DomainOut(BaseModel):
    domain: str
