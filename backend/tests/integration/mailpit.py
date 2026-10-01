"""Read email that the app sent to the Mailpit test SMTP server (CI service, dev stack)."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from httpx import AsyncClient

MAILPIT_API_URL = os.environ.get("MAILPIT_API_URL", "http://localhost:8025")
CODE_PATTERN = re.compile(r"\b(\d{6})\b")


async def wait_for_message(to: str, *, timeout_seconds: float = 15.0) -> dict[str, Any]:
    """Return the newest full message addressed to ``to``; fail if none arrives in time."""
    async with AsyncClient(base_url=MAILPIT_API_URL, timeout=5.0) as client:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        while loop.time() < deadline:
            found = await client.get("/api/v1/search", params={"query": f'to:"{to}"'})
            found.raise_for_status()
            messages = found.json().get("messages") or []
            if messages:
                full = await client.get(f"/api/v1/message/{messages[0]['ID']}")
                full.raise_for_status()
                message: dict[str, Any] = full.json()
                return message
            await asyncio.sleep(0.25)
    raise AssertionError(f"no email to {to} reached Mailpit within {timeout_seconds}s")


def code_from(message: dict[str, Any]) -> str:
    match = CODE_PATTERN.search(str(message.get("Text", "")))
    assert match, "no 6-digit code in the email text"
    return match.group(1)
