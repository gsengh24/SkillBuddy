"""Session factory and the FastAPI dependency that provides a session per request."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False lets endpoints read attributes after committing without
    # triggering implicit (and, under asyncio, illegal) lazy refreshes.
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session bound to the app's engine; roll back if the request fails."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
