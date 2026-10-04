"""Aggregates every v1 route module under the ``/api/v1`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    account,
    admin,
    auth,
    blocks,
    chat,
    health,
    jobs,
    moderation,
    profile,
    requests,
    social,
    spaces,
)

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(account.router)
api_router.include_router(profile.router)
api_router.include_router(requests.router)
api_router.include_router(social.router)
api_router.include_router(chat.router)
api_router.include_router(blocks.router)
api_router.include_router(spaces.router)
api_router.include_router(moderation.router)
api_router.include_router(admin.router)
api_router.include_router(jobs.router)
