"""Picked tags (skills, interests) as requests carry them (ADR 0020, ADR 0022)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from app.models import MAX_PICKED_TAGS, TAG_MAX_LENGTH


def unique_tags(values: list[str]) -> list[str]:
    """Drops repeats, ignoring case, keeping the first spelling of each."""
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            kept.append(value)
    return kept


Tag = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TAG_MAX_LENGTH)
]
Tags = Annotated[list[Tag], Field(max_length=MAX_PICKED_TAGS), AfterValidator(unique_tags)]
