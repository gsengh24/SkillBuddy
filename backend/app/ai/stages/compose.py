"""Step 5 of onboarding (ADR 0022): the about text, card heading and summary from the chips.

``compose()`` asks the gateway and falls back to ``compose_template()``, which needs no AI:
"Offers: React, Figma. Wants: Node.js. Into: chess, hackathons." Only the chips, the
optional note and the availability band are sent, never a name (ADR 0007, section 5). The
gateway redacts the note like any other user-written text.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.ai.gateway import AIGateway, AIResult, Prompt, Task
from app.ai.privacy import redact
from app.ai.prompts import load_prompt

PROMPT_ID: Final = "compose_v1"
ABOUT_MAX: Final = 500

_INTENT_WORDS: Final = {
    "build_together": "build something together",
    "skill_exchange": "swap skills",
    "interest_buddy": "find an interest buddy",
    "accountability": "find an accountability partner",
    "mentor": "find or be a mentor",
    "explore": "see who's out there",
}


class Composed(BaseModel):
    """What step 5 shows: a card heading, a one-line summary and an editable about text."""

    model_config = ConfigDict(extra="ignore")

    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    about: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ABOUT_MAX)
    ]


@dataclass(frozen=True)
class Chips:
    """The onboarding picks the about text is made from."""

    intents: Sequence[str]
    offers: Sequence[str]
    wants: Sequence[str]
    interests: Sequence[str]
    note: str
    availability: str


def _list(items: Sequence[str]) -> str:
    return ", ".join(items)


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text[0].upper() + text[1:] + ("" if text[-1] in ".!?" else ".")


def compose_template(chips: Chips, *, names: Sequence[str] = ()) -> Composed:
    """The about text from the chips alone, for when no AI is available. Always non-empty."""
    parts: list[str] = []
    if chips.offers:
        parts.append(f"Offers: {_list(chips.offers)}.")
    if chips.wants:
        parts.append(f"Wants: {_list(chips.wants)}.")
    if chips.interests:
        parts.append(f"Into: {_list(chips.interests).lower()}.")
    note = redact(chips.note, names=names).strip()
    if note:
        parts.append(f"Looking for: {note.rstrip('.')}.")
    if chips.availability:
        parts.append(f"Free: {chips.availability}.")
    if not parts:
        goals = [_INTENT_WORDS[i] for i in chips.intents if i in _INTENT_WORDS]
        parts.append(_sentence(f"Here to {' and '.join(goals[:2])}") if goals else "New here.")
    about = " ".join(parts)
    if len(about) > ABOUT_MAX:
        about = about[: ABOUT_MAX - 1].rstrip() + "…"
    return Composed(title=_template_title(chips), summary=_clip(about, 200), about=about)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _template_title(chips: Chips) -> str:
    """ "Offers React, wants Node.js": a plain heading from the first chips."""
    offer = chips.offers[0] if chips.offers else ""
    want = chips.wants[0] if chips.wants else ""
    if offer and want:
        title = f"Offers {offer}, wants {want}"
    elif offer:
        title = f"Offers {offer}"
    elif want:
        title = f"Looking for {want}"
    elif chips.interests:
        title = f"Into {chips.interests[0].lower()}"
    else:
        title = ""
    return _clip(title, 60)


async def compose(
    gateway: AIGateway,
    chips: Chips,
    *,
    user_id: str,
    name_hints: Sequence[str] = (),
) -> AIResult[Composed]:
    """The about text from the AI, or from the template when it is off or failing."""
    prompt = Prompt(
        version=PROMPT_ID,
        system=load_prompt(PROMPT_ID),
        data={
            "intents": list(chips.intents),
            "offers": list(chips.offers),
            "wants": list(chips.wants),
            "interests": list(chips.interests),
            "note": chips.note,
            "availability": chips.availability,
        },
        name_hints=name_hints,
        max_tokens=500,
    )
    return await gateway.complete(
        Task.UNDERSTAND,
        prompt,
        Composed,
        user_id=user_id,
        fallback=lambda: compose_template(chips, names=name_hints),
    )
