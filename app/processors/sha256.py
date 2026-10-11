"""Computes the SHA-256 checksum of a document."""

from __future__ import annotations

import asyncio
import hashlib


def _checksum(data: bytes) -> dict[str, str]:
    return {"sha256": hashlib.sha256(data).hexdigest()}


async def process(data: bytes) -> dict[str, str]:
    return await asyncio.to_thread(_checksum, data)
