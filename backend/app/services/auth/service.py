"""Sign-in flows: request a code, verify it, sign out, request account deletion."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import constant_time_equals, generate_numeric_code, mask_email
from app.models import (
    AuthEventType,
    AuthIdentity,
    AuthProvider,
    OtpCode,
    User,
    UserSession,
    UserStatus,
)
from app.services.auth.codes import OTP_DIGITS, email_hash, normalise_email, otp_hash
from app.services.auth.delivery import OtpDelivery
from app.services.auth.errors import (
    AccountPendingDeletionError,
    AccountSuspendedError,
    CodeLockedError,
    ConsentRequiredError,
    InvalidCodeError,
)
from app.services.auth.events import ClientInfo, record_event
from app.services.auth.rate_limit import RateLimiter
from app.services.auth.sessions import create_session, revoke_all_sessions, revoke_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignInResult:
    user: User
    session: UserSession
    token: str
    created_account: bool


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        limiter: RateLimiter,
        delivery: OtpDelivery,
    ) -> None:
        self._db = db
        self._settings = settings
        self._limiter = limiter
        self._delivery = delivery

    async def _limit(
        self, action: str, email: str, client: ClientInfo, *, per_email: int, per_ip: int
    ) -> None:
        if client.ip:
            await self._limiter.hit(f"{action}:ip:{client.ip}", limit=per_ip)
        await self._limiter.hit(
            f"{action}:email:{email_hash(self._settings, email)}", limit=per_email
        )

    async def request_code(self, raw_email: str, client: ClientInfo) -> None:
        """Send a new login code. Behaves identically whether or not the account exists."""
        email = normalise_email(raw_email)
        await self._limit(
            "otp-request",
            email,
            client,
            per_email=self._settings.otp_request_limit_per_email,
            per_ip=self._settings.otp_request_limit_per_ip,
        )
        # Only the newest code is ever valid.
        await self._db.execute(
            delete(OtpCode).where(OtpCode.email == email, OtpCode.consumed_at.is_(None))
        )
        code = generate_numeric_code(OTP_DIGITS)
        self._db.add(
            OtpCode(
                email=email,
                code_hash=otp_hash(self._settings, email, code),
                expires_at=datetime.now(UTC) + timedelta(minutes=self._settings.otp_ttl_minutes),
                created_ip=client.ip,
            )
        )
        record_event(
            self._db, self._settings, AuthEventType.OTP_REQUESTED, client=client, email=email
        )
        await self._db.commit()
        await self._delivery.send_login_code(email, code)
        logger.info("login_code_requested", extra={"email": mask_email(email)})

    async def verify_code(
        self,
        raw_email: str,
        code: str,
        *,
        age_confirmed: bool,
        accept_terms: bool,
        client: ClientInfo,
    ) -> SignInResult:
        """Check a code; on success sign in (creating the account on first use)."""
        email = normalise_email(raw_email)
        await self._limit(
            "otp-verify",
            email,
            client,
            per_email=self._settings.otp_verify_limit_per_email,
            per_ip=self._settings.otp_verify_limit_per_ip,
        )
        now = datetime.now(UTC)
        otp = await self._db.scalar(
            select(OtpCode)
            .where(OtpCode.email == email, OtpCode.consumed_at.is_(None))
            .order_by(OtpCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if otp is None or otp.expires_at <= now:
            await self._db.rollback()
            raise InvalidCodeError
        if otp.attempts >= self._settings.otp_max_attempts:
            await self._db.rollback()
            raise CodeLockedError
        if not constant_time_equals(otp_hash(self._settings, email, code), otp.code_hash):
            otp.attempts += 1
            locked = otp.attempts >= self._settings.otp_max_attempts
            event = AuthEventType.OTP_LOCKED if locked else AuthEventType.OTP_FAILED
            record_event(self._db, self._settings, event, client=client, email=email)
            await self._db.commit()
            raise CodeLockedError if locked else InvalidCodeError

        user = await self._db.scalar(select(User).where(User.email == email))
        if user is None and not (age_confirmed and accept_terms):
            # Keep the code usable so the person can tick the boxes and resubmit.
            await self._db.rollback()
            raise ConsentRequiredError

        otp.consumed_at = now
        if user is not None and user.status != UserStatus.ACTIVE:
            record_event(
                self._db,
                self._settings,
                AuthEventType.LOGIN_REFUSED,
                client=client,
                user_id=user.id,
                detail={"reason": user.status},
            )
            await self._db.commit()
            if user.status == UserStatus.PENDING_DELETION:
                raise AccountPendingDeletionError(user.deletion_scheduled_for)
            raise AccountSuspendedError

        created_account = user is None
        if user is None:
            user = User(
                email=email,
                email_verified_at=now,
                age_confirmed_at=now,
                terms_accepted_at=now,
                terms_version=self._settings.terms_version,
            )
            self._db.add(user)
            await self._db.flush()
            self._db.add(AuthIdentity(user_id=user.id, provider=AuthProvider.EMAIL, subject=email))
        user.last_login_at = now
        new = await create_session(self._db, self._settings, user.id, client)
        event = AuthEventType.SIGNUP if created_account else AuthEventType.LOGIN
        record_event(self._db, self._settings, event, client=client, user_id=user.id)
        await self._db.commit()
        logger.info(
            "signed_in", extra={"user_id": str(user.id), "created_account": created_account}
        )
        return SignInResult(
            user=user, session=new.session, token=new.token, created_account=created_account
        )

    async def logout(self, user: User, session: UserSession, client: ClientInfo) -> None:
        await revoke_session(self._db, session.id)
        record_event(self._db, self._settings, AuthEventType.LOGOUT, client=client, user_id=user.id)
        await self._db.commit()

    async def logout_all(self, user: User, client: ClientInfo) -> None:
        revoked = await revoke_all_sessions(self._db, user.id)
        record_event(
            self._db,
            self._settings,
            AuthEventType.LOGOUT_ALL,
            client=client,
            user_id=user.id,
            detail={"sessions_revoked": revoked},
        )
        await self._db.commit()

    async def request_deletion(self, user: User, client: ClientInfo) -> datetime:
        """Start the grace period: sign out everywhere; the account is purged later."""
        account = await self._db.get_one(User, user.id, with_for_update=True)
        now = datetime.now(UTC)
        scheduled_for = now + timedelta(days=self._settings.account_deletion_grace_days)
        account.status = UserStatus.PENDING_DELETION
        account.deleted_at = now
        account.deletion_scheduled_for = scheduled_for
        await revoke_all_sessions(self._db, user.id)
        record_event(
            self._db,
            self._settings,
            AuthEventType.DELETION_REQUESTED,
            client=client,
            user_id=user.id,
        )
        await self._db.commit()
        logger.info("account_deletion_requested", extra={"user_id": str(user.id)})
        return scheduled_for
