from __future__ import annotations

import copy
import operator
from typing import Annotated, Literal, TypedDict

from src.schema.types import (
    CodeSegment,
    EvaluationResult,
    FileReviewGroup,
    FixPatch,
    ReviewFinding,
    ReviewResult,
    RunMetadata,
)


class ReviewState(TypedDict, total=False):
    """Full state for the Code Watcher LangGraph workflow."""

    # --- Input ---
    pr_url: str
    owner: str
    repo: str
    pr_number: int
    auto_fix_enabled: bool
    dry_run: bool
    review_dimensions: list[str]

    # --- Message history ---
    messages: list[dict]

    # --- Intermediate state ---
    pr_metadata: dict
    raw_diff: str
    files: list[dict]
    segments: list[CodeSegment]
    current_segment_index: int

    # --- Review results (grouped by file) ---
    segment_reviews: Annotated[list[ReviewResult], operator.add]
    file_groups: dict[str, FileReviewGroup]
    all_findings: list[ReviewFinding]

    # --- Fixes ---
    suggestions: list[ReviewFinding]
    generated_fixes: list[FixPatch]
    evaluation_results: list[EvaluationResult]
    approved_fixes: list[FixPatch]

    # --- Human review ---
    human_feedback: str
    human_approved_fixes: list[str]

    # --- Output ---
    review_comments: list[dict]
    review_summary: str
    overall_confidence: float

    # --- Metadata ---
    metadata: RunMetadata

    # --- Workflow control ---
    error: str | None
    phase: str


_DEFAULTS = {
    "pr_url": "",
    "owner": "",
    "repo": "",
    "pr_number": 0,
    "auto_fix_enabled": False,
    "dry_run": False,
    "review_dimensions": ["correctness", "style", "security", "performance"],
    "messages": [],
    "pr_metadata": {},
    "raw_diff": "",
    "files": [],
    "segments": [],
    "current_segment_index": 0,
    "segment_reviews": [],
    "file_groups": {},
    "all_findings": [],
    "suggestions": [],
    "generated_fixes": [],
    "evaluation_results": [],
    "approved_fixes": [],
    "human_feedback": "",
    "human_approved_fixes": [],
    "review_comments": [],
    "review_summary": "",
    "overall_confidence": 0.0,
    "metadata": RunMetadata(),
    "error": None,
    "phase": "fetch",
}


def create_review_state(**kwargs) -> ReviewState:
    """Create a ReviewState with defaults, allowing selective overrides."""
    return {**copy.deepcopy(_DEFAULTS), **kwargs}  # type: ignore[return-value]
