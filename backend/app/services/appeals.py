"""Appeals (A3): a suspended or banned person sends one appeal without signing in.

They can't sign in, so the appeal is authorised by a signed token instead of a session:
- a refused sign-in returns one (they just proved the address with a code), valid an hour;
- the notice email about a suspension or ban carries one, valid 7 days.
The token names the account and when it expires; it is signed with SECRET_KEY and never
stored. One open appeal at a time, and one per suspension or ban.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ConflictError
from app.core.security import constant_time_equals, keyed_hash
from app.models import Appeal, AppealStatus, User, UserStatus

SIGN_IN_TOKEN_HOURS: Final = 1
EMAIL_TOKEN_HOURS: Final = 7 * 24
APPEALABLE: Final = (UserStatus.SUSPENDED, UserStatus.BANNED)


class InvalidAppealTokenError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "invalid_appeal_link"
    default_message = "This appeal link has expired or isn't valid. Try signing in again."


class NothingToAppealError(ConflictError):
    code = "nothing_to_appeal"
    default_message = "This account isn't suspended or banned, so there's nothing to appeal."


class AppealExistsError(ConflictError):
    code = "appeal_exists"
    default_message = "You've already sent an appeal. We'll email you when it's decided."


def _sign(settings: Settings, payload: str) -> str:
    return keyed_hash(settings.secret_key, "appeal", payload)


def make_token(settings: Settings, user_id: uuid.UUID, hours: int) -> str:
    expires = int((datetime.now(UTC) + timedelta(hours=hours)).timestamp())
    payload = f"{user_id}:{expires}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(settings, payload)}"


def read_token(settings: Settings, token: str) -> uuid.UUID:
    try:
        encoded, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        user_part, expires_part = payload.split(":", 1)
        user_id = uuid.UUID(user_part)
        expires = datetime.fromtimestamp(int(expires_part), UTC)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidAppealTokenError from error
    if not constant_time_equals(signature, _sign(settings, payload)):
        raise InvalidAppealTokenError
    if expires <= datetime.now(UTC):
        raise InvalidAppealTokenError
    return user_id


async def submit(db: AsyncSession, settings: Settings, token: str, body: str) -> Appeal:
    """Record the appeal. The person is told the outcome by email."""
    user_id = read_token(settings, token)
    user = await db.get(User, user_id, with_for_update=True)
    if user is None or user.status not in APPEALABLE:
        raise NothingToAppealError
    # One per suspension or ban: any appeal since the latest sanction counts.
    since = await db.scalar(
        select(Appeal.id).where(
            Appeal.user_id == user.id,
            (Appeal.status == AppealStatus.OPEN)
            | (Appeal.created_at >= user.updated_at - timedelta(seconds=1)),
        )
    )
    if since is not None:
        raise AppealExistsError
    appeal = Appeal(user_id=user.id, against=user.status, body=body.strip())
    db.add(appeal)
    await db.commit()
    await db.refresh(appeal)
    return appeal
