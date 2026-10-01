"""Append-only security audit log (``auth_events``)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AuthEvent, AuthEventType
from app.models.auth import IP_MAX_LENGTH, USER_AGENT_MAX_LENGTH
from app.services.auth.codes import email_hash


@dataclass(frozen=True)
class ClientInfo:
    """Where a request came from, capped to the column sizes (storage rules)."""

    ip: str | None
    user_agent: str | None

    @classmethod
    def build(cls, ip: str | None, user_agent: str | None) -> ClientInfo:
        return cls(
            ip=ip[:IP_MAX_LENGTH] if ip else None,
            user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else None,
        )


def record_event(
    db: AsyncSession,
    settings: Settings,
    event_type: AuthEventType,
    *,
    client: ClientInfo | None = None,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the current transaction (committed by the caller)."""
    db.add(
        AuthEvent(
            user_id=user_id,
            event_type=event_type,
            email_hash=email_hash(settings, email) if email else None,
            ip=client.ip if client else None,
            user_agent=client.user_agent if client else None,
            detail=detail or {},
        )
    )
