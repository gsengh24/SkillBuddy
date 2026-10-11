"""Skill-name suggestions for the profile tag editor."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_auth
from app.schemas.errors import ErrorResponse
from app.schemas.skills import SkillSuggestion, SkillSuggestionsOut
from app.services.skills import DEFAULT_LIMIT, MAX_LIMIT, QUERY_MAX_LENGTH, suggest_skills

# Signed-in only, so the list is not an open endpoint; the caller's identity is not needed.
router = APIRouter(prefix="/skills", tags=["skills"], dependencies=[Depends(get_auth)])


@router.get(
    "/suggest",
    summary="Suggest skill names",
    responses={
        401: {"model": ErrorResponse, "description": "Not signed in."},
        422: {"model": ErrorResponse, "description": "Validation failed."},
    },
)
async def suggest(
    q: Annotated[str, Query(min_length=1, max_length=QUERY_MAX_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> SkillSuggestionsOut:
    """Names that start with, or contain a word starting with, ``q``. A convenience only:
    profiles accept any tag, so a skill missing here can still be added."""
    return SkillSuggestionsOut(items=[SkillSuggestion(name=n) for n in suggest_skills(q, limit)])
