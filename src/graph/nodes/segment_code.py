from __future__ import annotations

from src.github.diff_parser import extract_segments
from src.graph.state import ReviewState


async def segment_code_node(state: ReviewState) -> dict:
    """Split parsed files into reviewable CodeSegments."""
    segments = extract_segments(state["raw_diff"])
    return {"segments": segments, "current_segment_index": 0, "phase": "cache_check"}
