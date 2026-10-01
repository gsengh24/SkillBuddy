"""Application factory.

Run with ``uvicorn app.main:create_app --factory``. Building the app in a function (not
at import time) keeps settings, connections and middleware explicit, and lets tests
create isolated app instances with their own settings.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import ConnectionPool, Redis

from app.api.deps import CSRF_HEADER
from app.api.v1.router import api_router
from app.core.config import Environment, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.security import SecurityHeadersMiddleware
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.runner import JobRunner
from app.jobs.tasks import build_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared connection pools and start the job runner; stop both on shutdown.

    Pools connect lazily, so the API starts (and reports liveness) even while a
    dependency is down; the readiness probe is what reports the outage.

    The in-process job runner (ADR 0008) always runs jobs with a secret (login codes,
    whose code exists only in this process). With ``JOBS_RUN_IN_API`` it runs every job.
    """
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    redis_pool = ConnectionPool.from_url(
        settings.redis_url.unicode_string(),
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    redis = Redis(connection_pool=redis_pool)
    session_factory = create_session_factory(engine)

    registry = build_registry()
    if not settings.jobs_run_in_api:
        registry = registry.subset(lambda spec: spec.needs_secret)
    runner = JobRunner(session_factory, registry, settings)
    runner_task = asyncio.create_task(runner.run_forever(), name="job-runner")

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis
    app.state.job_runner = runner
    logger.info(
        "startup",
        extra={
            "app_name": settings.app_name,
            "environment": settings.environment.value,
            "jobs_run_in_api": settings.jobs_run_in_api,
        },
    )
    try:
        yield
    finally:
        runner.stop()
        await runner_task
        await redis.aclose()
        await redis_pool.aclose()
        await engine.dispose()
        logger.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.state.settings = settings

    # Middleware added last runs first: request context wraps everything else, so even
    # CORS preflights and security-header responses carry a request id.
    deployed = settings.environment in {Environment.STAGING, Environment.PRODUCTION}
    app.add_middleware(SecurityHeadersMiddleware, hsts=deployed)
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", CSRF_HEADER, REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    return app
