"""The matcher's AI stages on top of the gateway (ADR 0007): Understand and Explain.

Both work with the AI off: each has a template fallback that needs no model.
"""

from app.ai.stages.compose import Chips, Composed, compose, compose_template
from app.ai.stages.explain import (
    Candidate,
    Explained,
    Explanation,
    Judgement,
    explain,
    explain_template,
)
from app.ai.stages.understand import Intent, Understanding, understand, understand_template

__all__ = [
    "Candidate",
    "Chips",
    "Composed",
    "Explained",
    "Explanation",
    "Intent",
    "Judgement",
    "Understanding",
    "compose",
    "compose_template",
    "explain",
    "explain_template",
    "understand",
    "understand_template",
]
