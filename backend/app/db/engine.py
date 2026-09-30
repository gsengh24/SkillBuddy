"""Async SQLAlchemy engine construction."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the process-wide engine. Call once, at startup, and dispose on shutdown."""
    return create_async_engine(
        settings.database_url.unicode_string(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_pre_ping=True,
        echo=settings.db_echo,
        connect_args={"application_name": settings.app_name},
    )
