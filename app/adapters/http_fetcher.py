"""httpx-based implementation of the DocumentFetcher port.

Streams the response with a max body size; no SSRF guard against
private/loopback addresses (documented as a known gap in the README).
"""

from __future__ import annotations

import httpx

from app.domain.errors import PermanentProcessingError, TransientProcessingError

_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class HttpDocumentFetcher:
    def __init__(self, timeout_seconds: float = 10.0, max_bytes: int = 10 * 1024 * 1024) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(self, url: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                async with client.stream("GET", url) as response:
                    self._raise_for_status(url, response)
                    return await self._read_body(url, response)
        except (TransientProcessingError, PermanentProcessingError):
            raise
        except httpx.TimeoutException as exc:
            raise TransientProcessingError(f"timeout fetching {url}") from exc
        except httpx.ConnectError as exc:
            raise TransientProcessingError(f"connection error fetching {url}") from exc
        except httpx.HTTPError as exc:
            raise TransientProcessingError(f"HTTP error fetching {url}: {exc}") from exc

    def _raise_for_status(self, url: str, response: httpx.Response) -> None:
        if response.status_code in _TRANSIENT_STATUS_CODES:
            raise TransientProcessingError(f"transient HTTP {response.status_code} fetching {url}")
        if response.is_error:
            raise PermanentProcessingError(f"permanent HTTP {response.status_code} fetching {url}")

    async def _read_body(self, url: str, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > self._max_bytes:
                raise PermanentProcessingError(
                    f"document at {url} exceeds max size of {self._max_bytes} bytes"
                )
            chunks.append(chunk)
        return b"".join(chunks)
