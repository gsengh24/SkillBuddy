"""Schema shape checks that need no database. Migrations are tested in integration."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, DateTime, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import Base
from app.models import EMBEDDING_DIMENSIONS, EmbeddingFacet, JobStatus


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_metadata_contains_all_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "profiles",
        "profile_embeddings",
        "auth_identities",
        "otp_codes",
        "oauth_states",
        "sessions",
        "auth_events",
        "jobs",
        "rate_limit_counters",
        "email_log",
        "match_requests",
        "matches",
    }


def test_every_timestamp_is_timezone_aware() -> None:
    for table in Base.metadata.tables.values():
        assert "created_at" in table.c, table.name
        for column in table.c:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True, f"{table.name}.{column.name}"


def test_embedding_ddl_uses_vector_and_hnsw_cosine_index() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    table = _table("profile_embeddings")
    create_table = str(CreateTable(table).compile(dialect=dialect))
    indexes = [str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes]

    assert f"embedding VECTOR({EMBEDDING_DIMENSIONS}) NOT NULL" in create_table
    assert "UNIQUE (user_id, facet)" in create_table
    assert any("USING hnsw (embedding vector_cosine_ops)" in ddl for ddl in indexes)


def test_job_status_check_constraint_matches_enum() -> None:
    constraint_sql = next(
        str(constraint.sqltext)
        for constraint in _table("jobs").constraints
        if isinstance(constraint, CheckConstraint) and constraint.name == "ck_jobs_status_valid"
    )

    for status in JobStatus:
        assert f"'{status.value}'" in constraint_sql


def test_job_claim_index_covers_only_queued_jobs() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    indexes = {
        str(index.name): str(CreateIndex(index).compile(dialect=dialect))
        for index in _table("jobs").indexes
    }

    assert "ON jobs (priority, run_at) WHERE status = 'queued'" in indexes["ix_jobs_claim"]
    assert "WHERE status = 'running'" in indexes["ix_jobs_lease"]


def test_facet_check_constraint_matches_enum() -> None:
    constraint_sql = next(
        str(constraint.sqltext)
        for constraint in _table("profile_embeddings").constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_profile_embeddings_facet_valid"
    )

    for facet in EmbeddingFacet:
        assert f"'{facet.value}'" in constraint_sql
