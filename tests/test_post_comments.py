from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.graph.nodes.post_comments import (
    _format_inline_comments,
    _format_review_body,
    post_comments_node,
)
from src.graph.state import create_review_state
from src.schema.types import ReviewFinding


def test_format_review_body_empty():
    state = create_review_state()
    body = _format_review_body(state)
    assert "Code Watcher Review" in body
    assert "0 total" in body


def test_format_review_body_with_findings():
    findings = [
        ReviewFinding(file_path="a.py", line=1, severity="critical", dimension="security", message="SQL injection"),
        ReviewFinding(file_path="a.py", line=5, severity="warning", dimension="style", message="Use f-string"),
    ]
    state = create_review_state(all_findings=findings, overall_confidence=0.85)
    body = _format_review_body(state)
    assert "Critical: 1" in body
    assert "Warning: 1" in body
    assert "0.85" in body


def test_format_inline_comments():
    findings = [
        ReviewFinding(file_path="a.py", line=1, severity="critical", dimension="security", message="SQL injection"),
        ReviewFinding(file_path="a.py", line=5, severity="nit", dimension="style", message="Minor style"),
    ]
    state = create_review_state(all_findings=findings)
    comments = _format_inline_comments(state)
    assert len(comments) == 1  # Only critical/warning
    assert comments[0]["path"] == "a.py"
    assert comments[0]["line"] == 1


@pytest.mark.asyncio
async def test_post_comments_node():
    state = create_review_state(
        owner="test",
        repo="repo",
        pr_number=1,
        all_findings=[
            ReviewFinding(file_path="a.py", line=1, severity="warning", dimension="style", message="test"),
        ],
    )

    mock_client = AsyncMock()
    mock_client.post_review = AsyncMock()
    mock_client.close = AsyncMock()

    with patch("src.graph.nodes.post_comments.GitHubClient", return_value=mock_client):
        result = await post_comments_node(state)

    assert result["phase"] == "done"
    mock_client.post_review.assert_called_once()
