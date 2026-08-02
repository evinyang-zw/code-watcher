from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.graph.nodes.aggregate import _deduplicate_findings, aggregate_node
from src.graph.nodes.suggest_fixes import suggest_fixes_node
from src.graph.state import create_review_state
from src.schema.types import CodeSegment, ReviewFinding, ReviewResult


def _make_finding(file_path: str = "a.py", line: int = 1, message: str = "test") -> ReviewFinding:
    return ReviewFinding(
        file_path=file_path,
        line=line,
        severity="warning",
        dimension="style",
        message=message,
    )


def _make_segment(file_path: str = "a.py") -> CodeSegment:
    return CodeSegment(
        file_path=file_path,
        hunk_start=1,
        hunk_end=2,
        old_content="",
        new_content="pass",
        language="python",
        segment_index=0,
    )


def test_deduplicate_findings():
    f1 = _make_finding(message="dup")
    f2 = _make_finding(message="dup")
    f3 = _make_finding(message="unique")
    result = _deduplicate_findings([f1, f2, f3])
    assert len(result) == 2


@pytest.mark.asyncio
async def test_aggregate_node_groups_by_file():
    seg_a = _make_segment("a.py")
    seg_b = _make_segment("b.py")

    review_a = ReviewResult(
        segment=seg_a,
        findings=[_make_finding("a.py", 1, "issue1"), _make_finding("a.py", 5, "issue2")],
    )
    review_b = ReviewResult(
        segment=seg_b,
        findings=[_make_finding("b.py", 3, "issue3")],
    )

    state = create_review_state(segment_reviews=[review_a, review_b])
    result = await aggregate_node(state)

    assert len(result["all_findings"]) == 3
    assert "a.py" in result["file_groups"]
    assert "b.py" in result["file_groups"]
    assert result["file_groups"]["a.py"].total_findings == 2
    assert result["file_groups"]["b.py"].total_findings == 1


@pytest.mark.asyncio
async def test_suggest_fixes_skips_without_suggested_fix():
    finding = _make_finding()
    finding.suggested_fix = None
    finding.severity = "warning"

    state = create_review_state(suggestions=[finding])
    result = await suggest_fixes_node(state)
    assert result["generated_fixes"] == []


@pytest.mark.asyncio
async def test_suggest_fixes_skips_critical():
    finding = _make_finding()
    finding.suggested_fix = "fix it"
    finding.severity = "critical"

    state = create_review_state(suggestions=[finding])
    result = await suggest_fixes_node(state)
    assert result["generated_fixes"] == []


@pytest.mark.asyncio
async def test_suggest_fixes_generates_patch():
    finding = _make_finding()
    finding.suggested_fix = "Use parameterized query"
    finding.severity = "warning"

    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new")

    with patch("src.graph.nodes.suggest_fixes.create_llm_provider", return_value=mock_provider):
        state = create_review_state(suggestions=[finding])
        result = await suggest_fixes_node(state)
        assert len(result["generated_fixes"]) == 1
        assert result["generated_fixes"][0].finding == finding
