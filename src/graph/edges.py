from __future__ import annotations

from src.graph.state import ReviewState


def should_continue_to_segment(state: ReviewState) -> str:
    """After reviewing one segment, check if more remain."""
    if state["current_segment_index"] < len(state["segments"]) - 1:
        return "continue"
    return "aggregate"


def should_auto_fix(state: ReviewState) -> str:
    """After suggesting fixes, decide the next step."""
    if state["auto_fix_enabled"] and state["suggestions"]:
        fixable = [
            s
            for s in state["suggestions"]
            if s.severity in ("warning", "suggestion", "nit") and s.suggested_fix is not None
        ]
        if fixable:
            return "auto_fix"
    has_critical = any(s.severity == "critical" for s in state["suggestions"])
    if has_critical:
        return "human_review"
    return "post"


def should_re_review(state: ReviewState) -> str:
    """After self-evaluation, decide whether to apply fixes."""
    approved = [e for e in state["evaluation_results"] if e.confidence_score >= 0.7]
    if approved:
        return "apply_and_review"
    if state["suggestions"]:
        return "human_review"
    return "post"


def needs_human_review(state: ReviewState) -> str:
    """After auto-fix, decide if human review is needed."""
    if state["evaluation_results"]:
        low_confidence = [e for e in state["evaluation_results"] if e.confidence_score < 0.7]
        if low_confidence:
            return "human_review"
    return "re_review"


def should_route_on_error(state: ReviewState) -> str:
    """Check if any error occurred and route accordingly."""
    if state.get("error"):
        return "human_review"
    return "ok"
