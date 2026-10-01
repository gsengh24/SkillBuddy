"""ORM models. Import every model here so ``Base.metadata`` is complete for Alembic."""

from app.models.auth import AuthEvent, AuthEventType, AuthIdentity, OtpCode, UserSession
from app.models.jobs import EmailLog, EmailPurpose, Job, JobStatus, RateLimitCounter
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
    "EmailLog",
    "EmailPurpose",
    "EmbeddingFacet",
    "Job",
    "JobStatus",
    "OtpCode",
    "Profile",
    "ProfileEmbedding",
    "ProfileVisibility",
    "RateLimitCounter",
    "User",
    "UserSession",
    "UserStatus",
]
