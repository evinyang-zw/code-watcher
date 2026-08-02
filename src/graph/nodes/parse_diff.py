from __future__ import annotations

from src.github.diff_parser import parse_unified_diff
from src.graph.state import ReviewState


async def parse_diff_node(state: ReviewState) -> dict:
    """Parse raw unified diff into per-file structures."""
    files = parse_unified_diff(state["raw_diff"])
    return {"files": files, "phase": "segment"}
