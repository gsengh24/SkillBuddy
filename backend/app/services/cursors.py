"""Opaque cursors for newest-first lists: ``created_at`` plus ``id``, base64-encoded."""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from http import HTTPStatus

from app.core.errors import AppError


class InvalidCursorError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "invalid_cursor"
    default_message = "The cursor is not valid."


def encode(created_at: datetime, identifier: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{identifier}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        stamp, _, identifier = base64.urlsafe_b64decode(padded).decode().partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(identifier)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursorError from None
