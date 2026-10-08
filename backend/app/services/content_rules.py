"""Automatic content rules (A7): fast checks run when a request, bio or intro note is saved.

Rules only FLAG: they never block, change or hide what a user wrote or sees. A flag goes to
the admin Content moderation queue, where a moderator keeps or removes the text. No AI call
and no network: regular expressions, plus one indexed query for repeated intros. Each rule
is a switch stored in ``app_settings`` (``modrule:<rule>``), read through its 60-second cache.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentFlag, ContentRule, FlaggedItem, Intro
from app.services import app_settings

logger = logging.getLogger(__name__)

# The reference's starting state: every rule on but prompt injection.
DEFAULTS: Final[dict[ContentRule, bool]] = {
    ContentRule.PROFANITY: True,
    ContentRule.LINKS_IN_BIOS: True,
    ContentRule.CONTACT_DETAILS: True,
    ContentRule.REPEATED_INTROS: True,
    ContentRule.PROMPT_INJECTION: False,
}

# Which kinds of text each rule looks at.
APPLIES_TO: Final[dict[ContentRule, frozenset[FlaggedItem]]] = {
    ContentRule.PROFANITY: frozenset(FlaggedItem),
    ContentRule.LINKS_IN_BIOS: frozenset({FlaggedItem.PROFILE}),
    ContentRule.CONTACT_DETAILS: frozenset(FlaggedItem),
    ContentRule.REPEATED_INTROS: frozenset({FlaggedItem.INTRO}),
    ContentRule.PROMPT_INJECTION: frozenset(FlaggedItem),
}

_PROFANITY = re.compile(
    r"\b(?:fuck\w*|motherfuck\w*|shit\w*|bullshit|bitch\w*|bastard\w*|asshole\w*|cunt\w*|"
    r"dickhead\w*|slut\w*|whore\w*|wanker\w*|retard\w*)\b",
    re.IGNORECASE,
)
_LINK = re.compile(
    r"(?:\bhttps?://|\bwww\.)\S+"
    r"|\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|is\.gd|cutt\.ly|rb\.gy|tiny\.cc|"
    r"shorturl\.at|t\.me|wa\.me)/\S*",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# Eight or more digits, allowing spaces, dots, dashes and brackets between them.
_PHONE = re.compile(r"(?<!\w)\+?\(?\d(?:[\s().-]*\d){7,}(?!\w)")
_INJECTION = re.compile(
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)*"
    r"(?:previous|prior|above|earlier|system)\s+(?:instructions?|prompts?|rules?)\b"
    r"|\bsystem\s+prompt\b|\byou\s+are\s+now\s+(?:a|an|in)\b|\bdeveloper\s+mode\b|\bjailbreak\b"
    r"|<\s*/?\s*system\s*>|\[\s*system\s*\]",
    re.IGNORECASE,
)
# The same note sent to this many people within a day is flagged.
REPEATED_INTRO_COUNT: Final = 3
REPEATED_INTRO_MIN_LENGTH: Final = 20


def text_rules(text: str, item: FlaggedItem) -> set[ContentRule]:
    """The text-only rules ``text`` matches (whether or not they're switched on)."""
    found: set[ContentRule] = set()
    if _PROFANITY.search(text):
        found.add(ContentRule.PROFANITY)
    if item is FlaggedItem.PROFILE and _LINK.search(text):
        found.add(ContentRule.LINKS_IN_BIOS)
    if _EMAIL.search(text) or _PHONE.search(text):
        found.add(ContentRule.CONTACT_DETAILS)
    if _INJECTION.search(text):
        found.add(ContentRule.PROMPT_INJECTION)
    return found


async def rule_on(db: AsyncSession, rule: ContentRule) -> bool:
    return await app_settings.switch(db, f"{app_settings.RULE_PREFIX}{rule.value}", DEFAULTS[rule])


async def _repeated_intro(db: AsyncSession, sender_id: uuid.UUID, note: str) -> bool:
    normalised = " ".join(note.split()).lower()
    if len(normalised) < REPEATED_INTRO_MIN_LENGTH:
        return False
    since = datetime.now(UTC) - timedelta(days=1)
    same = await db.scalar(
        select(func.count())
        .select_from(Intro)
        .where(
            Intro.sender_id == sender_id,
            Intro.created_at >= since,
            func.lower(func.regexp_replace(func.btrim(Intro.note), r"\s+", " ", "g")) == normalised,
        )
    )
    return int(same or 0) >= REPEATED_INTRO_COUNT


async def flag(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    item: FlaggedItem,
    item_id: uuid.UUID,
    text: str,
) -> list[ContentRule]:
    """Run the switched-on rules on a just-saved text; store a flag per match in the
    caller's transaction (it commits with the save). Returns the rules that matched."""
    if not text.strip():
        return []
    matched = text_rules(text, item)
    if item is FlaggedItem.INTRO and await _repeated_intro(db, user_id, text):
        matched.add(ContentRule.REPEATED_INTROS)
    flagged = [rule for rule in sorted(matched) if await rule_on(db, rule)]
    for rule in flagged:
        await db.execute(
            insert(ContentFlag)
            .values(user_id=user_id, item_type=item.value, item_id=item_id, rule=rule.value)
            .on_conflict_do_nothing(
                index_elements=[ContentFlag.item_type, ContentFlag.item_id, ContentFlag.rule],
                index_where=ContentFlag.status == "open",
            )
        )
    if flagged:
        logger.info(
            "content_flagged",
            extra={"item_type": item.value, "rules": [rule.value for rule in flagged]},
        )
    return flagged


DECIDED_RETENTION_DAYS: Final = 90
OPEN_RETENTION_DAYS: Final = 180


async def purge_flags(db: AsyncSession, now: datetime) -> int:
    """Daily: decided flags 90 days after the decision, open ones 180 days after flagging."""
    result = await db.execute(
        delete(ContentFlag).where(
            (
                (ContentFlag.status != "open")
                & (ContentFlag.decided_at < now - timedelta(days=DECIDED_RETENTION_DAYS))
            )
            | (
                (ContentFlag.status == "open")
                & (ContentFlag.created_at < now - timedelta(days=OPEN_RETENTION_DAYS))
            )
        )
    )
    await db.commit()
    deleted = int(getattr(result, "rowcount", 0) or 0)
    logger.info("content_flags_purged", extra={"deleted": deleted})
    return deleted
