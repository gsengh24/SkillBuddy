"""ORM models. Import every model here so ``Base.metadata`` is complete for Alembic."""

from app.models.auth import (
    AuthEvent,
    AuthEventType,
    AuthIdentity,
    OAuthState,
    OtpCode,
    UserSession,
)
from app.models.jobs import EmailLog, EmailPurpose, Job, JobStatus, RateLimitCounter
from app.models.matching import (
    INTENTS,
    REQUEST_TEXT_MAX_LENGTH,
    REQUEST_TEXT_MIN_LENGTH,
    Match,
    MatchRequest,
    MatchStatus,
    RequestStatus,
)
from app.models.profile import (
    ABOUT_TEXT_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    LINK_MAX_LENGTH,
    MAX_LANGUAGES,
    MAX_LINKS,
    ParseSource,
    ParseStatus,
    Profile,
    ProfileVisibility,
)
from app.models.profile_embedding import EMBEDDING_DIMENSIONS, EmbeddingFacet, ProfileEmbedding
from app.models.user import EMAIL_MAX_LENGTH, AuthProvider, User, UserStatus

__all__ = [
    "ABOUT_TEXT_MAX_LENGTH",
    "DISPLAY_NAME_MAX_LENGTH",
    "EMAIL_MAX_LENGTH",
    "EMBEDDING_DIMENSIONS",
    "INTENTS",
    "LINK_MAX_LENGTH",
    "MAX_LANGUAGES",
    "MAX_LINKS",
    "REQUEST_TEXT_MAX_LENGTH",
    "REQUEST_TEXT_MIN_LENGTH",
    "AuthEvent",
    "AuthEventType",
    "AuthIdentity",
    "AuthProvider",
    "EmailLog",
    "EmailPurpose",
    "EmbeddingFacet",
    "Job",
    "JobStatus",
    "Match",
    "MatchRequest",
    "MatchStatus",
    "OAuthState",
    "OtpCode",
    "ParseSource",
    "ParseStatus",
    "Profile",
    "ProfileEmbedding",
    "ProfileVisibility",
    "RateLimitCounter",
    "RequestStatus",
    "User",
    "UserSession",
    "UserStatus",
]
