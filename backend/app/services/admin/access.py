"""The admin Signup and access page (A5): signup mode, approval queue, invite codes and
email domains. Every change takes a reason and writes its audit entry in the same
transaction (``record``); the mode applies to the very next sign-up.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.jobs.queue import enqueue
from app.models import (
    ApplicationStatus,
    AppSetting,
    DomainKind,
    InviteCode,
    SignupApplication,
    SignupDomain,
    SignupMode,
    User,
)
from app.services import signup
from app.services.admin.core import AdminIdentity, record
from app.services.cursors import decode_cursor, encode

PAGE_MAX: Final = 50
INVITE_NEXT: Final = 10
# How long an approved application's invite code works.
APPLICATION_CODE_DAYS: Final = 14
# Domain lists are short by design; this keeps the page and the check small.
MAX_DOMAINS_PER_LIST: Final = 200
MAX_CODE_DAYS: Final = 365


class ApplicationNotFoundError(NotFoundError):
    code = "application_not_found"
    default_message = "That application doesn't exist any more."


class ApplicationAlreadyDecidedError(ConflictError):
    code = "application_already_decided"
    default_message = "That application has already been decided."


class InviteCodeNotFoundError(NotFoundError):
    code = "invite_code_not_found"
    default_message = "That invite code doesn't exist."


class InviteCodeTakenError(ConflictError):
    code = "invite_code_taken"
    default_message = "That code is already in use. Choose another."


class InviteCodeAlreadyRevokedError(ConflictError):
    code = "invite_code_revoked"
    default_message = "That code is already revoked."


class InvalidInviteCodeFormatError(ConflictError):
    code = "invalid_invite_code_format"
    default_message = "Codes are 4 to 32 letters, digits or hyphens."


class InvalidDomainError(ConflictError):
    code = "invalid_domain"
    default_message = "Enter a domain like example.edu."


class DomainAlreadyListedError(ConflictError):
    code = "domain_already_listed"
    default_message = "That domain is already on the list."


class DomainListFullError(ConflictError):
    code = "domain_list_full"
    default_message = f"A list can hold at most {MAX_DOMAINS_PER_LIST} domains."


class DomainNotListedError(NotFoundError):
    code = "domain_not_listed"
    default_message = "That domain isn't on the list."


# --- reading -------------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessSummary:
    mode: SignupMode
    waitlist: int
    allowed_domains: list[str]
    blocked_domains: list[str]


async def summary(db: AsyncSession) -> AccessSummary:
    mode = await signup.signup_mode(db)
    waitlist = await db.scalar(
        select(func.count())
        .select_from(SignupApplication)
        .where(SignupApplication.status == ApplicationStatus.PENDING)
    )
    domains = (
        await db.execute(
            select(SignupDomain.kind, SignupDomain.domain).order_by(SignupDomain.domain)
        )
    ).all()
    return AccessSummary(
        mode=mode,
        waitlist=int(waitlist or 0),
        allowed_domains=[d for kind, d in domains if kind == DomainKind.ALLOWED],
        blocked_domains=[d for kind, d in domains if kind == DomainKind.BLOCKED],
    )


async def pending_applications(
    db: AsyncSession, *, cursor: str | None, limit: int
) -> tuple[list[SignupApplication], str | None]:
    """The approval queue, oldest first (keyset on created_at, id)."""
    query = select(SignupApplication).where(SignupApplication.status == ApplicationStatus.PENDING)
    if cursor:
        created_at, application_id = decode_cursor(cursor)
        query = query.where(
            tuple_(SignupApplication.created_at, SignupApplication.id)
            > (created_at, application_id)
        )
    size = min(limit, PAGE_MAX)
    rows = list(
        await db.scalars(
            query.order_by(SignupApplication.created_at, SignupApplication.id).limit(size + 1)
        )
    )
    next_cursor = encode(rows[size - 1].created_at, rows[size - 1].id) if len(rows) > size else None
    return rows[:size], next_cursor


@dataclass(frozen=True)
class CodeRow:
    code: InviteCode
    created_by_email: str | None


async def invite_codes(
    db: AsyncSession, *, cursor: str | None, limit: int
) -> tuple[list[CodeRow], str | None]:
    """Shareable codes, newest first. Approved applications' one-use codes are not listed."""
    query = (
        select(InviteCode, User.email)
        .outerjoin(User, User.id == InviteCode.created_by)
        .where(InviteCode.application_id.is_(None))
    )
    if cursor:
        created_at, code_id = decode_cursor(cursor)
        query = query.where(tuple_(InviteCode.created_at, InviteCode.id) < (created_at, code_id))
    size = min(limit, PAGE_MAX)
    rows = (
        await db.execute(
            query.order_by(InviteCode.created_at.desc(), InviteCode.id.desc()).limit(size + 1)
        )
    ).all()
    items = [CodeRow(code=code, created_by_email=email) for code, email in rows[:size]]
    last = rows[size - 1][0] if len(rows) > size else None
    return items, encode(last.created_at, last.id) if last is not None else None


# --- changing ------------------------------------------------------------------------------


async def set_mode(
    db: AsyncSession, actor: AdminIdentity, mode: SignupMode, reason: str, ip: str | None
) -> SignupMode:
    now = datetime.now(UTC)
    await db.execute(
        insert(AppSetting)
        .values(key=signup.SIGNUP_MODE_KEY, value=mode.value, updated_by=actor.user.id)
        .on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={"value": mode.value, "updated_by": actor.user.id, "updated_at": now},
        )
    )
    record(
        db,
        actor,
        "signup.mode_changed",
        target_type="setting",
        target_id=mode.value,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    return mode


async def _approve(
    db: AsyncSession, actor: AdminIdentity, application: SignupApplication, now: datetime
) -> None:
    """Approve, make the one-use code for the address, and queue the invite email."""
    from app.jobs.tasks import SEND_INVITE  # the job module imports services

    application.status = ApplicationStatus.APPROVED
    application.decided_at = now
    application.decided_by = actor.user.id
    code = InviteCode(
        code=signup.generate_invite_code(),
        max_uses=1,
        expires_at=now + timedelta(days=APPLICATION_CODE_DAYS),
        created_by=actor.user.id,
        application_id=application.id,
    )
    db.add(code)
    await db.flush()
    await enqueue(db, SEND_INVITE, {"invite_code_id": str(code.id)})


async def decide(
    db: AsyncSession,
    actor: AdminIdentity,
    application_id: uuid.UUID,
    *,
    approve: bool,
    reason: str,
    ip: str | None,
) -> SignupApplication:
    application = await db.get(SignupApplication, application_id, with_for_update=True)
    if application is None:
        raise ApplicationNotFoundError
    if application.status != ApplicationStatus.PENDING:
        raise ApplicationAlreadyDecidedError
    now = datetime.now(UTC)
    if approve:
        await _approve(db, actor, application, now)
    else:
        application.status = ApplicationStatus.REJECTED
        application.decided_at = now
        application.decided_by = actor.user.id
    record(
        db,
        actor,
        "signup.application_approved" if approve else "signup.application_rejected",
        target_type="application",
        target_id=application.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    return application


async def invite_next(db: AsyncSession, actor: AdminIdentity, reason: str, ip: str | None) -> int:
    """Approve the oldest pending applications (up to 10), each with its own audit entry."""
    oldest = list(
        await db.scalars(
            select(SignupApplication)
            .where(SignupApplication.status == ApplicationStatus.PENDING)
            .order_by(SignupApplication.created_at, SignupApplication.id)
            .limit(INVITE_NEXT)
            .with_for_update(skip_locked=True)
        )
    )
    now = datetime.now(UTC)
    for application in oldest:
        await _approve(db, actor, application, now)
        record(
            db,
            actor,
            "signup.application_approved",
            target_type="application",
            target_id=application.id,
            reason=reason,
            ip=ip,
        )
    await db.commit()
    return len(oldest)


async def create_code(
    db: AsyncSession,
    actor: AdminIdentity,
    *,
    code: str | None,
    max_uses: int,
    expires_in_days: int | None,
    reason: str,
    ip: str | None,
) -> CodeRow:
    """A shareable code; ``code`` is chosen by the admin or generated."""
    chosen = signup.normalise_invite_code(code) if code else signup.generate_invite_code()
    if chosen is None:
        raise InvalidInviteCodeFormatError
    now = datetime.now(UTC)
    invite = InviteCode(
        code=chosen,
        max_uses=max_uses,
        expires_at=now + timedelta(days=expires_in_days) if expires_in_days else None,
        created_by=actor.user.id,
    )
    db.add(invite)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise InviteCodeTakenError from None
    record(
        db,
        actor,
        "signup.invite_code_created",
        target_type="invite_code",
        target_id=invite.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(invite)
    return CodeRow(code=invite, created_by_email=actor.user.email)


async def revoke_code(
    db: AsyncSession, actor: AdminIdentity, code_id: uuid.UUID, reason: str, ip: str | None
) -> None:
    """The code stops working; people who already joined with it are not affected."""
    invite = await db.get(InviteCode, code_id, with_for_update=True)
    if invite is None or invite.application_id is not None:
        raise InviteCodeNotFoundError
    if invite.revoked_at is not None:
        raise InviteCodeAlreadyRevokedError
    invite.revoked_at = datetime.now(UTC)
    record(
        db,
        actor,
        "signup.invite_code_revoked",
        target_type="invite_code",
        target_id=invite.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()


async def add_domain(
    db: AsyncSession,
    actor: AdminIdentity,
    kind: DomainKind,
    raw_domain: str,
    reason: str,
    ip: str | None,
) -> str:
    domain = signup.normalise_domain(raw_domain)
    if domain is None:
        raise InvalidDomainError
    listed = await db.scalar(
        select(func.count()).select_from(SignupDomain).where(SignupDomain.kind == kind)
    )
    if int(listed or 0) >= MAX_DOMAINS_PER_LIST:
        raise DomainListFullError
    added = await db.scalar(
        insert(SignupDomain)
        .values(kind=kind.value, domain=domain, created_by=actor.user.id)
        .on_conflict_do_nothing(index_elements=[SignupDomain.kind, SignupDomain.domain])
        .returning(SignupDomain.id)
    )
    if added is None:
        await db.rollback()
        raise DomainAlreadyListedError
    record(
        db,
        actor,
        f"signup.domain_{kind.value}_added",
        target_type="domain",
        target_id=domain[:64],  # the audit column holds 64 characters
        reason=reason,
        ip=ip,
    )
    await db.commit()
    return domain


async def remove_domain(
    db: AsyncSession,
    actor: AdminIdentity,
    kind: DomainKind,
    raw_domain: str,
    reason: str,
    ip: str | None,
) -> None:
    domain = signup.normalise_domain(raw_domain)
    if domain is None:
        raise DomainNotListedError
    found = await db.scalar(
        select(SignupDomain).where(SignupDomain.kind == kind, SignupDomain.domain == domain)
    )
    if found is None:
        raise DomainNotListedError
    await db.delete(found)
    record(
        db,
        actor,
        f"signup.domain_{kind.value}_removed",
        target_type="domain",
        target_id=domain[:64],  # the audit column holds 64 characters
        reason=reason,
        ip=ip,
    )
    await db.commit()
