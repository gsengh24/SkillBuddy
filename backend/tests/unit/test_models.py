"""Schema shape checks that need no database. Migrations are tested in integration."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, DateTime, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import Base
from app.models import EMBEDDING_DIMENSIONS, EmbeddingFacet


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_metadata_contains_phase_zero_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "profiles", "profile_embeddings"}


def test_every_table_uses_timezone_aware_timestamps() -> None:
    for table in Base.metadata.tables.values():
        for column in ("created_at", "updated_at"):
            column_type = table.c[column].type
            assert isinstance(column_type, DateTime)
            assert column_type.timezone is True, f"{table.name}.{column}"


def test_embedding_ddl_uses_vector_and_hnsw_cosine_index() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    table = _table("profile_embeddings")
    create_table = str(CreateTable(table).compile(dialect=dialect))
    indexes = [str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes]

    assert f"embedding VECTOR({EMBEDDING_DIMENSIONS}) NOT NULL" in create_table
    assert "UNIQUE (user_id, facet)" in create_table
    assert any("USING hnsw (embedding vector_cosine_ops)" in ddl for ddl in indexes)


def test_facet_check_constraint_matches_enum() -> None:
    constraint_sql = next(
        str(constraint.sqltext)
        for constraint in _table("profile_embeddings").constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_profile_embeddings_facet_valid"
    )

    for facet in EmbeddingFacet:
        assert f"'{facet.value}'" in constraint_sql
