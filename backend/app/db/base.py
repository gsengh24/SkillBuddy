"""Declarative base and shared column mixins for all ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names, so Alembic migrations are stable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012  # SQLAlchemy reads this as a class attribute
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


# Expression indexes that exist only in migrations (trigram search, migration 0019): a
# model can't express them in a form Alembic compares reliably, so the drift checks skip
# exactly these names. tests/integration/test_migrations.py checks that they exist.
MIGRATION_ONLY_INDEXES = frozenset({"ix_users_email_trgm", "ix_profiles_display_name_trgm"})


def include_in_drift_check(
    _object: object, name: str | None, type_: str, _reflected: bool, _compare_to: object
) -> bool:
    """Alembic's ``include_object`` hook for ``alembic check`` and autogenerate."""
    return not (type_ == "index" and name in MIGRATION_ONLY_INDEXES)
