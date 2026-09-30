"""Migrations apply, reverse and re-apply cleanly, and match the ORM models."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

from app.db.base import Base
from tests.integration.conftest import alembic_config

PHASE_ZERO_TABLES = {"users", "profiles", "profile_embeddings"}


@pytest.fixture
def engine(empty_database_url: str) -> Iterator[Engine]:
    engine = create_engine(empty_database_url)
    yield engine
    engine.dispose()


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _extensions(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        return set(connection.scalars(text("SELECT extname FROM pg_extension")))


def _hnsw_index_definition(engine: Engine) -> str | None:
    with engine.connect() as connection:
        definition = connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'ix_profile_embeddings_embedding_hnsw'"
            )
        )
    return None if definition is None else str(definition)


def test_upgrade_downgrade_upgrade(empty_database_url: str, engine: Engine) -> None:
    config = alembic_config(empty_database_url)

    command.upgrade(config, "head")
    assert _tables(engine) == PHASE_ZERO_TABLES
    assert {"vector", "citext"} <= _extensions(engine)
    index_definition = _hnsw_index_definition(engine)
    assert index_definition is not None
    assert "USING hnsw (embedding vector_cosine_ops)" in index_definition

    command.downgrade(config, "base")
    assert _tables(engine) == set()
    assert not {"vector", "citext"} & _extensions(engine)

    command.upgrade(config, "head")
    assert _tables(engine) == PHASE_ZERO_TABLES


def test_models_and_migrations_are_in_sync(migrated_database_url: str) -> None:
    """Fails if a model changed without a migration (or vice versa)."""
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"Models and migrations differ; run `make revision`: {diff}"
