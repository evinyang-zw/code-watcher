from __future__ import annotations

from src.cache.review_cache import ReviewCache
from src.schema.types import CodeSegment, ReviewResult


def _make_segment(file_path: str = "test.py", content: str = "print('hello')") -> CodeSegment:
    return CodeSegment(
        file_path=file_path,
        hunk_start=1,
        hunk_end=2,
        old_content="",
        new_content=content,
        language="python",
        segment_index=0,
    )


def _make_result(segment: CodeSegment) -> ReviewResult:
    return ReviewResult(segment=segment, findings=[])


def test_cache_miss():
    cache = ReviewCache()
    seg = _make_segment()
    assert not cache.has(seg)
    assert cache.get(seg) is None


def test_cache_hit():
    cache = ReviewCache()
    seg = _make_segment()
    result = _make_result(seg)
    cache.put(seg, result)
    assert cache.has(seg)
    assert cache.get(seg) == result


def test_cache_same_content_different_path():
    cache = ReviewCache()
    seg1 = _make_segment("a.py", "print('hello')")
    seg2 = _make_segment("b.py", "print('hello')")
    result1 = _make_result(seg1)
    cache.put(seg1, result1)
    # Same content but different path = different hash
    assert cache.has(seg1)
    assert not cache.has(seg2)


def test_cache_lru_eviction():
    cache = ReviewCache(max_size=2)
    seg1 = _make_segment("a.py")
    seg2 = _make_segment("b.py")
    seg3 = _make_segment("c.py")

    cache.put(seg1, _make_result(seg1))
    cache.put(seg2, _make_result(seg2))
    assert cache.size == 2

    # Adding third should evict oldest (seg1)
    cache.put(seg3, _make_result(seg3))
    assert cache.size == 2
    assert not cache.has(seg1)
    assert cache.has(seg2)
    assert cache.has(seg3)


def test_cache_lru_access_order():
    cache = ReviewCache(max_size=2)
    seg1 = _make_segment("a.py")
    seg2 = _make_segment("b.py")
    seg3 = _make_segment("c.py")

    cache.put(seg1, _make_result(seg1))
    cache.put(seg2, _make_result(seg2))

    # Access seg1 to make it recently used
    cache.get(seg1)

    # Adding seg3 should evict seg2 (least recently used)
    cache.put(seg3, _make_result(seg3))
    assert cache.has(seg1)
    assert not cache.has(seg2)
    assert cache.has(seg3)


def test_cache_clear():
    cache = ReviewCache()
    seg = _make_segment()
    cache.put(seg, _make_result(seg))
    assert cache.size == 1
    cache.clear()
    assert cache.size == 0
