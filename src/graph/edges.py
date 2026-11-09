from __future__ import annotations

from src.graph.state import ReviewState

# One auto-fix attempt per run is enough: a second pass would re-review the
# same segments and re-generate the same patches, which is how the graph used
# to loop forever (GraphRecursionError).
MAX_FIX_ATTEMPTS = 1


def should_continue_to_segment(state: ReviewState) -> str:
    """After reviewing one segment, check if more remain.

    ``current_segment_index`` is already advanced past the reviewed segment, so
    the next segment exists when ``index < len(segments)``. The previous
    ``len - 1`` comparison silently skipped the last segment.
    """
    if state["current_segment_index"] < len(state["segments"]):
        return "continue"
    return "aggregate"


def route_after_cache(state: ReviewState) -> str:
    """Decide whether to skip (cache hit), review, or finish."""
    idx = state["current_segment_index"]
    segments = state["segments"]
    if idx >= len(segments):
        return "aggregate"
    from src.cache.review_cache import get_cache

    if get_cache().get(segments[idx]) is not None:
        return "cache_hit"
    return "review_segment"


def should_auto_fix(state: ReviewState) -> str:
    """After suggesting fixes, decide the next step."""
    suggestions = state.get("suggestions") or []
    attempts = int(state.get("fix_attempts") or 0)

    # Critical findings always go to a human before any code is modified.
    if any(s.severity == "critical" for s in suggestions):
        return "human_review"

    if state.get("auto_fix_enabled") and suggestions and attempts < MAX_FIX_ATTEMPTS:
        fixable = [
            s
            for s in suggestions
            if s.severity in ("warning", "suggestion", "nit") and s.suggested_fix is not None
        ]
        if fixable:
            return "auto_fix"
    return "post"


def should_re_review(state: ReviewState) -> str:
    """After self-evaluation, decide whether to apply fixes."""
    approved = [e for e in (state.get("evaluation_results") or []) if e.confidence_score >= 0.7]
    if approved:
        return "apply_and_review"
    if state.get("suggestions"):
        return "human_review"
    return "post"


def needs_human_review(state: ReviewState) -> str:
    """After auto-fix, decide if human review is needed."""
    # Re-reviewing patched code is not implemented yet (segments describe the
    # original diff), so a passing self-evaluation goes straight to posting.
    evaluation_results = state.get("evaluation_results") or []
    if evaluation_results:
        low_confidence = [e for e in evaluation_results if e.confidence_score < 0.7]
        if low_confidence:
            return "human_review"
    return "post"


def should_route_on_error(state: ReviewState) -> str:
    """Check if any error occurred and route accordingly."""
    if state.get("error"):
        return "human_review"
    return "ok"
