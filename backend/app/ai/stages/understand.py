"""Stage 1, Understand: free text to structured intent (ADR 0007; ARCHITECTURE.md section 3).

``understand()`` asks the gateway (Groq, then Cloudflare) and falls back to
``understand_template()``, a rule-based reading that needs no AI, so matching still works
with the AI off, rate-limited or unreachable. The result feeds the embedding facets
(``summary``, ``offers``, ``seeks``, ``interests``) and the Explain stage.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.ai.gateway import AIGateway, AIResult, Prompt, Task
from app.ai.privacy import redact
from app.ai.prompts import load_prompt

PROMPT_ID: Final = "understand_v1"
MAX_ITEMS: Final = 8

Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class Intent(StrEnum):
    BUILD_TOGETHER = "build_together"
    SKILL_EXCHANGE = "skill_exchange"
    INTEREST_BUDDY = "interest_buddy"
    ACCOUNTABILITY = "accountability"
    MENTOR = "mentor"
    EXPLORE = "explore"


class Understanding(BaseModel):
    """What a profile or request says, in the shape the matcher uses."""

    model_config = ConfigDict(extra="ignore")

    intent: Intent | None = None
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    offers: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    seeks: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    interests: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    availability: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""

    def facets(self) -> dict[str, str | list[str]]:
        """The ``profiles.structured`` keys the embedding facets read."""
        return {
            "summary": self.summary,
            "offers": list(self.offers),
            "seeks": list(self.seeks),
            "interests": list(self.interests),
        }


# --- the template (no AI) --------------------------------------------------------------

# Checked in order; the first intent with a matching word wins.
_INTENT_WORDS: Final[tuple[tuple[Intent, tuple[str, ...]], ...]] = (
    (Intent.MENTOR, ("mentor", "mentorship", "guidance", "guide me", "advice from", "senior who")),
    (
        Intent.ACCOUNTABILITY,
        (
            "accountab",
            "keep each other",
            "keep me on track",
            "study partner",
            "study buddy",
            "gym partner",
            "workout partner",
            "check in",
            "check-in",
            "streak",
            "habit",
            "deadline",
            "motivat",
        ),
    ),
    (
        Intent.SKILL_EXCHANGE,
        (
            "exchange",
            "swap",
            "in return",
            "teach me",
            "i can teach",
            "trade skills",
            "learn from each other",
            "language partner",
            "tandem",
        ),
    ),
    (
        Intent.BUILD_TOGETHER,
        (
            "build",
            "co-founder",
            "cofounder",
            "startup",
            "hackathon",
            "side project",
            "project",
            "prototype",
            "app",
            "product",
            "research paper",
            "team up",
            "ship",
        ),
    ),
    (
        Intent.INTEREST_BUDDY,
        (
            "jam",
            "band",
            "play ",
            "chess",
            "football",
            "cricket",
            "badminton",
            "hike",
            "hiking",
            "trek",
            "book club",
            "reading",
            "games",
            "gaming",
            "music",
            "guitar",
            "photography",
            "run ",
            "running",
            "cycling",
            "dance",
            "movies",
            "anime",
            "hobby",
        ),
    ),
    (Intent.EXPLORE, ("meet people", "new people", "open to", "anyone", "explore", "network")),
)

_OFFER_CUES: Final = re.compile(
    r"\b(?:i can|i know|i'm good at|i am good at|i build|i teach|i do|i work (?:on|with)|"
    r"i've (?:built|worked)|experience (?:in|with)|skilled in|i code in|i use)\b",
    re.IGNORECASE,
)
_SEEK_CUES: Final = re.compile(
    r"\b(?:looking for|need|want|seeking|hoping to find|searching for|would like)\b",
    re.IGNORECASE,
)
_INTEREST_CUES: Final = re.compile(
    r"\b(?:i like|i love|i enjoy|i'm into|i am into|interested in|passionate about|fan of)\b",
    re.IGNORECASE,
)
_SPLIT: Final = re.compile(r",|;|\band\b|\bor\b|/", re.IGNORECASE)
_SENTENCE_END: Final = re.compile(r"(?<=[.!?])\s+")
_AVAILABILITY: Final = re.compile(
    r"\b(?:\d+\s*(?:-\s*\d+\s*)?(?:hours?|hrs?)\s*(?:a|per)\s*week|weekends?|weekdays?|"
    r"evenings?|mornings?|async)\b",
    re.IGNORECASE,
)


def _phrases_after(cue: re.Pattern[str], text: str) -> list[str]:
    found: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        match = cue.search(sentence)
        if not match:
            continue
        rest = sentence[match.end() :]
        for part in _SPLIT.split(rest):
            phrase = re.sub(r"^\W+|\W+$", "", part).strip()
            phrase = re.sub(r"^(?:a|an|the|someone (?:who|to)|to|some)\s+", "", phrase, flags=re.I)
            if 2 <= len(phrase) <= 60 and phrase.lower() not in {p.lower() for p in found}:
                found.append(phrase)
            if len(found) >= MAX_ITEMS:
                return found
    return found


def detect_intent(text: str) -> Intent | None:
    lowered = f" {text.lower()} "
    for intent, words in _INTENT_WORDS:
        if any(word in lowered for word in words):
            return intent
    return None


def understand_template(text: str) -> Understanding:
    """A rule-based reading of the text, for when no AI is available."""
    clean = " ".join(text.split())
    first = _SENTENCE_END.split(clean)[0] if clean else ""
    availability = _AVAILABILITY.search(clean)
    return Understanding(
        intent=detect_intent(clean),
        summary=first[:200],
        offers=_phrases_after(_OFFER_CUES, clean),
        seeks=_phrases_after(_SEEK_CUES, clean),
        interests=_phrases_after(_INTEREST_CUES, clean),
        availability=availability.group(0) if availability else "",
    )


# --- the stage -------------------------------------------------------------------------


async def understand(
    gateway: AIGateway,
    text: str,
    *,
    user_id: str,
    name_hints: Sequence[str] = (),
) -> AIResult[Understanding]:
    """Structured intent for ``text`` from the AI, or from the template when it is off."""
    prompt = Prompt(
        version=PROMPT_ID,
        system=load_prompt(PROMPT_ID),
        data={"text": text},
        name_hints=name_hints,
        max_tokens=600,
    )
    return await gateway.complete(
        Task.UNDERSTAND,
        prompt,
        Understanding,
        user_id=user_id,
        # The template sees the redacted text too, so its phrases carry no contact details.
        fallback=lambda: understand_template(redact(text, names=name_hints)),
    )
