from __future__ import annotations

from src.cache.review_cache import get_cache
from src.graph.state import ReviewState
from src.schema.types import ReviewResult


async def cache_check_node(state: ReviewState) -> dict:
    """Check if review results are cached for current segment."""
    idx = state["current_segment_index"]
    if idx >= len(state["segments"]):
        return {"phase": "aggregate"}

    segment = state["segments"][idx]
    cache = get_cache()
    cached = cache.get(segment)

    if cached is not None:
        new_metadata = state["metadata"].model_copy(update={
            "cache_hits": state["metadata"].cache_hits + 1,
        })
        return {
            "current_segment_index": idx + 1,
            "segment_reviews": [cached],
            "metadata": new_metadata,
            "phase": "review",
        }

    new_metadata = state["metadata"].model_copy(update={
        "cache_misses": state["metadata"].cache_misses + 1,
    })
    return {"metadata": new_metadata, "phase": "review"}
