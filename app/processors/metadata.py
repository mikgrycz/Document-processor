"""Extracts basic metadata about a document."""

from __future__ import annotations


async def process(data: bytes) -> dict[str, int]:
    return {"size_bytes": len(data)}
