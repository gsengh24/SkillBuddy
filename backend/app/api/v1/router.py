"""Aggregates every v1 route module under the ``/api/v1`` prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    account,
    admin,
    admin_access,
    admin_comms,
    admin_content,
    admin_data,
    admin_overview,
    admin_portal,
    admin_safety,
    admin_settings,
    admin_users,
    appeals,
    auth,
    blocks,
    chat,
    features,
    health,
    jobs,
    moderation,
    profile,
    requests,
    social,
    spaces,
    team_spaces,
    teams,
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
api_router.include_router(spaces.report_router)
api_router.include_router(teams.router)
api_router.include_router(team_spaces.router)
api_router.include_router(moderation.router)
api_router.include_router(admin.router)
api_router.include_router(admin_portal.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_safety.router)
api_router.include_router(admin_overview.router)
api_router.include_router(admin_access.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_content.router)
api_router.include_router(admin_comms.router)
api_router.include_router(admin_data.router)
api_router.include_router(features.router)
api_router.include_router(appeals.router)
api_router.include_router(jobs.router)
