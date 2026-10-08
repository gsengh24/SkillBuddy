"""Public, tiny reads for every client: which features are on (A6) and the current banner
(A8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep
from app.db.session import get_db_session
from app.schemas.admin_comms import BannerOut, CurrentBannerOut
from app.schemas.admin_settings import FeaturesOut
from app.services import app_settings, banners

router = APIRouter(tags=["features"])


@router.get("/features", summary="Features switched on right now")
async def features(
    settings: SettingsDep, db: Annotated[AsyncSession, Depends(get_db_session)]
) -> FeaturesOut:
    """Public. Changes made on the admin Settings page show here within 60 seconds."""
    return FeaturesOut(
        features=await app_settings.all_features(db),
        message_max_length=await app_settings.limit(
            db, settings, app_settings.Limit.MESSAGE_MAX_LENGTH
        ),
    )


@router.get("/banner", summary="The banner to show at the top of the app")
async def current_banner(
    response: Response, db: Annotated[AsyncSession, Depends(get_db_session)]
) -> CurrentBannerOut:
    """Public; cached for 60 seconds (here and by the browser). Plain text: never render it
    as HTML. Dismissing is up to the client (remember the ``id``)."""
    response.headers["Cache-Control"] = "public, max-age=60"
    found = await banners.active(db)
    return CurrentBannerOut(banner=BannerOut.from_active(found) if found else None)
