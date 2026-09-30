"""ORM models. Import every model here so ``Base.metadata`` is complete for Alembic."""

from app.models.profile import Profile, ProfileVisibility
from app.models.profile_embedding import EMBEDDING_DIMENSIONS, EmbeddingFacet, ProfileEmbedding
from app.models.user import AuthProvider, User, UserStatus

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "AuthProvider",
    "EmbeddingFacet",
    "Profile",
    "ProfileEmbedding",
    "ProfileVisibility",
    "User",
    "UserStatus",
]
