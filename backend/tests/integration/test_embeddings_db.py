"""Profile embeddings on real PostgreSQL + pgvector: 384-d column, facets, re-embed job."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.embeddings import FakeEmbedder
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobRegistry, JobRunner, enqueue
from app.jobs.tasks import REEMBED_PROFILES
from app.models import EmbeddingFacet
from app.services.embeddings import (
    EmbeddingDimensionMismatchError,
    column_dimensions,
    embed_profile,
    facet_texts,
    profiles_needing_embeddings,
    reembed_batch,
)
from tests.integration.conftest import run_sql


@pytest.fixture
async def session_factory(
    integration_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(integration_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _profile(url: str, about: str = "", structured: str = "{}") -> uuid.UUID:
    user = run_sql(
        url,
        "INSERT INTO users (email) VALUES (:e) RETURNING id",
        e=f"emb-{uuid.uuid4().hex[:12]}@example.com",
    )[0]["id"]
    run_sql(
        url,
        "INSERT INTO profiles (user_id, raw_about_text, structured) "
        "VALUES (:u, :a, CAST(:s AS jsonb))",
        u=user,
        a=about,
        s=structured,
    )
    return uuid.UUID(str(user))


def _stored(url: str, user_id: uuid.UUID) -> list[dict[str, Any]]:
    return run_sql(
        url,
        "SELECT facet, model_version, vector_dims(embedding) AS dims, embedding::text AS v "
        "FROM profile_embeddings WHERE user_id = :u ORDER BY facet",
        u=user_id,
    )


async def test_column_is_384_dimensional(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as db:
        assert await column_dimensions(db) == 384


async def test_embed_profile_stores_four_facets_and_replaces_them(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    user = _profile(
        migrated_database_url,
        "I build backends.",
        '{"offers": ["Python"], "seeks": ["a designer"]}',
    )
    embedder = FakeEmbedder()
    async with session_factory() as db:
        assert await embed_profile(db, embedder, user) is True
        first = _stored(migrated_database_url, user)
        assert await embed_profile(db, embedder, user) is True  # upsert, no duplicates

    rows = _stored(migrated_database_url, user)
    assert [row["facet"] for row in rows] == sorted(facet.value for facet in EmbeddingFacet)
    assert {row["dims"] for row in rows} == {384}
    assert {row["model_version"] for row in rows} == {"fake-embedder@1"}
    assert [row["v"] for row in rows] == [row["v"] for row in first]
    # Different facets, different text, different vectors.
    by_facet = {row["facet"]: row["v"] for row in rows}
    assert by_facet["offer"] != by_facet["seek"]
    # The offer facet is the embedding of the parsed offers, not of the raw text.
    texts = facet_texts("I build backends.", {"offers": ["Python"], "seeks": ["a designer"]})
    assert texts[EmbeddingFacet.OFFER] == "Python"
    expected_offer = (await embedder.embed(["Python"], kind="passage"))[0]
    distance = run_sql(
        migrated_database_url,
        "SELECT embedding <=> CAST(:v AS vector) AS d FROM profile_embeddings "
        "WHERE user_id = :u AND facet = 'offer'",
        v=str(expected_offer),
        u=user,
    )
    assert distance[0]["d"] < 1e-6


async def test_profile_without_text_is_not_embedded(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    empty = _profile(migrated_database_url, "   ")
    async with session_factory() as db:
        assert await embed_profile(db, FakeEmbedder(), empty) is False
        assert await embed_profile(db, FakeEmbedder(), uuid.uuid4()) is False
        assert empty not in await profiles_needing_embeddings(db, "fake-embedder@1", 10_000)
    assert _stored(migrated_database_url, empty) == []


async def test_reembed_works_through_profiles_in_batches(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    mine = [_profile(migrated_database_url, f"Profile number {n}.") for n in range(3)]
    embedder = FakeEmbedder()
    async with session_factory() as db:
        rounds = 0
        while True:
            rounds += 1
            _, more = await reembed_batch(db, embedder, batch_size=2)
            if not more:
                break
        pending = await profiles_needing_embeddings(db, embedder.model_version, 10_000)

    assert rounds >= 2
    for user in mine:
        assert len(_stored(migrated_database_url, user)) == 4
        assert user not in pending


async def test_reembed_refuses_vectors_that_do_not_fit_the_column(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class Wrong(FakeEmbedder):
        dimensions = 768  # type: ignore[misc]  # deliberately wrong for this test

    async with session_factory() as db:
        with pytest.raises(EmbeddingDimensionMismatchError, match="vector\\(384\\)"):
            await reembed_batch(db, Wrong())


async def test_reembed_job_runs_on_the_job_runner(
    session_factory: async_sessionmaker[AsyncSession],
    integration_settings: Settings,
    migrated_database_url: str,
) -> None:
    user = _profile(migrated_database_url, "Guitarist looking for a weekend jam.")
    async with session_factory() as db:
        await enqueue(db, REEMBED_PROFILES)
        await db.commit()

    await JobRunner(
        session_factory, JobRegistry([REEMBED_PROFILES]), integration_settings
    ).run_until_idle()

    assert len(_stored(migrated_database_url, user)) == 4
    queued = run_sql(
        migrated_database_url,
        "SELECT count(*) AS n FROM jobs WHERE kind = 'reembed_profiles' AND status = 'queued'",
    )
    assert queued == [{"n": 0}]  # it ran until no profile was left


async def test_migration_queued_the_reembed(migrated_database_url: str) -> None:
    rows = run_sql(
        migrated_database_url,
        "SELECT kind FROM jobs WHERE dedupe_key = 'reembed_profiles:migration-0004'",
    )
    assert rows == [{"kind": "reembed_profiles"}]
