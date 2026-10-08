"""The admin Settings page (A6): feature switches, limits, and read-only server values.
Owners and admins only ("Settings and switches"); every change takes a reason and is
audited. Changes reach every process within 60 seconds, without a deploy."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.models import INTENTS
from app.schemas.admin_settings import (
    FeatureIn,
    FeatureStateOut,
    LimitIn,
    LimitStateOut,
    ServerSettingsOut,
    SettingsOut,
)
from app.schemas.errors import ErrorResponse
from app.services import app_settings, signup
from app.services.admin import settings as admin_settings
from app.services.admin.permissions import Permission
from app.services.app_settings import LIMITS, Feature, Limit

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}

router = APIRouter(prefix="/admin/settings", tags=["admin"], responses=_ERRORS)

Manager = Annotated[AdminContext, Depends(require_admin(Permission.MANAGE_SETTINGS))]


@router.get("", summary="Feature switches, limits and server settings")
async def get_settings(_: Manager, db: DbDep, settings: SettingsDep) -> SettingsOut:
    # Fresh from the database, not the cache: the page shows what is stored now.
    app_settings.cache.invalidate()
    features = await app_settings.all_features(db)
    limits = await app_settings.all_limits(db, settings)
    return SettingsOut(
        server=ServerSettingsOut(
            app_name=settings.app_name,
            terms_version=settings.terms_version,
            environment=settings.environment.value,
        ),
        signup_mode=await signup.signup_mode(db),
        features=[FeatureStateOut(key=key, on=on) for key, on in features.items()],
        limits=[
            LimitStateOut(
                key=key,
                value=value,
                default=LIMITS[key].default(settings),
                minimum=LIMITS[key].minimum,
                maximum=LIMITS[key].maximum,
            )
            for key, value in limits.items()
        ],
        intents=list(INTENTS),
    )


@router.post(
    "/features/{feature}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Turn a feature on or off",
    dependencies=[Depends(require_json)],
)
async def set_feature(
    feature: Feature, body: FeatureIn, request: Request, admin: Manager, db: DbDep
) -> None:
    """Off: its endpoints answer 503 ``feature_off`` (AI matching falls back to the rule-based
    path; email notifications are skipped). Applies within 60 seconds."""
    await admin_settings.set_feature(
        db, admin.who, feature, body.on, body.reason, client_ip(request)
    )


@router.post(
    "/limits/{limit}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Change a limit",
    dependencies=[Depends(require_json)],
    responses={HTTPStatus.UNPROCESSABLE_ENTITY.value: {"model": ErrorResponse}},
)
async def set_limit(
    limit: Limit, body: LimitIn, request: Request, admin: Manager, db: DbDep
) -> None:
    """422 ``limit_out_of_range`` outside the limit's minimum and maximum."""
    await admin_settings.set_limit(
        db, admin.who, limit, body.value, body.reason, client_ip(request)
    )
