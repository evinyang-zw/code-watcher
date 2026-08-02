from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.graph.edges import (
    needs_human_review,
    should_auto_fix,
    should_continue_to_segment,
    should_re_review,
    should_route_on_error,
)
from src.graph.state import create_review_state
from src.graph.workflow import build_review_graph, compile_workflow
from src.schema.types import (
    CodeSegment,
    EvaluationResult,
    FixPatch,
    ReviewFinding,
    ReviewResult,
    RunMetadata,
)


def test_graph_compiles():
    graph = build_review_graph()
    workflow = graph.compile()
    assert workflow is not None


def test_should_continue_to_segment_more():
    segments = [CodeSegment(
        file_path="a.py", hunk_start=1, hunk_end=2,
        old_content="", new_content="pass", language="python", segment_index=i,
    ) for i in range(3)]
    state = create_review_state(segments=segments, current_segment_index=1)
    assert should_continue_to_segment(state) == "continue"


def test_should_continue_to_segment_done():
    segments = [CodeSegment(
        file_path="a.py", hunk_start=1, hunk_end=2,
        old_content="", new_content="pass", language="python", segment_index=0,
    )]
    state = create_review_state(segments=segments, current_segment_index=1)
    assert should_continue_to_segment(state) == "aggregate"


def test_should_auto_fix_enabled():
    finding = ReviewFinding(
        file_path="a.py", line=1, severity="warning", dimension="style",
        message="test", suggested_fix="fix it",
    )
    state = create_review_state(auto_fix_enabled=True, suggestions=[finding])
    assert should_auto_fix(state) == "auto_fix"


def test_should_auto_fix_disabled():
    finding = ReviewFinding(
        file_path="a.py", line=1, severity="warning", dimension="style",
        message="test", suggested_fix="fix it",
    )
    state = create_review_state(auto_fix_enabled=False, suggestions=[finding])
    assert should_auto_fix(state) == "post"


def test_should_auto_fix_critical():
    finding = ReviewFinding(
        file_path="a.py", line=1, severity="critical", dimension="security",
        message="SQL injection",
    )
    state = create_review_state(auto_fix_enabled=True, suggestions=[finding])
    assert should_auto_fix(state) == "human_review"


def test_should_re_review_approved():
    evaluation = EvaluationResult(
        patch=FixPatch(
            finding=ReviewFinding(file_path="a.py", line=1, severity="warning", dimension="style", message="test"),
            patch_diff="diff", description="fix",
        ),
        syntax_valid=True,
        confidence_score=0.8,
    )
    state = create_review_state(evaluation_results=[evaluation])
    assert should_re_review(state) == "apply_and_review"


def test_should_re_review_low_confidence():
    evaluation = EvaluationResult(
        patch=FixPatch(
            finding=ReviewFinding(file_path="a.py", line=1, severity="warning", dimension="style", message="test"),
            patch_diff="diff", description="fix",
        ),
        syntax_valid=True,
        confidence_score=0.5,
    )
    state = create_review_state(evaluation_results=[evaluation], suggestions=[evaluation.patch.finding])
    assert should_re_review(state) == "human_review"


def test_needs_human_review_low_confidence():
    evaluation = EvaluationResult(
        patch=FixPatch(
            finding=ReviewFinding(file_path="a.py", line=1, severity="warning", dimension="style", message="test"),
            patch_diff="diff", description="fix",
        ),
        syntax_valid=True,
        confidence_score=0.5,
    )
    state = create_review_state(evaluation_results=[evaluation])
    assert needs_human_review(state) == "human_review"


def test_needs_human_review_high_confidence():
    evaluation = EvaluationResult(
        patch=FixPatch(
            finding=ReviewFinding(file_path="a.py", line=1, severity="warning", dimension="style", message="test"),
            patch_diff="diff", description="fix",
        ),
        syntax_valid=True,
        confidence_score=0.8,
    )
    state = create_review_state(evaluation_results=[evaluation])
    assert needs_human_review(state) == "re_review"


def test_should_route_on_error():
    state = create_review_state(error="Something went wrong")
    assert should_route_on_error(state) == "human_review"


def test_should_route_on_no_error():
    state = create_review_state()
    assert should_route_on_error(state) == "ok"
