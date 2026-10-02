"""Versioned prompt files (ADR 0007: prompts live in files with ids, not inline strings).

A prompt id is ``<name>_v<N>``; the file is ``<name>_v<N>.md`` in this folder. A change to
a prompt's meaning is a new version, so stored results can be traced to the prompt that
made them.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


@cache
def load_prompt(prompt_id: str) -> str:
    path = PROMPTS_DIR / f"{prompt_id}.md"
    if not path.is_file() or path.parent != PROMPTS_DIR:
        raise FileNotFoundError(f"no prompt {prompt_id!r}")
    return path.read_text(encoding="utf-8").strip()
