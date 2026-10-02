"""Privacy stripping before any text leaves the server (ADR 0007, section 5).

Only redacted free text and anonymous candidate summaries (C1 to C15) are sent to an AI
provider. Emails, phone numbers, links, social handles and the person's own name are
replaced with placeholders. ``find_leaks`` is a last check on the exact bytes about to be
sent; the gateway refuses to send anything it flags.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Final

EMAIL_PLACEHOLDER: Final = "[email]"
PHONE_PLACEHOLDER: Final = "[phone]"
LINK_PLACEHOLDER: Final = "[link]"
HANDLE_PLACEHOLDER: Final = "[handle]"
NAME_PLACEHOLDER: Final = "[name]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_URL = re.compile(r"(?:\bhttps?://|\bwww\.)[^\s<>\"')\]]+", re.IGNORECASE)
# Bare domains with a common top-level domain, optionally with a path: "github.com/aarav",
# "linktr.ee/x", "mysite.dev". "Node.js" and "e.g." are not domains here.
_BARE_DOMAIN = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:com|in|org|net|io|dev|me|co|ai|app|edu|ly|gg|ee|xyz|tech|site|page)"
    r"\b(?:/[^\s<>\"')\]]*)?",
    re.IGNORECASE,
)
# Runs of digits with common separators; only replaced if they hold enough digits to be
# a phone number (so "2019-2023" or "3rd year" are kept).
_DIGIT_RUN = re.compile(r"(?<![\w])\+?\(?\d[\d\s().-]{6,}\d(?![\w])")
_MIN_PHONE_DIGITS: Final = 10
_MIN_INTL_PHONE_DIGITS: Final = 8
_HANDLE = re.compile(r"(?<![\w@./])@[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?")
_MIN_NAME_LENGTH: Final = 3


def _phone(match: re.Match[str]) -> str:
    text = match.group(0)
    digits = sum(ch.isdigit() for ch in text)
    needed = _MIN_INTL_PHONE_DIGITS if text.startswith("+") else _MIN_PHONE_DIGITS
    return PHONE_PLACEHOLDER if digits >= needed else text


def name_hints_from_email(email: str) -> list[str]:
    """Likely name parts from an address: "ananya.sharma91@x.in" gives ananya, sharma."""
    local = email.split("@", 1)[0]
    return [part for part in re.split(r"[^A-Za-z]+", local) if len(part) >= _MIN_NAME_LENGTH]


def _name_pattern(names: Iterable[str]) -> re.Pattern[str] | None:
    words = sorted(
        {word for name in names for word in name.split() if len(word) >= _MIN_NAME_LENGTH},
        key=len,
        reverse=True,
    )
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


def redact(text: str, *, names: Sequence[str] = ()) -> str:
    """Replace contact details and the given names with placeholders."""
    text = _EMAIL.sub(EMAIL_PLACEHOLDER, text)
    text = _URL.sub(LINK_PLACEHOLDER, text)
    text = _BARE_DOMAIN.sub(LINK_PLACEHOLDER, text)
    text = _DIGIT_RUN.sub(_phone, text)
    text = _HANDLE.sub(HANDLE_PLACEHOLDER, text)
    pattern = _name_pattern(names)
    if pattern is not None:
        text = pattern.sub(NAME_PLACEHOLDER, text)
    return text


def find_leaks(text: str, *, names: Sequence[str] = ()) -> list[str]:
    """What still looks like personal contact data (or a given name) in ``text``."""
    leaks = [kind for kind, rx in (("email", _EMAIL), ("link", _URL)) if rx.search(text)]
    if _BARE_DOMAIN.search(text):
        leaks.append("link")
    if any(_phone(match) == PHONE_PLACEHOLDER for match in _DIGIT_RUN.finditer(text)):
        leaks.append("phone")
    if _HANDLE.search(text):
        leaks.append("handle")
    pattern = _name_pattern(names)
    if pattern is not None and pattern.search(text):
        leaks.append("name")
    return leaks
