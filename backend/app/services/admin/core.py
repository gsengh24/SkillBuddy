"""Admin roles, two-step login, admin sessions, audit log and the team (ADR 0015).

Owners come from ADMIN_OWNER_EMAILS; everyone else's role is a row in admin_accounts. An
admin's requests need their normal session and a second, short admin session that only a
TOTP or recovery code opens. Every change is written to the audit log in the same
transaction as the change itself, by ``record``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import constant_time_equals, generate_token, hash_token
from app.models import (
    AUDIT_REASON_MIN_LENGTH,
    AdminAccount,
    AdminAuditEntry,
    AdminRecoveryCode,
    AdminRole,
    AdminSession,
    User,
)
from app.services.admin.permissions import Permission, allows
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode

logger = logging.getLogger(__name__)

RECOVERY_CODE_COUNT: Final = 10
# Refresh last_seen_at at most this often, to avoid a write on every admin request.
SLIDE_INTERVAL: Final = timedelta(seconds=60)
_MAX_TOKEN_LENGTH: Final = 128
AUDIT_PAGE_MAX: Final = 50


# --- errors --------------------------------------------------------------------------------


class NotAdminError(PermissionDeniedError):
    code = "not_admin"
    default_message = "This page is for the team that runs the service."


class AdminPermissionError(PermissionDeniedError):
    code = "admin_permission_denied"
    default_message = "Your admin role doesn't allow this."


class TwoStepRequiredError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "admin_two_step_required"
    default_message = "Enter the code from your authenticator app to continue."


class TwoStepAlreadyEnabledError(ConflictError):
    code = "two_step_already_enabled"
    default_message = "Two-step login is already set up for this account."


class TwoStepNotSetUpError(ConflictError):
    code = "two_step_not_set_up"
    default_message = "Set up two-step login first."


class InvalidTwoStepCodeError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "invalid_two_step_code"
    default_message = "That code didn't work. Check your authenticator app and try again."


class AdminUserNotFoundError(NotFoundError):
    code = "user_not_found"
    default_message = "No account uses that email. They need to sign up first."


class CannotChangeOwnerError(ConflictError):
    code = "cannot_change_owner"
    default_message = "Owners are set on the server (ADMIN_OWNER_EMAILS), not here."


class NotAnAdminError(NotFoundError):
    code = "admin_not_found"
    default_message = "That person isn't an admin."


class ReasonRequiredError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "reason_required"
    default_message = f"Give a reason of at least {AUDIT_REASON_MIN_LENGTH} characters."


# --- who is an admin -----------------------------------------------------------------------


def role_of(settings: Settings, user: User, account: AdminAccount | None) -> AdminRole | None:
    """The person's admin role, or None. Owners only from ADMIN_OWNER_EMAILS."""
    if user.email.lower() in settings.admin_owner_emails:
        return AdminRole.OWNER
    if account is not None and account.role:
        return AdminRole(account.role)
    return None


@dataclass(frozen=True)
class AdminIdentity:
    """An admin by role, before or after the second step."""

    user: User
    role: AdminRole
    account: AdminAccount | None

    @property
    def two_step_enabled(self) -> bool:
        return self.account is not None and self.account.two_step_enabled_at is not None


async def identity(db: AsyncSession, settings: Settings, user: User) -> AdminIdentity | None:
    account = await db.get(AdminAccount, user.id)
    role = role_of(settings, user, account)
    return AdminIdentity(user=user, role=role, account=account) if role else None


def require(identity_: AdminIdentity, permission: Permission) -> None:
    if not allows(identity_.role, permission):
        raise AdminPermissionError


# --- the audit log -------------------------------------------------------------------------


def record(
    db: AsyncSession,
    actor: AdminIdentity | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    reason: str | None = None,
    ip: str | None = None,
) -> AdminAuditEntry:
    """Add an audit entry to the caller's transaction (it commits with the action, or not
    at all). Changes must pass a reason; sign-ins and the like pass none."""
    if reason is not None and len(reason.strip()) < AUDIT_REASON_MIN_LENGTH:
        raise ReasonRequiredError
    entry = AdminAuditEntry(
        actor_id=actor.user.id if actor else None,
        actor_role=actor.role.value if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        reason=reason.strip() if reason else None,
        ip=ip,
    )
    db.add(entry)
    return entry


async def audit_page(
    db: AsyncSession,
    *,
    cursor: str | None,
    limit: int,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
    target_id: str | None = None,
) -> tuple[list[AdminAuditEntry], str | None]:
    """Newest first, keyset paging on (created_at, id); filters use indexed columns."""
    query = select(AdminAuditEntry)
    if action:
        query = query.where(AdminAuditEntry.action == action)
    if actor_id:
        query = query.where(AdminAuditEntry.actor_id == actor_id)
    if target_id:
        query = query.where(AdminAuditEntry.target_id == target_id)
    if cursor:
        created_at, entry_id = decode_cursor(cursor)
        query = query.where(
            tuple_(AdminAuditEntry.created_at, AdminAuditEntry.id) < (created_at, entry_id)
        )
    rows = list(
        await db.scalars(
            query.order_by(AdminAuditEntry.created_at.desc(), AdminAuditEntry.id.desc()).limit(
                min(limit, AUDIT_PAGE_MAX) + 1
            )
        )
    )
    more = len(rows) > min(limit, AUDIT_PAGE_MAX)
    items = rows[: min(limit, AUDIT_PAGE_MAX)]
    return items, encode(items[-1].created_at, items[-1].id) if more and items else None


# --- two-step login ------------------------------------------------------------------------


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(b"admin-totp:" + settings.secret_key.get_secret_value().encode())
    return Fernet(base64.urlsafe_b64encode(digest.digest()))


def _secret(settings: Settings, account: AdminAccount) -> str:
    if not account.totp_secret:
        raise TwoStepNotSetUpError
    try:
        return _fernet(settings).decrypt(account.totp_secret.encode()).decode()
    except InvalidToken as error:  # SECRET_KEY changed: set up again
        raise TwoStepNotSetUpError from error


def _new_recovery_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(10)).decode().lower()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


def _normalise(code: str) -> str:
    return code.strip().replace(" ", "").lower()


@dataclass(frozen=True)
class TwoStepSetup:
    secret: str
    otpauth_uri: str


@dataclass(frozen=True)
class AdminSignIn:
    token: str
    session: AdminSession
    recovery_codes: list[str] | None = None


class AdminService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        self._limiter = limiter

    async def start_two_step(self, who: AdminIdentity) -> TwoStepSetup:
        """A new secret to add to an authenticator app. Replaces an unconfirmed one."""
        if who.two_step_enabled:
            raise TwoStepAlreadyEnabledError
        secret = pyotp.random_base32()
        account = who.account or AdminAccount(user_id=who.user.id, role=None)
        account.totp_secret = _fernet(self._settings).encrypt(secret.encode()).decode()
        self._db.add(account)
        await self._db.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=who.user.email, issuer_name=self._settings.app_name
        )
        return TwoStepSetup(secret=secret, otpauth_uri=uri)

    async def _check_totp(self, account: AdminAccount, code: str) -> bool:
        """A current code (one step either side), never one already used."""
        totp = pyotp.TOTP(_secret(self._settings, account))
        now_step = totp.timecode(datetime.now(UTC))
        for step in (now_step - 1, now_step, now_step + 1):
            if account.last_totp_step is not None and step <= account.last_totp_step:
                continue
            if constant_time_equals(totp.generate_otp(step), code):
                account.last_totp_step = step
                return True
        return False

    async def confirm_two_step(self, who: AdminIdentity, code: str, ip: str | None) -> AdminSignIn:
        """The first code turns two-step login on, hands out recovery codes and signs in."""
        await self._limiter.hit(
            f"admin:2fa:{who.user.id}", limit=self._settings.admin_two_step_attempts
        )
        account = await self._db.get(AdminAccount, who.user.id, with_for_update=True)
        if account is None or not account.totp_secret:
            raise TwoStepNotSetUpError
        if account.two_step_enabled_at is not None:
            raise TwoStepAlreadyEnabledError
        if not await self._check_totp(account, _normalise(code)):
            raise InvalidTwoStepCodeError
        account.two_step_enabled_at = datetime.now(UTC)
        await self._db.execute(
            delete(AdminRecoveryCode).where(AdminRecoveryCode.user_id == who.user.id)
        )
        codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        for plain in codes:
            self._db.add(AdminRecoveryCode(user_id=who.user.id, code_hash=hash_token(plain)))
        record(
            self._db,
            who,
            "admin.two_step_enabled",
            target_type="user",
            target_id=who.user.id,
            ip=ip,
        )
        token, session = self._new_session(who.user.id)
        record(self._db, who, "admin.signed_in", target_type="user", target_id=who.user.id, ip=ip)
        await self._db.commit()
        return AdminSignIn(token=token, session=session, recovery_codes=codes)

    async def verify(self, who: AdminIdentity, code: str, ip: str | None) -> AdminSignIn:
        """A TOTP code or an unused recovery code opens an admin session."""
        await self._limiter.hit(
            f"admin:2fa:{who.user.id}", limit=self._settings.admin_two_step_attempts
        )
        account = await self._db.get(AdminAccount, who.user.id, with_for_update=True)
        if account is None or account.two_step_enabled_at is None:
            raise TwoStepNotSetUpError
        clean = _normalise(code)
        used_recovery = False
        if "-" in clean or len(clean) > 6:
            recovery = await self._db.scalar(
                select(AdminRecoveryCode)
                .where(
                    AdminRecoveryCode.user_id == who.user.id,
                    AdminRecoveryCode.code_hash == hash_token(clean),
                    AdminRecoveryCode.used_at.is_(None),
                )
                .with_for_update()
            )
            if recovery is None:
                raise InvalidTwoStepCodeError
            recovery.used_at = datetime.now(UTC)
            used_recovery = True
        elif not await self._check_totp(account, clean):
            raise InvalidTwoStepCodeError
        token, session = self._new_session(who.user.id)
        record(
            self._db,
            who,
            "admin.recovery_code_used" if used_recovery else "admin.signed_in",
            target_type="user",
            target_id=who.user.id,
            ip=ip,
        )
        await self._db.commit()
        return AdminSignIn(token=token, session=session)

    def _new_session(self, user_id: uuid.UUID) -> tuple[str, AdminSession]:
        now = datetime.now(UTC)
        token = generate_token()
        session = AdminSession(
            user_id=user_id,
            token_hash=hash_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(minutes=self._settings.admin_session_idle_minutes),
        )
        self._db.add(session)
        return token, session

    async def sign_out(self, who: AdminIdentity, session: AdminSession, ip: str | None) -> None:
        await self._db.execute(delete(AdminSession).where(AdminSession.id == session.id))
        record(self._db, who, "admin.signed_out", target_type="user", target_id=who.user.id, ip=ip)
        await self._db.commit()

    # --- the team ------------------------------------------------------------------------

    async def team(self) -> list[tuple[User, AdminRole, AdminAccount | None, datetime | None]]:
        """Owners (from the environment) and everyone with a role, with their last admin
        activity. Two queries, whatever the size of the team."""
        owners = (
            list(
                await self._db.scalars(
                    select(User).where(User.email.in_(self._settings.admin_owner_emails))
                )
            )
            if self._settings.admin_owner_emails
            else []
        )
        rows = (
            (
                await self._db.execute(
                    select(User, AdminAccount)
                    .join(AdminAccount, AdminAccount.user_id == User.id)
                    .where(AdminAccount.role.is_not(None))
                )
            )
            .tuples()
            .all()
        )
        accounts = {user.id: account for user, account in rows}
        people = {user.id: user for user in owners} | {user.id: user for user, _ in rows}
        if not people:
            return []
        owner_accounts = (
            {
                account.user_id: account
                for account in await self._db.scalars(
                    select(AdminAccount).where(AdminAccount.user_id.in_([u.id for u in owners]))
                )
            }
            if owners
            else {}
        )
        accounts |= {k: v for k, v in owner_accounts.items() if k not in accounts}
        seen = dict(
            (
                await self._db.execute(
                    select(AdminSession.user_id, AdminSession.last_seen_at)
                    .where(AdminSession.user_id.in_(list(people)))
                    .order_by(AdminSession.last_seen_at)
                )
            )
            .tuples()
            .all()
        )
        team: list[tuple[User, AdminRole, AdminAccount | None, datetime | None]] = []
        for user_id, user in people.items():
            role = role_of(self._settings, user, accounts.get(user_id))
            if role is not None:
                team.append((user, role, accounts.get(user_id), seen.get(user_id)))
        order = list(AdminRole)
        return sorted(team, key=lambda item: (order.index(item[1]), item[0].email))

    async def grant(
        self, actor: AdminIdentity, email: str, role: AdminRole, reason: str, ip: str | None
    ) -> User:
        user = await self._db.scalar(select(User).where(User.email == email.strip()))
        if user is None:
            raise AdminUserNotFoundError
        if user.email.lower() in self._settings.admin_owner_emails or role is AdminRole.OWNER:
            raise CannotChangeOwnerError
        account = await self._db.get(AdminAccount, user.id, with_for_update=True)
        if account is None:
            account = AdminAccount(user_id=user.id, role=role.value, granted_by=actor.user.id)
            self._db.add(account)
        else:
            account.role = role.value
            account.granted_by = actor.user.id
        record(
            self._db,
            actor,
            f"admin.role_granted.{role.value}",
            target_type="user",
            target_id=user.id,
            reason=reason,
            ip=ip,
        )
        await self._db.commit()
        logger.info("admin_role_granted", extra={"role": role.value})
        return user

    async def remove(
        self, actor: AdminIdentity, user_id: uuid.UUID, reason: str, ip: str | None
    ) -> None:
        user = await self._db.get(User, user_id)
        if user is not None and user.email.lower() in self._settings.admin_owner_emails:
            raise CannotChangeOwnerError
        account = await self._db.get(AdminAccount, user_id, with_for_update=True)
        if user is None or account is None or account.role is None:
            raise NotAnAdminError
        # The role, the two-step set-up, the recovery codes and any admin session all go.
        await self._db.execute(delete(AdminSession).where(AdminSession.user_id == user_id))
        await self._db.execute(
            delete(AdminRecoveryCode).where(AdminRecoveryCode.user_id == user_id)
        )
        await self._db.delete(account)
        record(
            self._db,
            actor,
            "admin.role_removed",
            target_type="user",
            target_id=user_id,
            reason=reason,
            ip=ip,
        )
        await self._db.commit()
        logger.info("admin_role_removed")


# --- admin sessions ------------------------------------------------------------------------


async def resolve_admin_session(
    db: AsyncSession, settings: Settings, token: str, user_id: uuid.UUID
) -> AdminSession | None:
    """The live admin session for this token and person, sliding its idle expiry."""
    if not token or len(token) > _MAX_TOKEN_LENGTH:
        return None
    session = await db.scalar(
        select(AdminSession).where(AdminSession.token_hash == hash_token(token))
    )
    if session is None or session.user_id != user_id:
        return None
    now = datetime.now(UTC)
    ends = session.created_at + timedelta(hours=settings.admin_session_max_hours)
    if session.expires_at <= now or ends <= now:
        await db.delete(session)
        await db.commit()
        return None
    if now - session.last_seen_at >= SLIDE_INTERVAL:
        await db.execute(
            update(AdminSession)
            .where(AdminSession.id == session.id)
            .values(
                last_seen_at=now,
                expires_at=min(now + timedelta(minutes=settings.admin_session_idle_minutes), ends),
            )
        )
        await db.commit()
    return session
