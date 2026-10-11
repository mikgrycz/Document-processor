"""Counts whitespace-separated words in a document."""

from __future__ import annotations

import asyncio


def _count(data: bytes) -> dict[str, int]:
    text = data.decode("utf-8", errors="replace")
    return {"word_count": len(text.split())}


async def process(data: bytes) -> dict[str, int]:
    return await asyncio.to_thread(_count, data)
