"""Registry mapping an Operation to its processor callable."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.models import Operation
from app.processors import metadata, sha256, word_count

Processor = Callable[[bytes], Awaitable[object]]

_REGISTRY: dict[Operation, Processor] = {
    Operation.WORD_COUNT: word_count.process,
    Operation.SHA256: sha256.process,
    Operation.METADATA: metadata.process,
}


def get_processor(operation: Operation) -> Processor:
    return _REGISTRY[operation]
