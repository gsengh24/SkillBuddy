"""Aggregates every v1 route module under the ``/api/v1`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(health.router)
