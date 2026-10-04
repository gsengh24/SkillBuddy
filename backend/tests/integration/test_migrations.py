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
AUTH_TABLES = {"auth_identities", "otp_codes", "sessions", "auth_events"}
JOB_TABLES = {"jobs", "rate_limit_counters", "email_log"}
GOOGLE_TABLES = {"oauth_states"}  # migration 0006 (ADR 0011)
MATCH_TABLES = {"match_requests", "matches"}  # migration 0007
SOCIAL_TABLES = {"intros", "connections", "notifications"}  # migration 0008
CHAT_TABLES = {"messages"}  # migration 0009 (ADR 0012)
REPORT_TABLES = {"reports"}  # migration 0010
BLOCK_TABLES = {"blocks"}  # migration 0011
MODERATION_TABLES = {"moderation_actions"}  # migration 0013
SPACE_TABLES = {"space_goals", "space_skills", "progress_logs"}  # migration 0014
ALL_TABLES = (
    PHASE_ZERO_TABLES
    | AUTH_TABLES
    | JOB_TABLES
    | GOOGLE_TABLES
    | MATCH_TABLES
    | SOCIAL_TABLES
    | CHAT_TABLES
    | REPORT_TABLES
    | BLOCK_TABLES
    | MODERATION_TABLES
    | SPACE_TABLES
)


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
    assert _tables(engine) == ALL_TABLES
    assert {"vector", "citext"} <= _extensions(engine)
    index_definition = _hnsw_index_definition(engine)
    assert index_definition is not None
    assert "USING hnsw (embedding vector_cosine_ops)" in index_definition

    command.downgrade(config, "base")
    assert _tables(engine) == set()
    assert not {"vector", "citext"} & _extensions(engine)

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def _user_columns(engine: Engine) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns("users")}


def test_auth_migration_downgrades_to_0001_and_back(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (email, status, deleted_at, deletion_scheduled_for) "
                "VALUES ('leaving@example.com', 'pending_deletion', now(), now())"
            )
        )

    command.downgrade(config, "0001")
    assert _tables(engine) == PHASE_ZERO_TABLES
    columns = _user_columns(engine)
    assert "auth_provider" in columns
    assert not {"last_login_at", "terms_version", "deletion_scheduled_for"} & columns
    with engine.connect() as connection:
        status = connection.scalar(
            text("SELECT status FROM users WHERE email = 'leaving@example.com'")
        )
    assert status == "deleted"

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES
    assert "auth_provider" not in _user_columns(engine)


def test_job_tables_migration_downgrades_to_0002_and_back(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO jobs (kind) VALUES ('ping')"))

    command.downgrade(config, "0002")
    assert _tables(engine) == PHASE_ZERO_TABLES | AUTH_TABLES

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def test_oauth_states_migration_downgrades_to_0005_and_back(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO oauth_states (state_hash, next_path, age_confirmed, accept_terms, "
                "expires_at) VALUES ('h', '/home', true, true, now())"
            )
        )

    command.downgrade(config, "0005")
    assert _tables(engine) == PHASE_ZERO_TABLES | AUTH_TABLES | JOB_TABLES

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def _connection_columns(engine: Engine) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns("connections")}


def test_chat_migration_keeps_connections_and_downgrades_to_0008(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "0008")
    with engine.begin() as connection:
        ids = sorted(
            connection.scalars(
                text(
                    "INSERT INTO users (email) "
                    "VALUES ('a@example.com'), ('b@example.com') RETURNING id"
                )
            )
        )
        pair = connection.scalar(
            text("INSERT INTO connections (user_a, user_b) VALUES (:a, :b) RETURNING id"),
            {"a": ids[0], "b": ids[1]},
        )

    command.upgrade(config, "0009")
    with engine.begin() as connection:
        # Existing connections are kept, with nothing read yet.
        row = connection.execute(
            text("SELECT user_a_read_at, user_b_read_at FROM connections WHERE id = :id"),
            {"id": pair},
        ).one()
        assert tuple(row) == (None, None)
        connection.execute(
            text("INSERT INTO messages (connection_id, from_a, body) VALUES (:c, true, 'hi')"),
            {"c": pair},
        )

    command.downgrade(config, "0008")
    assert (
        _tables(engine)
        == ALL_TABLES
        - CHAT_TABLES
        - REPORT_TABLES
        - BLOCK_TABLES
        - MODERATION_TABLES
        - SPACE_TABLES
    )
    assert not {"user_a_read_at", "user_b_read_at"} & _connection_columns(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM connections")) == 1

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def _embedding_type(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(
            connection.scalar(
                text(
                    "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                    "WHERE attrelid = 'profile_embeddings'::regclass AND attname = 'embedding'"
                )
            )
        )


def _reembed_jobs(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM jobs WHERE dedupe_key = 'reembed_profiles:migration-0004'"
                )
            )
        )


def test_embedding_migration_resizes_to_384_and_back(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")
    assert _embedding_type(engine) == "vector(384)"
    assert _reembed_jobs(engine) == 1  # the re-embed is queued for the job runner

    command.downgrade(config, "0003")
    assert _embedding_type(engine) == "vector(768)"
    assert _reembed_jobs(engine) == 0
    index_definition = _hnsw_index_definition(engine)
    assert index_definition is not None
    assert "USING hnsw (embedding vector_cosine_ops)" in index_definition

    command.upgrade(config, "head")
    assert _embedding_type(engine) == "vector(384)"
    assert _reembed_jobs(engine) == 1
    assert "vector_cosine_ops" in (_hnsw_index_definition(engine) or "")


def test_models_and_migrations_are_in_sync(migrated_database_url: str) -> None:
    """Fails if a model changed without a migration (or vice versa)."""
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], (
        f"Models and migrations differ; run `alembic revision --autogenerate`: {diff}"
    )


def test_reports_migration_downgrades_to_0009_and_back(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "0009")
    assert _tables(engine) == (
        ALL_TABLES - REPORT_TABLES - BLOCK_TABLES - MODERATION_TABLES - SPACE_TABLES
    )

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def test_blocks_migration_keeps_connections_and_downgrades_to_0010(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "0010")
    with engine.begin() as connection:
        ids = sorted(
            connection.scalars(
                text(
                    "INSERT INTO users (email) "
                    "VALUES ('c@example.com'), ('d@example.com') RETURNING id"
                )
            )
        )
        connection.execute(
            text("INSERT INTO connections (user_a, user_b) VALUES (:a, :b)"),
            {"a": ids[0], "b": ids[1]},
        )

    command.upgrade(config, "0011")
    with engine.begin() as connection:
        # Existing connections stay open.
        assert connection.scalar(text("SELECT ended_at FROM connections")) is None
        connection.execute(
            text("INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)"),
            {"a": ids[0], "b": ids[1]},
        )

    command.downgrade(config, "0010")
    assert _tables(engine) == ALL_TABLES - BLOCK_TABLES - MODERATION_TABLES - SPACE_TABLES
    assert "ended_at" not in _connection_columns(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM connections")) == 1

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES


def test_report_targets_migration_keeps_message_reports(
    empty_database_url: str, engine: Engine
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "0011")
    message = "11111111-0000-4000-8000-00000000000a"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reports (message_id, reason, snapshot) "
                "VALUES (:m, 'spam', '[]'::jsonb)"
            ),
            {"m": message},
        )

    command.upgrade(config, "0012")
    with engine.begin() as connection:
        row = connection.execute(text("SELECT target, target_id FROM reports")).one()
        assert (row[0], str(row[1])) == ("message", message)
        connection.execute(
            text(
                "INSERT INTO reports (target, target_id, reason, snapshot) "
                "VALUES ('intro', gen_random_uuid(), 'spam', '[]'::jsonb)"
            )
        )

    command.downgrade(config, "0011")
    with engine.connect() as connection:
        kept = connection.scalars(text("SELECT message_id FROM reports")).all()
    assert [str(value) for value in kept] == [message]

    command.upgrade(config, "head")
    assert _tables(engine) == ALL_TABLES
