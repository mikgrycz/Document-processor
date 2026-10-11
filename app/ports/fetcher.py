"""Interface for retrieving document bytes from a URL."""

from __future__ import annotations

from typing import Protocol


class DocumentFetcher(Protocol):
    async def fetch(self, url: str) -> bytes:
        """Download the document at `url` and return its raw bytes."""
        ...
