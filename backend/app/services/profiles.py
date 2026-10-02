"""The signed-in user's profile: save, settings, corrections (ARCHITECTURE.md §4, Profile).

The API never calls a model: a changed about text is marked ``pending`` and a
``parse_profile`` job is queued in the same transaction (ADR 0002, ADR 0008).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from http import HTTPStatus

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.jobs.queue import enqueue
from app.jobs.tasks import EMBED_PROFILE, PARSE_PROFILE
from app.models import ParseSource, ParseStatus, Profile, User
from app.schemas.profile import ProfileIn, ProfileSettingsIn, UnderstandingIn
from app.services.auth.rate_limit import RateLimiter
from app.services.profile_parsing import text_hash

logger = logging.getLogger(__name__)


class ProfileNotFoundError(NotFoundError):
    code = "profile_not_found"
    default_message = "You have not created a profile yet."


class AiConsentRequiredError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "ai_consent_required"
    default_message = "To save your profile, agree to how AI is used to find your matches."


class ProfileTextRequiredError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "profile_text_required"
    default_message = "Add a description before correcting what was understood from it."


class ProfileService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        self._limiter = limiter

    async def get(self, user: User) -> Profile:
        profile = await self._db.get(Profile, user.id)
        if profile is None:
            raise ProfileNotFoundError
        return profile

    async def _locked(self, user: User) -> Profile | None:
        return await self._db.scalar(
            select(Profile).where(Profile.user_id == user.id).with_for_update()
        )

    async def _rate_limit(self, user: User) -> None:
        await self._limiter.hit(
            f"profile:{user.id}", limit=self._settings.profile_update_limit_per_user
        )

    async def save(self, user: User, data: ProfileIn) -> Profile:
        """Create or replace the profile; queue a parse if the text changed."""
        await self._rate_limit(user)
        profile = await self._locked(user)
        consent_current = (
            profile is not None and profile.ai_consent_version == self._settings.ai_consent_version
        )
        if not data.ai_consent and not consent_current:
            raise AiConsentRequiredError
        if profile is None:
            profile = Profile(user_id=user.id, raw_about_text="")
            self._db.add(profile)
        now = datetime.now(UTC)
        if data.ai_consent:
            profile.ai_consent_at = now
            profile.ai_consent_version = self._settings.ai_consent_version
        text_changed = text_hash(data.about_text) != text_hash(profile.raw_about_text)
        profile.display_name = data.display_name
        profile.raw_about_text = data.about_text
        profile.links = list(data.links)
        profile.timezone = data.timezone
        profile.languages = list(data.languages)
        profile.visibility = data.visibility
        if text_changed or profile.parse_status == ParseStatus.EMPTY:
            profile.parse_status = ParseStatus.PENDING
            await self._db.flush()
            await enqueue(self._db, PARSE_PROFILE, {"user_id": str(user.id)})
        await self._db.commit()
        await self._db.refresh(profile)
        logger.info("profile_saved", extra={"text_changed": text_changed})
        return profile

    async def update_settings(self, user: User, data: ProfileSettingsIn) -> Profile:
        await self._rate_limit(user)
        profile = await self._locked(user)
        if profile is None:
            raise ProfileNotFoundError
        changes = data.model_dump(exclude_unset=True)
        for field in ("display_name", "visibility", "links", "languages", "email_notifications"):
            if changes.get(field) is not None:
                setattr(profile, field, changes[field])
        if "timezone" in changes:
            profile.timezone = changes["timezone"]
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def correct(self, user: User, data: UnderstandingIn) -> Profile:
        """Replace what was understood with the user's own version, and re-embed it."""
        await self._rate_limit(user)
        profile = await self._locked(user)
        if profile is None:
            raise ProfileNotFoundError
        if not profile.raw_about_text.strip():
            raise ProfileTextRequiredError
        profile.structured = data.model_dump()
        profile.parse_source = ParseSource.USER
        profile.parse_prompt_version = None
        # Marks the correction as belonging to this text, so a queued parse skips it.
        profile.parsed_text_hash = text_hash(profile.raw_about_text)
        profile.parsed_at = datetime.now(UTC)
        profile.parse_status = ParseStatus.PARSED
        await enqueue(self._db, EMBED_PROFILE, {"user_id": str(user.id)})
        await self._db.commit()
        await self._db.refresh(profile)
        return profile
