import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.cache import TTLCache  # noqa: E402


def test_cache_set_and_get():
    cache = TTLCache(max_entries=10, ttl_seconds=60)
    cache.set("Some Query", [1, 2, 3])
    assert cache.get("some query") == [1, 2, 3]  # normalization is case/whitespace-insensitive


def test_cache_expires_after_ttl():
    cache = TTLCache(max_entries=10, ttl_seconds=0.05)
    cache.set("query", "value")
    time.sleep(0.1)
    assert cache.get("query") is None


def test_cache_evicts_oldest_when_full():
    cache = TTLCache(max_entries=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_cache_miss_returns_none():
    cache = TTLCache(max_entries=10, ttl_seconds=60)
    assert cache.get("nonexistent") is None
