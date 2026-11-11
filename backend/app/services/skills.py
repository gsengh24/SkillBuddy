"""Skill-name suggestions for the profile tag editor (ADR 0020).

A small, bundled list (O*NET technology names plus a hand-written list of general skills and
interests) searched in memory. No database, no network, no AI call: it is safe to call on
every keystroke. Suggestions are only a convenience; people can still type any tag.

The same list also vets the skill tags of a profile read without AI (``known_skills_in``),
so the rule-based reading shows only real skill names, never stray words from a sentence.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# Curated names come first, so they outrank O*NET names that match equally well.
DATA_FILES = ("skills_curated.txt", "skills_onet.txt")
QUERY_MAX_LENGTH = 60
DEFAULT_LIMIT = 8
MAX_LIMIT = 20
# One letter or two matches almost everything as a substring; only prefixes count then.
SUBSTRING_MIN_LENGTH = 3

_WORD = re.compile(r"[a-z0-9+#.]+")
# Tokens for spotting names inside free text: a dot counts only inside a word ("Node.js").
_TEXT_TOKEN = re.compile(r"[A-Za-z0-9+#]+(?:\.[A-Za-z0-9+#]+)*")
# Single-word names that are also everyday words or letters. They count only when written
# exactly as named ("I code in Go", not "a go-to person" or "zoom ahead").
AMBIGUOUS_NAMES = frozenset(
    {"ada", "awk", "c", "chef", "eko", "go", "hms", "j", "puppet", "r", "slack", "swift", "zoom"}
)
# Longest name, in tokens, worth looking for.
_MAX_NAME_TOKENS = 6


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


@lru_cache(maxsize=1)
def load_skills() -> tuple[str, ...]:
    """Every name once (first spelling wins), in ranking order."""
    seen: set[str] = set()
    names: list[str] = []
    for filename in DATA_FILES:
        for line in (DATA_DIR / filename).read_text(encoding="utf-8").splitlines():
            name = " ".join(line.split())
            if not name or name.startswith("#") or _key(name) in seen:
                continue
            seen.add(_key(name))
            names.append(name)
    return tuple(names)


@lru_cache(maxsize=1)
def curated_skills() -> tuple[str, ...]:
    """The hand-written list only (no O*NET names): short and common enough to spot in text."""
    lines = (DATA_DIR / DATA_FILES[0]).read_text(encoding="utf-8").splitlines()
    names = (" ".join(line.split()) for line in lines)
    return tuple(name for name in names if name and not name.startswith("#"))


def suggest_skills(query: str, limit: int = DEFAULT_LIMIT) -> list[str]:
    """Names matching ``query``: whole-name prefix first, then a word prefix, then (for three
    or more characters) any substring. Within a tier, list order decides."""
    needle = _key(query)[:QUERY_MAX_LENGTH]
    if not needle:
        return []
    limit = max(1, min(limit, MAX_LIMIT))
    prefix: list[str] = []
    word: list[str] = []
    inside: list[str] = []
    for name in load_skills():
        haystack = name.casefold()
        if haystack.startswith(needle):
            prefix.append(name)
        elif any(token.startswith(needle) for token in _WORD.findall(haystack)):
            word.append(name)
        elif len(needle) >= SUBSTRING_MIN_LENGTH and needle in haystack:
            inside.append(name)
        if len(prefix) >= limit:
            break
    return (prefix + word + inside)[:limit]


@lru_cache(maxsize=1)
def _names_by_tokens() -> dict[tuple[str, ...], str]:
    """Each name's lower-case tokens mapped to its usual spelling."""
    index: dict[tuple[str, ...], str] = {}
    for name in load_skills():
        tokens = tuple(t.casefold() for t in _TEXT_TOKEN.findall(name))
        if tokens and len(tokens) <= _MAX_NAME_TOKENS:
            index.setdefault(tokens, name)
    return index


def known_skills_in(phrases: list[str], limit: int) -> list[str]:
    """The known skill names mentioned in ``phrases``, in order, each once, in the list's
    spelling: "lot of reading in my free time" gives "Reading", "a cook" gives nothing.
    The longest name wins where names overlap ("Machine learning", not "Learning")."""
    index = _names_by_tokens()
    found: list[str] = []
    for phrase in phrases:
        tokens = _TEXT_TOKEN.findall(phrase)
        lowered = [t.casefold() for t in tokens]
        i = 0
        while i < len(tokens) and len(found) < limit:
            for size in range(min(_MAX_NAME_TOKENS, len(tokens) - i), 0, -1):
                name = index.get(tuple(lowered[i : i + size]))
                if name is None:
                    continue
                if size == 1 and name.casefold() in AMBIGUOUS_NAMES and tokens[i] != name:
                    continue
                if name not in found:
                    found.append(name)
                i += size
                break
            else:
                i += 1
    return found
