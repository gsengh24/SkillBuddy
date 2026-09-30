"""Initial schema: users, profiles and per-facet profile embeddings.

Revision ID: 0001
Revises:
Create Date: 2026-10-01 00:00:00+00:00
"""

from collections.abc import Sequence
from typing import Any

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSIONS = 768  # Frozen here: later changes need their own migration.


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("auth_provider", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.CheckConstraint(
            "auth_provider IN ('email', 'google')", name=op.f("ck_users_auth_provider_valid")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')", name=op.f("ck_users_status_valid")
        ),
    )

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("raw_about_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "structured",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=35)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            sa.String(length=32),
            server_default=sa.text("'matchable'"),
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "visibility IN ('matchable', 'paused')", name=op.f("ck_profiles_visibility_valid")
        ),
    )

    op.create_table(
        "profile_embeddings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("facet", sa.String(length=16), nullable=False),
        sa.Column(
            "embedding", pgvector.sqlalchemy.Vector(dim=EMBEDDING_DIMENSIONS), nullable=False
        ),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_embeddings")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_profile_embeddings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "facet", name=op.f("uq_profile_embeddings_user_id_facet")),
        sa.CheckConstraint(
            "facet IN ('identity', 'offer', 'seek', 'interest')",
            name=op.f("ck_profile_embeddings_facet_valid"),
        ),
    )
    op.create_index(
        "ix_profile_embeddings_embedding_hnsw",
        "profile_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_profile_embeddings_embedding_hnsw", table_name="profile_embeddings")
    op.drop_table("profile_embeddings")
    op.drop_table("profiles")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS vector")
