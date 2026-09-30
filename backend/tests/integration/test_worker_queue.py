"""A job enqueued the way the API will enqueue it is executed by an Arq worker."""

from __future__ import annotations

import uuid

from arq import Worker, create_pool
from arq.connections import RedisSettings

from app.core.config import Settings
from app.worker.jobs import ping


async def test_ping_job_round_trip(settings: Settings) -> None:
    # A unique queue keeps this test independent of any worker running in dev.
    queue_name = f"test:{uuid.uuid4().hex}"
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url.unicode_string()))
    worker = Worker(
        functions=[ping],
        queue_name=queue_name,
        redis_pool=redis,
        burst=True,
        handle_signals=False,
        poll_delay=0.05,
    )
    try:
        job = await redis.enqueue_job("ping", _queue_name=queue_name)
        assert job is not None

        await worker.main()

        assert await job.result(timeout=5) == "pong"
    finally:
        await worker.close()
