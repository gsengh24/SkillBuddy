"""ORM models. Import every model here so ``Base.metadata`` is complete for Alembic."""

from app.models.auth import AuthEvent, AuthEventType, AuthIdentity, OtpCode, UserSession
from app.models.profile import Profile, ProfileVisibility
from app.models.profile_embedding import EMBEDDING_DIMENSIONS, EmbeddingFacet, ProfileEmbedding
from app.models.user import EMAIL_MAX_LENGTH, AuthProvider, User, UserStatus

__all__ = [
    "EMAIL_MAX_LENGTH",
    "EMBEDDING_DIMENSIONS",
    "AuthEvent",
    "AuthEventType",
    "AuthIdentity",
    "AuthProvider",
    "EmbeddingFacet",
    "OtpCode",
    "Profile",
    "ProfileEmbedding",
    "ProfileVisibility",
    "User",
    "UserSession",
    "UserStatus",
]
