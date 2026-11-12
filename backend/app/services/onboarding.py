"""Onboarding (ADR 0022): save each step on its own, skip steps, and report progress.

A step save creates the profile row if there is none yet. That row has no about text
(``parse_status`` stays ``empty``), so no AI reads anything and matching ignores it.

Leaving step 4 (``finish``) stores an about text made from the chips by a template, then a
``compose_profile`` job asks the AI for a better one (step 5 shows it loading). Step 5's
"Looks good" (``complete``) finishes onboarding; only then is the profile embedded and
matchable.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.stages.compose import compose_template
from app.core.config import Settings
from app.core.errors import AppError, ConflictError
from app.jobs.queue import enqueue
from app.jobs.tasks import COMPOSE_PROFILE, EMBED_PROFILE, PARSE_PROFILE
from app.models import FlaggedItem, OnboardingStep, ParseSource, ParseStatus, Profile, User
from app.schemas.onboarding import (
    AboutStepIn,
    CompleteIn,
    FinishIn,
    IntentsStepIn,
    NextStep,
    OffersStepIn,
    OnboardingOut,
    SkippableStep,
    StepOut,
    StepState,
    WantsStepIn,
)
from app.schemas.strength import StrengthOut
from app.services import content_rules
from app.services.auth.rate_limit import RateLimiter
from app.services.profile_compose import chips_of, structured_from_chips
from app.services.profile_parsing import set_chips, text_hash
from app.services.profile_strength import strength_of
from app.services.profiles import AiConsentRequiredError

logger = logging.getLogger(__name__)

STEP_ORDER: tuple[OnboardingStep, ...] = tuple(OnboardingStep)

# Step 4 fields where an explicit null clears the value.
_ABOUT_CLEARED_ON_NULL = ("study_year", "branch", "weekly_hours")
# ... and those that stay as they are when sent as null.
_ABOUT_KEPT_ON_NULL = ("available_days", "display_name")


def progress(profile: Profile | None) -> OnboardingOut:
    """The person's progress. Pure: no database access, so it is unit tested directly."""
    if profile is None:
        return OnboardingOut(
            completed_at=None,
            next_step=NextStep.INTENTS,
            steps=[StepOut(step=step, state=StepState.TODO) for step in STEP_ORDER],
            intents=[],
            offer_skills=[],
            want_skills=[],
            interest_tags=[],
            want_note="",
            study_year=None,
            branch=None,
            available_days=[],
            weekly_hours=None,
            display_name="",
            strength=StrengthOut.of(strength_of(None)),
        )
    states: list[StepOut] = []
    for step in STEP_ORDER:
        if step in profile.onboarding_saved:
            state = StepState.SAVED
        elif step in profile.onboarding_skipped:
            state = StepState.SKIPPED
        else:
            state = StepState.TODO
        states.append(StepOut(step=step, state=state))
    next_step: NextStep | None = None
    if profile.onboarding_completed_at is None:
        todo = next((s.step for s in states if s.state is StepState.TODO), None)
        next_step = NextStep(todo.value) if todo is not None else NextStep.REVIEW
    return OnboardingOut.model_validate(
        {
            "completed_at": profile.onboarding_completed_at,
            "next_step": next_step,
            "steps": states,
            "intents": list(profile.intents),
            "offer_skills": list(profile.offer_skills),
            "want_skills": list(profile.want_skills),
            "interest_tags": list(profile.interest_tags),
            "want_note": profile.want_note,
            "study_year": profile.study_year,
            "branch": profile.branch,
            "available_days": list(profile.available_days),
            "weekly_hours": profile.weekly_hours,
            "display_name": profile.display_name,
            "strength": StrengthOut.of(strength_of(profile)),
        }
    )


class IntentsRequiredError(ConflictError):
    code = "onboarding_intents_required"
    default_message = "Pick what you're here for before finishing."


class AlreadyOnboardedError(ConflictError):
    code = "onboarding_completed"
    default_message = "Your profile is already set up. Change it on the You page."


class NotFinishedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "onboarding_not_finished"
    default_message = "Finish the earlier steps first."


def _mark(profile: Profile, step: OnboardingStep, *, skipped: bool) -> None:
    """A step is either saved or skipped, never both."""
    saved = [s for s in profile.onboarding_saved if s != step]
    skips = [s for s in profile.onboarding_skipped if s != step]
    (skips if skipped else saved).append(step.value)
    profile.onboarding_saved = saved
    profile.onboarding_skipped = skips


class OnboardingService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        self._limiter = limiter

    async def get(self, user: User) -> OnboardingOut:
        return progress(await self._db.get(Profile, user.id))

    async def _profile_for_write(self, user: User) -> Profile:
        """The locked profile row, created (empty, nothing to parse) if there is none."""
        await self._limiter.hit(
            f"onboarding:{user.id}", limit=self._settings.profile_update_limit_per_user
        )
        profile = await self._db.scalar(
            select(Profile).where(Profile.user_id == user.id).with_for_update()
        )
        if profile is None:
            profile = Profile(user_id=user.id, raw_about_text="")
            self._db.add(profile)
            await self._db.flush()
        return profile

    async def _reembed_if(self, profile: Profile, changed: bool) -> None:
        """A finished profile's skills changed (e.g. from the soft gate): match on the new ones.
        Before "Looks good" nothing is embedded; finishing step 4 again rebuilds the view."""
        if changed and profile.onboarding_completed_at is not None:
            await enqueue(self._db, EMBED_PROFILE, {"user_id": str(profile.user_id)})

    async def _commit(self, user: User, profile: Profile, step: OnboardingStep) -> OnboardingOut:
        await self._db.commit()
        await self._db.refresh(profile)
        logger.info("onboarding_step_saved", extra={"step": step.value})
        return progress(profile)

    async def save_intents(self, user: User, data: IntentsStepIn) -> OnboardingOut:
        profile = await self._profile_for_write(user)
        profile.intents = [intent.value for intent in data.intents]
        _mark(profile, OnboardingStep.INTENTS, skipped=False)
        return await self._commit(user, profile, OnboardingStep.INTENTS)

    async def save_offers(self, user: User, data: OffersStepIn) -> OnboardingOut:
        profile = await self._profile_for_write(user)
        await self._reembed_if(profile, set_chips(profile, offers=data.skills))
        _mark(profile, OnboardingStep.OFFERS, skipped=False)
        return await self._commit(user, profile, OnboardingStep.OFFERS)

    async def save_wants(self, user: User, data: WantsStepIn) -> OnboardingOut:
        profile = await self._profile_for_write(user)
        note_changed = data.note != profile.want_note
        changed = set_chips(profile, wants=data.skills, interests=data.interests)
        await self._reembed_if(profile, changed)
        profile.want_note = data.note
        if note_changed:
            # Content rules only flag for a moderator; they never block the save.
            await content_rules.flag(
                self._db,
                user_id=user.id,
                item=FlaggedItem.PROFILE,
                item_id=user.id,
                text=data.note,
            )
        _mark(profile, OnboardingStep.WANTS, skipped=False)
        return await self._commit(user, profile, OnboardingStep.WANTS)

    async def save_about(self, user: User, data: AboutStepIn) -> OnboardingOut:
        profile = await self._profile_for_write(user)
        changes: dict[str, Any] = data.model_dump(exclude_unset=True)
        for field in _ABOUT_CLEARED_ON_NULL:
            if field in changes:
                setattr(profile, field, changes[field])
        for field in _ABOUT_KEPT_ON_NULL:
            if changes.get(field) is not None:
                setattr(profile, field, changes[field])
        _mark(profile, OnboardingStep.ABOUT, skipped=False)
        return await self._commit(user, profile, OnboardingStep.ABOUT)

    async def skip(self, user: User, step: SkippableStep) -> OnboardingOut:
        """Skip for now. Whatever was saved for the step stays."""
        profile = await self._profile_for_write(user)
        onboarding_step = OnboardingStep(step.value)
        _mark(profile, onboarding_step, skipped=True)
        return await self._commit(user, profile, onboarding_step)

    async def finish(self, user: User, data: FinishIn) -> Profile:
        """Leave step 4: store the template about text now, and queue the AI's version."""
        profile = await self._profile_for_write(user)
        if profile.onboarding_completed_at is not None:
            raise AlreadyOnboardedError
        if OnboardingStep.INTENTS not in profile.onboarding_saved:
            raise IntentsRequiredError
        consent_current = profile.ai_consent_version == self._settings.ai_consent_version
        if not data.ai_consent and not consent_current:
            raise AiConsentRequiredError
        now = datetime.now(UTC)
        if data.ai_consent:
            profile.ai_consent_at = now
            profile.ai_consent_version = self._settings.ai_consent_version
        names = [profile.display_name] if profile.display_name.strip() else []
        template = compose_template(chips_of(profile), names=names)
        profile.raw_about_text = template.about
        profile.structured = structured_from_chips(profile, template)
        profile.parse_source = ParseSource.TEMPLATE
        profile.parse_prompt_version = None
        # Marks the text the job may replace; an edit on step 5 changes it.
        profile.parsed_text_hash = text_hash(template.about)
        profile.parsed_at = now
        profile.parse_status = ParseStatus.PENDING
        await self._db.flush()
        await enqueue(self._db, COMPOSE_PROFILE, {"user_id": str(user.id)})
        await self._db.commit()
        await self._db.refresh(profile)
        logger.info("onboarding_finished_steps")
        return profile

    async def complete(self, user: User, data: CompleteIn) -> Profile:
        """Step 5's "Looks good": keep the about text (edited or not), finish onboarding."""
        profile = await self._profile_for_write(user)
        if profile.onboarding_completed_at is not None:
            return profile
        if not profile.raw_about_text.strip():
            raise NotFinishedError
        if profile.ai_consent_version != self._settings.ai_consent_version:
            raise AiConsentRequiredError
        edited = text_hash(data.about_text) != text_hash(profile.raw_about_text)
        profile.onboarding_completed_at = datetime.now(UTC)
        if edited:
            profile.raw_about_text = data.about_text
            await content_rules.flag(
                self._db,
                user_id=user.id,
                item=FlaggedItem.PROFILE,
                item_id=user.id,
                text=data.about_text,
            )
            # Their own words now: read them like any about text (the chips stay first).
            profile.parsed_text_hash = None
            profile.parse_status = ParseStatus.PENDING
            await self._db.flush()
            await enqueue(self._db, PARSE_PROFILE, {"user_id": str(user.id)})
        elif profile.parse_status == ParseStatus.PARSED:
            await enqueue(self._db, EMBED_PROFILE, {"user_id": str(user.id)})
        # Otherwise the compose job is still running; it embeds once it is done.
        await self._db.commit()
        await self._db.refresh(profile)
        logger.info("onboarding_completed", extra={"edited": edited})
        return profile
