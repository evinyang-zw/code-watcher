from __future__ import annotations

import hashlib
from collections import OrderedDict

from src.schema.types import CodeSegment, ReviewResult


class ReviewCache:
    """LRU cache for review results, indexed by code content hash.

    Uses OrderedDict for O(1) get/put/evict operations.
    """

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, ReviewResult] = OrderedDict()
        self._max_size = max_size

    def _content_hash(self, segment: CodeSegment) -> str:
        content = f"{segment.file_path}:{segment.new_content}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def has(self, segment: CodeSegment) -> bool:
        return self._content_hash(segment) in self._cache

    def get(self, segment: CodeSegment) -> ReviewResult | None:
        key = self._content_hash(segment)
        if key in self._cache:
            # Move to end (most recently used) — O(1)
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, segment: CodeSegment, result: ReviewResult):
        key = self._content_hash(segment)
        if key in self._cache:
            # Update existing entry — O(1)
            self._cache.move_to_end(key)
            self._cache[key] = result
        else:
            # New entry — evict LRU if at capacity — O(1)
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = result

    @property
    def size(self) -> int:
        return len(self._cache)

    def clear(self):
        self._cache.clear()


# Global cache instance
_global_cache = ReviewCache()


def get_cache() -> ReviewCache:
    return _global_cache
