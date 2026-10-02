"""Stage 1 for profiles: the about text becomes ``structured`` (ADR 0007; ARCHITECTURE.md §3).

Runs in the ``parse_profile`` job, never in a request. The text is parsed only when it has
changed since the last parse (hash-based caching), and a user's own correction of the
result is never overwritten by a parse of the same text.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, Source
from app.ai.stages import Understanding, understand
from app.ai.stages.understand import PROMPT_ID
from app.models import ParseSource, ParseStatus, Profile

logger = logging.getLogger(__name__)

# Profiles the backfill queues per run; it queues itself again while more are pending.
BACKFILL_BATCH_SIZE: Final = 200

AfterParse = Callable[[AsyncSession, uuid.UUID], Awaitable[None]]


def text_hash(text: str) -> str:
    """SHA-256 of the text with whitespace normalised, so spacing edits do not re-parse."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def structured_from(understanding: Understanding) -> dict[str, Any]:
    """The ``profiles.structured`` document: the four facet keys plus availability."""
    return {**understanding.facets(), "availability": understanding.availability}


async def parse_profile(
    session_factory: async_sessionmaker[AsyncSession],
    gateway: AIGateway,
    user_id: uuid.UUID,
    *,
    after_parse: AfterParse,
) -> bool:
    """Parse one profile if its text changed. Returns True if ``structured`` was replaced.

    ``after_parse`` runs in the same transaction as the update (it queues the embedding).
    """
    async with session_factory() as db:
        profile = await db.get(Profile, user_id)
        if profile is None or not profile.raw_about_text.strip():
            return False
        digest = text_hash(profile.raw_about_text)
        if profile.parsed_text_hash == digest and profile.parse_status == ParseStatus.PARSED:
            return False
        text = profile.raw_about_text
        names = [profile.display_name] if profile.display_name.strip() else []

    # No transaction is held open during the model call.
    result = await understand(gateway, text, user_id=str(user_id), name_hints=names)

    async with session_factory() as db:
        profile = await db.scalar(
            select(Profile).where(Profile.user_id == user_id).with_for_update()
        )
        if profile is None or text_hash(profile.raw_about_text) != digest:
            # Deleted, or edited meanwhile: the job queued by that edit parses the new text.
            return False
        if profile.parse_source == ParseSource.USER and profile.parsed_text_hash == digest:
            return False
        llm = result.source is Source.LLM
        profile.structured = structured_from(result.value)
        profile.parse_source = ParseSource.LLM if llm else ParseSource.TEMPLATE
        profile.parse_prompt_version = PROMPT_ID if llm else None
        profile.parsed_text_hash = digest
        profile.parsed_at = datetime.now(UTC)
        profile.parse_status = ParseStatus.PARSED
        await after_parse(db, user_id)
        await db.commit()
    logger.info(
        "profile_parsed",
        extra={
            "source": result.source.value,
            "reason": result.reason.value if result.reason else None,
        },
    )
    return True


async def pending_profiles(
    db: AsyncSession, *, after: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    """Pending profiles in id order after ``after``, so a backfill can resume where it left off."""
    query = select(Profile.user_id).where(Profile.parse_status == ParseStatus.PENDING)
    if after is not None:
        query = query.where(Profile.user_id > after)
    rows = await db.scalars(query.order_by(Profile.user_id).limit(limit))
    return list(rows)
