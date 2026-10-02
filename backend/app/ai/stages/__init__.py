"""The matcher's AI stages on top of the gateway (ADR 0007): Understand and Explain.

Both work with the AI off: each has a template fallback that needs no model.
"""

from app.ai.stages.explain import (
    Candidate,
    Explained,
    Explanation,
    Selection,
    explain,
    explain_template,
)
from app.ai.stages.understand import Intent, Understanding, understand, understand_template

__all__ = [
    "Candidate",
    "Explained",
    "Explanation",
    "Intent",
    "Selection",
    "Understanding",
    "explain",
    "explain_template",
    "understand",
    "understand_template",
]
