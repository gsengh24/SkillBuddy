"""Requests and responses for the admin Communication page and the public banner (A8).
Banner text is plain text; clients must never render it as HTML."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import BANNER_MAX_LENGTH, Banner, BannerKind, EmailSend, EmailSendStatus
from app.schemas.admin_portal import Reason
from app.services.banners import ActiveBanner

_REQUEST = ConfigDict(extra="forbid")


class BannerOut(BaseModel):
    id: uuid.UUID
    announcement: str = Field(description="Plain text, at most 160 characters.")
    kind: BannerKind
    ends_at: datetime | None

    @classmethod
    def from_active(cls, banner: ActiveBanner) -> BannerOut:
        return cls(
            id=banner.id, announcement=banner.message, kind=banner.kind, ends_at=banner.ends_at
        )


class CurrentBannerOut(BaseModel):
    """The banner to show at the top of the app, or null. Clients remember dismissals
    themselves (by ``id``). Cached for up to 60 seconds."""

    banner: BannerOut | None


class AdminBannerOut(BaseModel):
    id: uuid.UUID
    announcement: str
    kind: BannerKind
    created_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None
    live: bool

    @classmethod
    def from_banner(cls, banner: Banner, now: datetime) -> AdminBannerOut:
        live = banner.ended_at is None and (banner.ends_at is None or banner.ends_at > now)
        return cls(
            id=banner.id,
            announcement=banner.message,
            kind=BannerKind(banner.kind),
            created_at=banner.created_at,
            ends_at=banner.ends_at,
            ended_at=banner.ended_at,
            live=live,
        )


class BannerIn(BaseModel):
    model_config = _REQUEST

    announcement: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=BANNER_MAX_LENGTH),
    ]
    kind: BannerKind
    ends_at: datetime | None = Field(default=None, description="Empty: until ended by hand.")
    reason: Reason


class TemplateOut(BaseModel):
    key: str
    name: str
    sent_when: str


class CommsOut(BaseModel):
    banners: list[AdminBannerOut] = Field(description="The 20 newest, live or not.")
    templates: list[TemplateOut]


class EmailSendOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    to: str
    template: str
    status: EmailSendStatus
    error: str | None = Field(description="A short summary; never a token or key.")
    retryable: bool
    retried_at: datetime | None

    @classmethod
    def from_send(cls, send: EmailSend) -> EmailSendOut:
        return cls(
            id=send.id,
            created_at=send.created_at,
            to=send.to_email,
            template=send.template,
            status=EmailSendStatus(send.status),
            error=send.error,
            retryable=send.status == EmailSendStatus.FAILED
            and send.retried_at is None
            and send.retry_kind is not None,
            retried_at=send.retried_at,
        )


class EmailSendPage(BaseModel):
    items: list[EmailSendOut]
    next_cursor: str | None
