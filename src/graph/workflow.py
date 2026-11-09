from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.graph.edges import (
    needs_human_review,
    route_after_cache,
    should_auto_fix,
    should_continue_to_segment,
    should_re_review,
    should_route_on_error,
)
from src.graph.nodes import (
    aggregate,
    auto_fix,
    cache_check,
    fetch_pr,
    human_review,
    parse_diff,
    post_comments,
    retry,
    review_segment,
    rollback,
    segment_code,
    self_evaluate,
    suggest_fixes,
)
from src.graph.state import ReviewState


def build_review_graph() -> StateGraph:
    """Build the Code Watcher StateGraph."""
    graph = StateGraph(ReviewState)

    # --- Nodes ---
    graph.add_node("fetch_pr", fetch_pr.fetch_pr_node)
    graph.add_node("parse_diff", parse_diff.parse_diff_node)
    graph.add_node("segment_code", segment_code.segment_code_node)
    graph.add_node("cache_check", cache_check.cache_check_node)
    graph.add_node("review_segment", review_segment.review_segment_node)
    graph.add_node("aggregate", aggregate.aggregate_node)
    graph.add_node("suggest_fixes", suggest_fixes.suggest_fixes_node)
    graph.add_node("self_evaluate", self_evaluate.self_evaluate_node)
    graph.add_node("auto_fix", auto_fix.auto_fix_node)
    graph.add_node("rollback", rollback.rollback_node)
    graph.add_node("human_review", human_review.human_review_node)
    graph.add_node("post_comments", post_comments.post_comments_node)
    graph.add_node("retry", retry.retry_node)

    # --- Linear start ---
    graph.add_edge(START, "fetch_pr")
    graph.add_conditional_edges(
        "fetch_pr",
        should_route_on_error,
        {
            "ok": "parse_diff",
            "human_review": "human_review",
        },
    )
    graph.add_edge("parse_diff", "segment_code")
    graph.add_edge("segment_code", "cache_check")

    # --- Segment review loop (cache-aware for every segment) ---
    graph.add_conditional_edges(
        "cache_check",
        route_after_cache,
        {
            "cache_hit": "cache_check",
            "review_segment": "review_segment",
            "aggregate": "aggregate",
        },
    )
    graph.add_conditional_edges(
        "review_segment",
        should_continue_to_segment,
        {
            "continue": "cache_check",
            "aggregate": "aggregate",
        },
    )

    # --- After aggregation ---
    graph.add_edge("aggregate", "suggest_fixes")
    graph.add_conditional_edges(
        "suggest_fixes",
        should_auto_fix,
        {
            "auto_fix": "self_evaluate",
            "human_review": "human_review",
            "post": "post_comments",
        },
    )

    # --- Self-evaluation routing ---
    graph.add_conditional_edges(
        "self_evaluate",
        should_re_review,
        {
            "apply_and_review": "auto_fix",
            "human_review": "human_review",
            "post": "post_comments",
        },
    )

    # --- Auto-fix routing ---
    graph.add_conditional_edges(
        "auto_fix",
        needs_human_review,
        {
            # Low-confidence fixes are rolled back before the human gate.
            "human_review": "rollback",
            "post": "post_comments",
        },
    )

    # --- Rollback routes to human review ---
    graph.add_edge("rollback", "human_review")

    # --- Terminal ---
    graph.add_edge("human_review", "post_comments")
    graph.add_edge("post_comments", END)

    return graph


def compile_workflow(checkpointer: Any | None = None) -> Any:
    """Compile the review workflow.

    Pass an explicit checkpointer (``MemorySaver`` in tests, an async SQLite
    saver for cross-process resume via ``--persist``); otherwise the run keeps
    its state in memory.
    """
    graph = build_review_graph()
    if checkpointer is None:
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
