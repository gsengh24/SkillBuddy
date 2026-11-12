"""Onboarding (ADR 0022): save each step on its own, skip steps, and read progress.

Responses are data only (no UI copy), so any client can drive the same flow.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.db.session import get_db_session
from app.schemas.errors import ErrorResponse
from app.schemas.onboarding import (
    AboutStepIn,
    IntentsStepIn,
    OffersStepIn,
    OnboardingOut,
    SkippableStep,
    WantsStepIn,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.onboarding import OnboardingService

router = APIRouter(prefix="/me/onboarding", tags=["onboarding"])


def get_onboarding_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: SettingsDep,
) -> OnboardingService:
    limiter = RateLimiter(
        request.app.state.session_factory,
        settings.secret_key,
        window_seconds=settings.rate_limit_window_seconds,
    )
    return OnboardingService(db, settings, limiter)


OnboardingServiceDep = Annotated[OnboardingService, Depends(get_onboarding_service)]

_READ_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
}
_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_READ_ERRORS,
    422: {"model": ErrorResponse, "description": "Validation failed."},
    429: {"model": ErrorResponse, "description": "Too many saves; retry later."},
    503: {"model": ErrorResponse, "description": "Storage nearly full; try again later."},
}
_JSON_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_WRITE_ERRORS,
    415: {"model": ErrorResponse, "description": "The body is not JSON."},
}
_JSON_WRITE = [Depends(require_json), Depends(require_storage_capacity)]


@router.get("", summary="Get my onboarding progress", responses=_READ_ERRORS)
async def get_onboarding(auth: AuthDep, service: OnboardingServiceDep) -> OnboardingOut:
    """Works before a profile exists: everything is empty and ``next_step`` is ``intents``."""
    return await service.get(auth.user)


@router.put(
    "/intents",
    summary="Save step 1: what I'm here for",
    dependencies=_JSON_WRITE,
    responses=_JSON_WRITE_ERRORS,
)
async def save_intents(
    body: IntentsStepIn, auth: AuthDep, service: OnboardingServiceDep
) -> OnboardingOut:
    return await service.save_intents(auth.user, body)


@router.put(
    "/offers",
    summary="Save step 2: skills I offer",
    dependencies=_JSON_WRITE,
    responses=_JSON_WRITE_ERRORS,
)
async def save_offers(
    body: OffersStepIn, auth: AuthDep, service: OnboardingServiceDep
) -> OnboardingOut:
    return await service.save_offers(auth.user, body)


@router.put(
    "/wants",
    summary="Save step 3: what I'm looking for",
    dependencies=_JSON_WRITE,
    responses=_JSON_WRITE_ERRORS,
)
async def save_wants(
    body: WantsStepIn, auth: AuthDep, service: OnboardingServiceDep
) -> OnboardingOut:
    return await service.save_wants(auth.user, body)


@router.put(
    "/about",
    summary="Save step 4: a bit about me",
    dependencies=_JSON_WRITE,
    responses=_JSON_WRITE_ERRORS,
)
async def save_about(
    body: AboutStepIn, auth: AuthDep, service: OnboardingServiceDep
) -> OnboardingOut:
    """Omitted fields stay as they are; ``null`` clears year, branch and hours."""
    return await service.save_about(auth.user, body)


@router.post(
    "/{step}/skip",
    summary="Skip a step for now",
    dependencies=[Depends(require_storage_capacity)],
    responses=_WRITE_ERRORS,
)
async def skip_step(
    step: SkippableStep, auth: AuthDep, service: OnboardingServiceDep
) -> OnboardingOut:
    """Steps 2 to 4 only (``offers``, ``wants``, ``about``); anything saved for the step
    stays. Saving the step later replaces the skip."""
    return await service.skip(auth.user, step)
