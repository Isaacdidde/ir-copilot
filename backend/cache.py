"""In-memory TTL cache for retrieval results, keyed by normalized query text."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Optional

from backend.config import settings
from backend.logger import get_logger

logger = get_logger(__name__)


class TTLCache:
    def __init__(self, max_entries: int, ttl_seconds: int) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()

    @staticmethod
    def _normalize(key: str) -> str:
        return " ".join(key.strip().lower().split())

    def get(self, key: str) -> Optional[Any]:
        norm = self._normalize(key)
        entry = self._store.get(norm)
        if entry is None:
            return None
        timestamp, value = entry
        if time.time() - timestamp > self.ttl_seconds:
            del self._store[norm]
            return None
        self._store.move_to_end(norm)
        return value

    def set(self, key: str, value: Any) -> None:
        norm = self._normalize(key)
        self._store[norm] = (time.time(), value)
        self._store.move_to_end(norm)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


retrieval_cache = TTLCache(
    max_entries=settings.retrieval_cache_max_entries,
    ttl_seconds=settings.retrieval_cache_ttl_seconds,
)
