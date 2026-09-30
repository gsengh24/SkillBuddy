"""The schema behaves as designed on a real PostgreSQL + pgvector database."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import (
    EMBEDDING_DIMENSIONS,
    AuthProvider,
    EmbeddingFacet,
    Profile,
    ProfileEmbedding,
    User,
)


@pytest.fixture
async def session(integration_settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(integration_settings)
    try:
        async with create_session_factory(engine)() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"Person.{uuid.uuid4().hex}@Example.com", auth_provider=AuthProvider.EMAIL)
    session.add(user)
    await session.flush()
    return user


async def test_user_defaults_and_case_insensitive_email(session: AsyncSession) -> None:
    user = await _create_user(session)
    await session.refresh(user)

    assert user.status == "active"
    assert user.created_at.tzinfo is not None
    found = await session.scalar(select(User).where(User.email == user.email.lower()))
    assert found is user


async def test_profile_defaults(session: AsyncSession) -> None:
    user = await _create_user(session)
    session.add(Profile(user_id=user.id, raw_about_text="I build budgeting apps."))
    await session.flush()

    profile = await session.get_one(Profile, user.id)
    assert profile.structured == {}
    assert profile.languages == []
    assert profile.visibility == "matchable"


async def test_nearest_neighbour_by_cosine_distance(session: AsyncSession) -> None:
    near, far = await _create_user(session), await _create_user(session)
    session.add_all(
        [
            ProfileEmbedding(
                user_id=near.id,
                facet=EmbeddingFacet.OFFER,
                embedding=_unit_vector(0),
                model_version="test-model@1",
            ),
            ProfileEmbedding(
                user_id=far.id,
                facet=EmbeddingFacet.OFFER,
                embedding=_unit_vector(1),
                model_version="test-model@1",
            ),
        ]
    )
    await session.flush()

    query = (
        select(ProfileEmbedding.user_id)
        .where(ProfileEmbedding.facet == EmbeddingFacet.OFFER)
        .where(ProfileEmbedding.user_id.in_([near.id, far.id]))
        .order_by(ProfileEmbedding.embedding.cosine_distance(_unit_vector(0)))
    )
    assert list(await session.scalars(query)) == [near.id, far.id]


async def test_one_embedding_per_user_and_facet(session: AsyncSession) -> None:
    user = await _create_user(session)
    for _ in range(2):
        session.add(
            ProfileEmbedding(
                user_id=user.id,
                facet=EmbeddingFacet.SEEK,
                embedding=_unit_vector(2),
                model_version="test-model@1",
            )
        )

    with pytest.raises(IntegrityError, match="uq_profile_embeddings_user_id_facet"):
        await session.flush()


async def test_unknown_facet_is_rejected(session: AsyncSession) -> None:
    user = await _create_user(session)
    session.add(
        ProfileEmbedding(
            user_id=user.id, facet="salary", embedding=_unit_vector(3), model_version="m@1"
        )
    )

    with pytest.raises(IntegrityError, match="ck_profile_embeddings_facet_valid"):
        await session.flush()


async def test_deleting_user_removes_personal_data(session: AsyncSession) -> None:
    user = await _create_user(session)
    session.add(Profile(user_id=user.id))
    session.add(
        ProfileEmbedding(
            user_id=user.id,
            facet=EmbeddingFacet.IDENTITY,
            embedding=_unit_vector(4),
            model_version="test-model@1",
        )
    )
    await session.flush()

    await session.execute(delete(User).where(User.id == user.id))

    for model in (Profile, ProfileEmbedding):
        count = await session.scalar(
            select(func.count()).select_from(model).where(model.user_id == user.id)
        )
        assert count == 0, model.__name__
