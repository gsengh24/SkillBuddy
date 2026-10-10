"""The signed-in user's profile. Parsing and embedding happen in background jobs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, require_json, require_storage_capacity
from app.api.v1.auth import AuthDep
from app.core.config import Settings
from app.db.session import get_db_session
from app.models import Profile, User
from app.schemas.errors import ErrorResponse
from app.schemas.profile import ProfileIn, ProfileOut, ProfileSettingsIn, UnderstandingIn
from app.services.auth.rate_limit import RateLimiter
from app.services.profiles import ProfileService

router = APIRouter(prefix="/me/profile", tags=["profile"])


def get_profile_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: SettingsDep,
) -> ProfileService:
    limiter = RateLimiter(
        request.app.state.session_factory,
        settings.secret_key,
        window_seconds=settings.rate_limit_window_seconds,
    )
    return ProfileService(db, settings, limiter)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


def _out(profile: Profile, user: User, settings: Settings) -> ProfileOut:
    return ProfileOut.from_profile(
        profile,
        consent_version=settings.ai_consent_version,
        photo_available=user.google_picture_url is not None,
    )


_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    404: {"model": ErrorResponse, "description": "No profile yet (`profile_not_found`)."},
}
_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_ERRORS,
    415: {"model": ErrorResponse, "description": "The body is not JSON."},
    422: {"model": ErrorResponse, "description": "Validation failed."},
    429: {"model": ErrorResponse, "description": "Too many saves; retry later."},
}


@router.get("", summary="Get my profile", responses=_ERRORS)
async def get_profile(
    auth: AuthDep, service: ProfileServiceDep, settings: SettingsDep
) -> ProfileOut:
    profile = await service.get(auth.user)
    return _out(profile, auth.user, settings)


@router.put(
    "",
    summary="Create or replace my profile",
    dependencies=[Depends(require_json), Depends(require_storage_capacity)],
    responses={
        **_WRITE_ERRORS,
        400: {"model": ErrorResponse, "description": "AI consent missing (`ai_consent_required`)."},
        503: {"model": ErrorResponse, "description": "Storage nearly full; try again later."},
    },
)
async def save_profile(
    body: ProfileIn, auth: AuthDep, service: ProfileServiceDep, settings: SettingsDep
) -> ProfileOut:
    """Saves at once. If the about text changed, ``parse_status`` is ``pending`` until a
    background job has read it (usually seconds); poll ``GET /me/profile``."""
    profile = await service.save(auth.user, body)
    return _out(profile, auth.user, settings)


@router.patch(
    "",
    summary="Change my profile settings",
    dependencies=[Depends(require_json)],
    responses={
        **_WRITE_ERRORS,
        409: {
            "model": ErrorResponse,
            "description": "No Google account picture to show (`photo_unavailable`).",
        },
    },
)
async def update_profile_settings(
    body: ProfileSettingsIn, auth: AuthDep, service: ProfileServiceDep, settings: SettingsDep
) -> ProfileOut:
    """Name, links, timezone, languages and visibility (``paused`` hides the profile from
    new matches). The about text changes only through ``PUT``."""
    profile = await service.update_settings(auth.user, body)
    return _out(profile, auth.user, settings)


@router.put(
    "/understanding",
    summary="Correct what was understood from my profile",
    dependencies=[Depends(require_json)],
    responses={
        **_WRITE_ERRORS,
        409: {"model": ErrorResponse, "description": "No about text (`profile_text_required`)."},
    },
)
async def correct_understanding(
    body: UnderstandingIn, auth: AuthDep, service: ProfileServiceDep, settings: SettingsDep
) -> ProfileOut:
    """Replaces the parsed summary, offers, seeks, interests and availability with the
    user's version; matching uses it from the next embedding (a background job)."""
    profile = await service.correct(auth.user, body)
    return _out(profile, auth.user, settings)
