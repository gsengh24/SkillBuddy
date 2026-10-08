"""Requests and responses for the admin portal (ADR 0015)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import AUDIT_REASON_MAX_LENGTH, AUDIT_REASON_MIN_LENGTH, AdminAuditEntry

_REQUEST = ConfigDict(extra="forbid")

Role = Literal["owner", "admin", "moderator", "readonly"]
GrantableRole = Literal["admin", "moderator", "readonly"]
Reason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=AUDIT_REASON_MIN_LENGTH,
        max_length=AUDIT_REASON_MAX_LENGTH,
    ),
]
TwoStepCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=6, max_length=20),
]


class TwoStepStatusOut(BaseModel):
    role: Role
    two_step_enabled: bool = Field(
        description="False until the first code is confirmed: then set it up first."
    )


class TwoStepSetupOut(BaseModel):
    """Add this to an authenticator app. Shown once; the secret is stored encrypted."""

    secret: str = Field(description="Base32, for typing in by hand.")
    otpauth_uri: str = Field(description="An otpauth:// link for authenticator apps.")


class TwoStepCodeIn(BaseModel):
    model_config = _REQUEST

    code: TwoStepCode = Field(description="6 digits from the app, or a recovery code.")


class AdminSessionOut(BaseModel):
    expires_at: datetime = Field(description="Moves on with use; ends after 30 idle minutes.")
    recovery_codes: list[str] | None = Field(
        default=None,
        description="Only when two-step login was just turned on. Shown once: keep them safe.",
    )


class AdminMeOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: Role
    permissions: list[str]


class PermissionRow(BaseModel):
    permission: str
    label: str
    roles: list[Role] = Field(description="The roles that have it.")


class PermissionTable(BaseModel):
    roles: list[Role]
    rows: list[PermissionRow]


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str | None
    action: str
    target_type: str | None
    target_id: str | None
    reason: str | None = Field(description="Plain text written by the admin.")
    ip: str | None

    @classmethod
    def from_entry(cls, entry: AdminAuditEntry) -> AuditEntryOut:
        return cls(
            id=entry.id,
            created_at=entry.created_at,
            actor_id=entry.actor_id,
            actor_role=entry.actor_role,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            reason=entry.reason,
            ip=entry.ip,
        )


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    next_cursor: str | None = Field(description="Pass as `cursor` for older entries.")


class TeamMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: Role
    from_environment: bool = Field(description="Owners come from ADMIN_OWNER_EMAILS.")
    two_step_enabled: bool
    last_active_at: datetime | None = Field(description="Last admin session activity.")


class TeamOut(BaseModel):
    items: list[TeamMemberOut]


class GrantIn(BaseModel):
    model_config = _REQUEST

    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
    role: GrantableRole
    reason: Reason


class ReasonIn(BaseModel):
    model_config = _REQUEST

    reason: Reason
