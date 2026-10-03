"""Liveness and readiness probes."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services.health import check_readiness

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness probe")
async def liveness(settings: Annotated[Settings, Depends(get_app_settings)]) -> LivenessResponse:
    """Report that the process is up. Touches no dependencies, so it stays cheap."""
    return LivenessResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ReadinessResponse:
    """Check PostgreSQL and the pgvector extension. Returns 503 if either fails."""
    result = await check_readiness(
        request.app.state.engine, timeout_seconds=settings.readiness_timeout_seconds
    )
    if result.status != "ok":
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    # THROWAWAY (step 8e, never merged): break readiness in the Docker stack only, to prove
    # the Smoke job goes red. Backend tests run with ENVIRONMENT=test and are unaffected.
    if settings.environment == "local":
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    return result
