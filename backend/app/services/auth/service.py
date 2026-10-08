"""Sign-in flows: email codes and Google (ADR 0006, ADR 0011), sign out, account deletion."""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import constant_time_equals, generate_numeric_code, mask_email
from app.models import (
    SIGNED_IN_STATUSES,
    AuthEventType,
    AuthIdentity,
    AuthProvider,
    OAuthState,
    OtpCode,
    User,
    UserSession,
    UserStatus,
)
from app.services.auth.codes import (
    OTP_DIGITS,
    email_hash,
    normalise_email,
    oauth_state_hash,
    otp_hash,
)
from app.services.auth.delivery import OtpDelivery
from app.services.auth.errors import (
    AccountPendingDeletionError,
    AccountSuspendedError,
    CannotPauseError,
    CodeLockedError,
    ConsentRequiredError,
    EmailNotAllowedError,
    GoogleSignInCancelledError,
    GoogleSignInFailedError,
    GoogleSignInUnavailableError,
    InvalidCodeError,
    NotPausedError,
    OAuthStateInvalidError,
    SessionNotFoundError,
)
from app.services.auth.events import ClientInfo, record_event
from app.services.auth.google import GoogleOidcClient, GoogleSignInError
from app.services.auth.policy import SignInMethod, is_email_allowed
from app.services.auth.rate_limit import RateLimiter
from app.services.auth.sessions import create_session, revoke_all_sessions, revoke_session
from app.services.email.budget import ensure_login_code_can_be_sent
from app.services.storage import SignupsPausedError, StorageMonitor

logger = logging.getLogger(__name__)

# How long a "Continue with Google" attempt may take before its state expires.
OAUTH_STATE_TTL = timedelta(minutes=10)
DEFAULT_NEXT_PATH = "/home"


@dataclass(frozen=True)
class SignInResult:
    user: User
    session: UserSession
    token: str
    created_account: bool


@dataclass(frozen=True)
class GoogleStart:
    state: str
    authorization_url: str


@dataclass(frozen=True)
class GoogleSignInResult:
    sign_in: SignInResult
    next_path: str


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        limiter: RateLimiter,
        delivery: OtpDelivery,
        storage: StorageMonitor,
        google: GoogleOidcClient | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._limiter = limiter
        self._delivery = delivery
        self._storage = storage
        self._google = google

    async def _refuse(
        self,
        client: ClientInfo,
        reason: str,
        *,
        method: SignInMethod,
        email: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Record a refused sign-in in the audit log (reason codes only, never secrets)."""
        record_event(
            self._db,
            self._settings,
            AuthEventType.LOGIN_REFUSED,
            client=client,
            email=email,
            user_id=user_id,
            detail={"reason": reason, "method": method.value},
        )
        await self._db.commit()

    async def _ensure_allowed(self, email: str, method: SignInMethod, client: ClientInfo) -> None:
        if not is_email_allowed(self._settings, email, method):
            await self._refuse(client, "email_not_allowed", method=method, email=email)
            raise EmailNotAllowedError

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
        await self._ensure_allowed(email, SignInMethod.EMAIL_CODE, client)
        # Gmail's daily cap: refuse now (503) rather than accept a code that cannot be sent.
        await ensure_login_code_can_be_sent(self._db, self._settings)
        # Only the newest code is ever valid.
        await self._db.execute(
            delete(OtpCode).where(OtpCode.email == email, OtpCode.consumed_at.is_(None))
        )
        code = generate_numeric_code(OTP_DIGITS)
        otp_id = uuid.uuid4()
        self._db.add(
            OtpCode(
                id=otp_id,
                email=email,
                code_hash=otp_hash(self._settings, email, code),
                expires_at=datetime.now(UTC) + timedelta(minutes=self._settings.otp_ttl_minutes),
                created_ip=client.ip,
            )
        )
        record_event(
            self._db, self._settings, AuthEventType.OTP_REQUESTED, client=client, email=email
        )
        # The email job commits with the code: both exist, or neither (ADR 0008).
        await self._delivery.send_login_code(self._db, otp_id, email, code)
        await self._db.commit()
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
        await self._ensure_allowed(email, SignInMethod.EMAIL_CODE, client)
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
        try:
            await self._check_consent_and_capacity(
                user, age_confirmed=age_confirmed, accept_terms=accept_terms
            )
        except (ConsentRequiredError, SignupsPausedError):
            # Keep the code usable so the person can tick the boxes and resubmit.
            await self._db.rollback()
            raise
        otp.consumed_at = now
        return await self._finish_sign_in(
            user, email, now, client, provider=AuthProvider.EMAIL, subject=email
        )

    async def _check_consent_and_capacity(
        self, user: User | None, *, age_confirmed: bool, accept_terms: bool
    ) -> None:
        # 18+ by self-declaration (ADR 0009): new accounts confirm age and accept the terms;
        # an active account with no recorded age confirmation must confirm before signing in.
        needs_terms = user is None
        needs_age = user is None or (
            user.status in SIGNED_IN_STATUSES and user.age_confirmed_at is None
        )
        if (needs_age and not age_confirmed) or (needs_terms and not accept_terms):
            raise ConsentRequiredError
        if user is None:
            # Near the free storage limit, refuse new accounts (existing users still sign in).
            await self._storage.ensure_signups_allowed()

    async def _finish_sign_in(
        self,
        user: User | None,
        email: str,
        now: datetime,
        client: ClientInfo,
        *,
        provider: AuthProvider,
        subject: str,
    ) -> SignInResult:
        """Refuse inactive accounts, create or link the account, and start a session."""
        google = provider is AuthProvider.GOOGLE
        detail = {"method": SignInMethod.GOOGLE.value} if google else None
        if user is not None and user.status not in SIGNED_IN_STATUSES:
            record_event(
                self._db,
                self._settings,
                AuthEventType.LOGIN_REFUSED,
                client=client,
                user_id=user.id,
                detail={"reason": user.status, **(detail or {})},
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
            self._db.add(AuthIdentity(user_id=user.id, provider=provider, subject=subject))
        else:
            if google and not await self._has_identity(user.id, provider, subject):
                # An account made with email codes: Google has verified this address too.
                self._db.add(AuthIdentity(user_id=user.id, provider=provider, subject=subject))
            if user.age_confirmed_at is None:
                user.age_confirmed_at = now  # confirmed now (checked by the caller)
        user.last_login_at = now
        new = await create_session(self._db, self._settings, user.id, client)
        event = AuthEventType.SIGNUP if created_account else AuthEventType.LOGIN
        record_event(self._db, self._settings, event, client=client, user_id=user.id, detail=detail)
        await self._db.commit()
        logger.info(
            "signed_in",
            extra={
                "user_id": str(user.id),
                "created_account": created_account,
                "method": SignInMethod.GOOGLE.value if google else SignInMethod.EMAIL_CODE.value,
            },
        )
        return SignInResult(
            user=user, session=new.session, token=new.token, created_account=created_account
        )

    async def _has_identity(self, user_id: uuid.UUID, provider: AuthProvider, subject: str) -> bool:
        found = await self._db.scalar(
            select(AuthIdentity.id).where(
                AuthIdentity.user_id == user_id,
                AuthIdentity.provider == provider,
                AuthIdentity.subject == subject,
            )
        )
        return found is not None

    # --- Google (ADR 0011) ----------------------------------------------------------------

    def _google_client(self) -> GoogleOidcClient:
        if self._google is None or not self._settings.google_signin_available:
            raise GoogleSignInUnavailableError
        return self._google

    async def _limit_google(self, action: str, client: ClientInfo) -> None:
        if client.ip:
            await self._limiter.hit(
                f"google-{action}:ip:{client.ip}", limit=self._settings.google_signin_limit_per_ip
            )

    async def start_google(
        self, *, age_confirmed: bool, accept_terms: bool, next_path: str | None, client: ClientInfo
    ) -> GoogleStart:
        """Record a single-use attempt and return Google's URL to send the browser to."""
        google = self._google_client()
        await self._limit_google("start", client)
        state = secrets.token_urlsafe(32)
        self._db.add(
            OAuthState(
                state_hash=oauth_state_hash(self._settings, state),
                next_path=next_path or DEFAULT_NEXT_PATH,
                age_confirmed=age_confirmed,
                accept_terms=accept_terms,
                created_ip=client.ip,
                expires_at=datetime.now(UTC) + OAUTH_STATE_TTL,
            )
        )
        await self._db.commit()
        return GoogleStart(state=state, authorization_url=google.authorization_url(state))

    async def finish_google(
        self,
        *,
        state: str | None,
        bound_state: str | None,
        code: str | None,
        error: str | None,
        client: ClientInfo,
    ) -> GoogleSignInResult:
        """Handle Google's redirect back: check the state, then the ID token, then sign in.

        ``bound_state`` is the value of the httpOnly cookie set at the start, so a callback
        only works in the browser that began the attempt (no login CSRF).
        """
        google = self._google_client()
        method = SignInMethod.GOOGLE
        await self._limit_google("callback", client)
        if not state or not bound_state or not constant_time_equals(state, bound_state):
            await self._refuse(client, "state_mismatch", method=method)
            raise OAuthStateInvalidError
        now = datetime.now(UTC)
        attempt = await self._db.scalar(
            delete(OAuthState)
            .where(
                OAuthState.state_hash == oauth_state_hash(self._settings, state),
                OAuthState.expires_at > now,
            )
            .returning(OAuthState)
        )
        # Used up whatever happens next: a state works once.
        await self._db.commit()
        if attempt is None:
            await self._refuse(client, "state_unknown_or_used", method=method)
            raise OAuthStateInvalidError
        if error or not code:
            await self._refuse(client, "cancelled" if error else "no_code", method=method)
            if error:
                raise GoogleSignInCancelledError
            raise GoogleSignInFailedError

        try:
            identity = await google.sign_in(code, state)
        except GoogleSignInError as rejected:
            logger.warning("google_sign_in_rejected", extra={"reason": rejected.reason})
            await self._refuse(client, rejected.reason, method=method)
            raise GoogleSignInFailedError from None

        email = normalise_email(identity.email)
        await self._ensure_allowed(email, method, client)
        user = await self._db.scalar(
            select(User)
            .join(AuthIdentity, AuthIdentity.user_id == User.id)
            .where(
                AuthIdentity.provider == AuthProvider.GOOGLE,
                AuthIdentity.subject == identity.subject,
            )
        )
        if user is None:
            user = await self._db.scalar(select(User).where(User.email == email))
        await self._check_consent_and_capacity(
            user, age_confirmed=attempt.age_confirmed, accept_terms=attempt.accept_terms
        )
        result = await self._finish_sign_in(
            user,
            user.email if user is not None else email,
            now,
            client,
            provider=AuthProvider.GOOGLE,
            subject=identity.subject,
        )
        return GoogleSignInResult(sign_in=result, next_path=attempt.next_path)

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

    async def logout_others(self, user: User, current: UserSession, client: ClientInfo) -> int:
        """Sign out every device but this one."""
        result = await self._db.execute(
            delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != current.id)
        )
        revoked = int(getattr(result, "rowcount", 0) or 0)
        record_event(
            self._db,
            self._settings,
            AuthEventType.LOGOUT_OTHERS,
            client=client,
            user_id=user.id,
            detail={"sessions_revoked": revoked},
        )
        await self._db.commit()
        return revoked

    async def sessions(self, user: User) -> list[UserSession]:
        """The live sessions, most recently used first."""
        now = datetime.now(UTC)
        rows = await self._db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user.id, UserSession.expires_at > now)
            .order_by(UserSession.last_seen_at.desc())
        )
        return list(rows)

    async def revoke(self, user: User, session_id: uuid.UUID, client: ClientInfo) -> None:
        """Sign out one of your own devices (404 for anyone else's)."""
        result = await self._db.execute(
            delete(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id)
        )
        if not getattr(result, "rowcount", 0):
            raise SessionNotFoundError
        record_event(
            self._db, self._settings, AuthEventType.SESSION_REVOKED, client=client, user_id=user.id
        )
        await self._db.commit()

    async def pause(self, user: User, client: ClientInfo) -> User:
        """Hide the account from matching and new intros; sign-in and chats carry on."""
        account = await self._db.get_one(User, user.id, with_for_update=True)
        if account.status != UserStatus.ACTIVE:
            raise CannotPauseError
        account.status = UserStatus.PAUSED
        record_event(
            self._db, self._settings, AuthEventType.ACCOUNT_PAUSED, client=client, user_id=user.id
        )
        await self._db.commit()
        await self._db.refresh(account)
        return account

    async def resume(self, user: User, client: ClientInfo) -> User:
        account = await self._db.get_one(User, user.id, with_for_update=True)
        if account.status != UserStatus.PAUSED:
            raise NotPausedError
        account.status = UserStatus.ACTIVE
        record_event(
            self._db, self._settings, AuthEventType.ACCOUNT_RESUMED, client=client, user_id=user.id
        )
        await self._db.commit()
        await self._db.refresh(account)
        return account

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
