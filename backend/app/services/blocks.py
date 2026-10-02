"""Blocks between people: the hook other modules ask before letting two people interact.

Blocking itself (a table, endpoints, the hard filter in retrieval) arrives with roadmap
item 7 (ARCHITECTURE.md §8). Until then nobody is blocked. Chat already asks here before
every send, read, history page and poll, so when item 7 fills this in, a block stops
sending and reading in both directions without touching chat.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def blocked_with(db: AsyncSession, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
    """Everyone ``user_id`` has blocked or been blocked by (a block works both ways)."""
    del db, user_id  # Item 7: look the pair up in the blocks table.
    return frozenset()
