"""Profile embeddings: vector(768) to vector(384) for bge-small-en-v1.5 (ADR 0007).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02 00:00:00+00:00

Embeddings are derived data and pgvector cannot cast between dimensions, so both directions
delete the stored vectors, change the column and rebuild the HNSW index. The upgrade queues
a ``reembed_profiles`` job on the job runner (ADR 0008), which recomputes every profile's
four facets with the new model. No real data exists yet (ADR 0007).

Storage: about 1.5 KB less per vector, so about 6 KB less per user (4 facets) plus a smaller
HNSW index (docs/storage-budget.md).
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_profile_embeddings_embedding_hnsw"
# Frozen copies of the values at this revision.
NEW_DIMENSIONS = 384
OLD_DIMENSIONS = 768
REEMBED_JOB = "reembed_profiles"
REEMBED_DEDUPE_KEY = "reembed_profiles:migration-0004"


def _resize(dimensions: int) -> None:
    op.drop_index(INDEX, table_name="profile_embeddings")
    op.execute("DELETE FROM profile_embeddings")
    op.alter_column(
        "profile_embeddings",
        "embedding",
        type_=pgvector.sqlalchemy.Vector(dim=dimensions),
        existing_nullable=False,
    )
    op.create_index(
        INDEX,
        "profile_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def upgrade() -> None:
    _resize(NEW_DIMENSIONS)
    # Recompute every profile's vectors with the new model, in the background.
    op.execute(
        sa.text(
            "INSERT INTO jobs (kind, priority, dedupe_key) VALUES (:kind, 300, :key) "
            "ON CONFLICT (dedupe_key) DO NOTHING"
        ).bindparams(kind=REEMBED_JOB, key=REEMBED_DEDUPE_KEY)
    )


def downgrade() -> None:
    # A queued re-embed would write 384-d vectors into the old column, and a finished one
    # would stop a later re-upgrade from queueing it again: remove it either way.
    op.execute(
        sa.text("DELETE FROM jobs WHERE dedupe_key = :key").bindparams(key=REEMBED_DEDUPE_KEY)
    )
    _resize(OLD_DIMENSIONS)
