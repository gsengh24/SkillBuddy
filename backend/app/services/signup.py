"""Who may create an account (A5): the signup mode, invite codes, approved applications and
the allowed and blocked email domains.

Checked only when a sign-in would create an account, never for people who already have
one. With nothing configured, signups are open to any domain, as before. The sign-in
allow-list and block list in the server settings (ADR 0011) still apply to everyone.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Final

from sqlalchemy import exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApplicationStatus,
    AppSetting,
    DomainKind,
    InviteCode,
    SignupApplication,
    SignupDomain,
    SignupMode,
)
from app.models.signup import INVITE_CODE_MAX_LENGTH, INVITE_CODE_MIN_LENGTH
from app.services.auth.errors import (
    EmailNotAllowedError,
    InvalidInviteCodeError,
    InviteRequiredError,
    SignupsClosedError,
)
from app.services.auth.policy import email_domain

SIGNUP_MODE_KEY: Final = "signup_mode"
# Labels, letters and digits with inner hyphens, at least one dot: "example.edu".
DOMAIN_PATTERN: Final = re.compile(
    r"^(?=.{3,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"
)
INVITE_CODE_PATTERN: Final = re.compile(
    rf"^[A-Z0-9-]{{{INVITE_CODE_MIN_LENGTH},{INVITE_CODE_MAX_LENGTH}}}$"
)
# No 0/O or 1/I/L, so a code read aloud or copied by hand still works.
_CODE_ALPHABET: Final = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def normalise_domain(raw: str) -> str | None:
    """``"@Example.EDU "`` -> ``"example.edu"``; None when it isn't a domain."""
    domain = raw.strip().lower().removeprefix("@")
    return domain if DOMAIN_PATTERN.match(domain) else None


def normalise_invite_code(raw: str | None) -> str | None:
    """Upper case, no spaces; None when empty or not a possible code."""
    if raw is None:
        return None
    code = raw.strip().upper()
    return code if INVITE_CODE_PATTERN.match(code) else None


def generate_invite_code(length: int = 8) -> str:
    return "CYN-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


async def signup_mode(db: AsyncSession) -> SignupMode:
    """Read fresh each time: a change applies to the very next sign-up."""
    value = await db.scalar(select(AppSetting.value).where(AppSetting.key == SIGNUP_MODE_KEY))
    try:
        return SignupMode(value) if value is not None else SignupMode.OPEN
    except ValueError:
        return SignupMode.OPEN


async def domain_allowed(db: AsyncSession, email: str) -> bool:
    """Blocked domains never; otherwise any domain when the allow list is empty."""
    domain = email_domain(email)
    blocked, any_allowed, allowed = (
        await db.execute(
            select(
                exists().where(
                    SignupDomain.kind == DomainKind.BLOCKED, SignupDomain.domain == domain
                ),
                exists().where(SignupDomain.kind == DomainKind.ALLOWED),
                exists().where(
                    SignupDomain.kind == DomainKind.ALLOWED, SignupDomain.domain == domain
                ),
            )
        )
    ).one()
    return not blocked and (allowed or not any_allowed)


async def _use_invite_code(db: AsyncSession, email: str, code: str, now: datetime) -> bool:
    """Count one use of a live code, in the caller's transaction (it commits with the new
    account). An application's code works only for that application's address."""
    used = await db.scalar(
        update(InviteCode)
        .where(
            InviteCode.code == code,
            InviteCode.revoked_at.is_(None),
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now),
            InviteCode.uses < InviteCode.max_uses,
            or_(
                InviteCode.application_id.is_(None),
                InviteCode.application_id.in_(
                    select(SignupApplication.id).where(SignupApplication.email == email)
                ),
            ),
        )
        .values(uses=InviteCode.uses + 1)
        .returning(InviteCode.id)
        .execution_options(synchronize_session=False)
    )
    return used is not None


async def ensure_can_create_account(
    db: AsyncSession, email: str, invite_code: str | None, now: datetime
) -> None:
    """Raise unless ``email`` (normalised) may create an account now.

    - blocked domain, or not on a non-empty allow list: ``email_not_allowed``;
    - closed: ``signups_closed`` (invite codes don't override it);
    - invite only: an approved application for the address, or a live invite code
      (one use is counted); otherwise ``invite_required`` or ``invalid_invite_code``.
    """
    if not await domain_allowed(db, email):
        raise EmailNotAllowedError
    mode = await signup_mode(db)
    if mode is SignupMode.OPEN:
        return
    if mode is SignupMode.CLOSED:
        raise SignupsClosedError
    approved = await db.scalar(
        select(
            exists().where(
                SignupApplication.email == email,
                SignupApplication.status == ApplicationStatus.APPROVED,
            )
        )
    )
    if approved:
        return
    code = normalise_invite_code(invite_code)
    if invite_code is None or not invite_code.strip():
        raise InviteRequiredError
    if code is None or not await _use_invite_code(db, email, code, now):
        raise InvalidInviteCodeError
