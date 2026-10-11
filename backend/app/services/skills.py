"""Skill-name suggestions for the profile tag editor (ADR 0020).

A small, bundled list (O*NET technology names plus a hand-written list of general skills and
interests) searched in memory. No database, no network, no AI call: it is safe to call on
every keystroke. Suggestions are only a convenience; people can still type any tag.
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
