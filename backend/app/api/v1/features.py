"""Which features are switched on (A6), so every client hides what's off."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep
from app.db.session import get_db_session
from app.schemas.admin_settings import FeaturesOut
from app.services import app_settings

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
