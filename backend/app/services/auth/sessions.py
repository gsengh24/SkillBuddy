"""Server-side sessions: create, resolve with sliding expiry, revoke.

The browser holds a random token; the database holds only its SHA-256. A session expires
after ``session_idle_days`` without use (sliding) and never outlives
``session_max_days`` from sign-in (absolute).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import generate_token, hash_token, keyed_hash
from app.models import User, UserSession, UserStatus
from app.services.auth.events import ClientInfo

# Refresh last_seen_at/expires_at at most this often, to avoid a write on every request.
SLIDE_INTERVAL: Final = timedelta(hours=1)
# Tokens are generate_token() output (43 URL-safe characters); anything else is rejected
# before touching the database.
_MAX_TOKEN_LENGTH: Final = 128


@dataclass(frozen=True)
class NewSession:
    token: str
    session: UserSession


def absolute_expiry(settings: Settings, created_at: datetime) -> datetime:
    return created_at + timedelta(days=settings.session_max_days)


def csrf_token_for(settings: Settings, session: UserSession) -> str:
    """The CSRF token for a session: a keyed hash of its token hash (signed double-submit)."""
    return keyed_hash(settings.secret_key, "csrf", session.token_hash)


async def create_session(
    db: AsyncSession, settings: Settings, user_id: uuid.UUID, client: ClientInfo
) -> NewSession:
    now = datetime.now(UTC)
    token = generate_token()
    session = UserSession(
        user_id=user_id,
        token_hash=hash_token(token),
        created_at=now,
        last_seen_at=now,
        expires_at=min(
            now + timedelta(days=settings.session_idle_days), absolute_expiry(settings, now)
        ),
        user_agent=client.user_agent,
        ip=client.ip,
    )
    db.add(session)
    await db.flush()
    return NewSession(token=token, session=session)


async def resolve_session(
    db: AsyncSession, settings: Settings, token: str
) -> tuple[UserSession, User] | None:
    """Return the live session and its active user for a token, or None."""
    if not token or len(token) > _MAX_TOKEN_LENGTH:
        return None
    row = (
        await db.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == hash_token(token))
        )
    ).first()
    if row is None:
        return None
    session, user = row
    now = datetime.now(UTC)
    if session.expires_at <= now:
        await db.delete(session)
        await db.commit()
        return None
    if user.status != UserStatus.ACTIVE:
        return None
    if now - session.last_seen_at >= SLIDE_INTERVAL:
        session.last_seen_at = now
        session.expires_at = min(
            now + timedelta(days=settings.session_idle_days),
            absolute_expiry(settings, session.created_at),
        )
        await db.commit()
    return session, user


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(delete(UserSession).where(UserSession.id == session_id))


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    return int(getattr(result, "rowcount", 0) or 0)
