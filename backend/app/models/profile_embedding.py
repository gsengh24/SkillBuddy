"""Per-facet vector embeddings of a profile, used for candidate retrieval.

Each profile has up to one embedding per facet. Different match intents search
different facet pairs (e.g. "build together" compares my ``seek`` with your ``offer``).
``model_version`` records which embedding model produced the vector, so changing
models is a background re-embed rather than a schema migration.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Final

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIMENSIONS: Final = 768


class EmbeddingFacet(StrEnum):
    IDENTITY = "identity"
    OFFER = "offer"
    SEEK = "seek"
    INTEREST = "interest"


class ProfileEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profile_embeddings"
    __table_args__ = (
        UniqueConstraint("user_id", "facet"),
        CheckConstraint(
            "facet IN ('identity', 'offer', 'seek', 'interest')",
            name="facet_valid",
        ),
        # Approximate nearest-neighbour index for cosine distance (the ``<=>`` operator).
        Index(
            "ix_profile_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # Embeddings are personal data: they go when the account goes.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    facet: Mapped[str] = mapped_column(String(16))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    model_version: Mapped[str] = mapped_column(String(128))
