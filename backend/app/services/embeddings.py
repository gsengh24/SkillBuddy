"""Profile embeddings: the four facets, embedded and stored per profile (ADR 0007).

Each profile gets one vector per facet, so different intents can search different
facets ("build together" compares my *seek* with your *offer*):

- identity: who they are overall (the parsed summary, or the whole text);
- offer: what they can give (skills, knowledge, time);
- seek: what they are looking for;
- interest: topics they care about.

Facet text comes from ``profiles.structured`` (filled by the Understand stage). Until a
profile has been parsed, every facet uses the profile's own text (ADR 0007, section 6).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Final

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import Embedder
from app.models import EmbeddingFacet, Profile, ProfileEmbedding

logger = logging.getLogger(__name__)

# The keys of ``profiles.structured`` each facet is built from (the Understand stage's
# output contract). A missing or empty key falls back to the profile's own text.
FACET_SOURCES: Final[dict[EmbeddingFacet, str]] = {
    EmbeddingFacet.IDENTITY: "summary",
    EmbeddingFacet.OFFER: "offers",
    EmbeddingFacet.SEEK: "seeks",
    EmbeddingFacet.INTEREST: "interests",
}

REEMBED_BATCH_SIZE: Final = 25


class EmbeddingDimensionMismatchError(RuntimeError):
    """The model's vectors do not fit the column; changing it needs a migration."""


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return ""


def facet_texts(raw_about_text: str, structured: dict[str, Any]) -> dict[EmbeddingFacet, str]:
    """The text for each of the four facets, or nothing if the profile has no text at all.

    A facet without its own parsed text falls back to the profile's own words, or failing
    that to the other parsed text, so a profile with any text always gets all four.
    """
    own = {
        facet: " ".join(_as_text(structured.get(key)).split())
        for facet, key in FACET_SOURCES.items()
    }
    fallback = " ".join(raw_about_text.split()) or " ".join(t for t in own.values() if t)
    if not fallback:
        return {}
    return {facet: own[facet] or fallback for facet in FACET_SOURCES}


async def column_dimensions(db: AsyncSession) -> int:
    """The dimension of ``profile_embeddings.embedding`` as migrated (pgvector's typmod)."""
    value = await db.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'profile_embeddings'::regclass AND attname = 'embedding'"
        )
    )
    return int(value)


async def ensure_dimensions_match(db: AsyncSession, embedder: Embedder) -> None:
    dims = await column_dimensions(db)
    if dims != embedder.dimensions:
        raise EmbeddingDimensionMismatchError(
            f"model makes {embedder.dimensions}-d vectors but the column is vector({dims})"
        )


async def embed_profile(db: AsyncSession, embedder: Embedder, user_id: uuid.UUID) -> bool:
    """(Re-)embed one profile's facets. Returns False if it has no text. Commits."""
    profile = await db.get(Profile, user_id)
    if profile is None:
        return False
    texts = facet_texts(profile.raw_about_text, profile.structured)
    if not texts:
        return False
    vectors = await embedder.embed(list(texts.values()), kind="passage")
    for facet, vector in zip(texts, vectors, strict=True):
        statement = insert(ProfileEmbedding).values(
            user_id=user_id,
            facet=facet.value,
            embedding=vector,
            model_version=embedder.model_version,
        )
        await db.execute(
            statement.on_conflict_do_update(
                constraint="uq_profile_embeddings_user_id_facet",
                set_={
                    "embedding": statement.excluded.embedding,
                    "model_version": statement.excluded.model_version,
                    "updated_at": func.now(),
                },
            )
        )
    await db.commit()
    return True


async def profiles_needing_embeddings(
    db: AsyncSession, model_version: str, limit: int
) -> list[uuid.UUID]:
    """Profiles with text that lack a current-model vector for every facet they have."""
    complete = (
        select(ProfileEmbedding.user_id)
        .where(ProfileEmbedding.model_version == model_version)
        .group_by(ProfileEmbedding.user_id)
        .having(func.count() >= len(FACET_SOURCES))
    )
    rows = await db.scalars(
        select(Profile.user_id)
        .where(
            (func.btrim(Profile.raw_about_text) != "")
            | (Profile.structured != text("'{}'::jsonb")),
            Profile.user_id.not_in(complete),
        )
        .order_by(Profile.user_id)
        .limit(limit)
    )
    return list(rows)


async def reembed_batch(
    db: AsyncSession, embedder: Embedder, *, batch_size: int = REEMBED_BATCH_SIZE
) -> tuple[int, bool]:
    """Embed the next batch of profiles that need it. Returns (embedded, more_left)."""
    await ensure_dimensions_match(db, embedder)
    due = await profiles_needing_embeddings(db, embedder.model_version, batch_size + 1)
    embedded = 0
    for user_id in due[:batch_size]:
        if await embed_profile(db, embedder, user_id):
            embedded += 1
    # A batch that embedded nothing cannot make progress: stop rather than loop forever.
    more = len(due) > batch_size and embedded > 0
    logger.info(
        "profiles_reembedded",
        extra={"count": embedded, "model": embedder.model_version, "more": more},
    )
    return embedded, more
