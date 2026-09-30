"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    """Settings the running app was created with (overridable per app in tests)."""
    settings: Settings = request.app.state.settings
    return settings
