"""Skill suggestion responses."""

from __future__ import annotations

from pydantic import BaseModel


class SkillSuggestion(BaseModel):
    name: str


class SkillSuggestionsOut(BaseModel):
    items: list[SkillSuggestion]
