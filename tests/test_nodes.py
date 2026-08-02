from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.graph.nodes.fetch_pr import _parse_pr_url
from src.graph.nodes.parse_diff import parse_diff_node
from src.graph.nodes.segment_code import segment_code_node
from src.graph.state import create_review_state


def test_parse_pr_url_valid():
    owner, repo, number = _parse_pr_url("https://github.com/owner/repo/pull/42")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 42


def test_parse_pr_url_invalid():
    with pytest.raises(ValueError):
        _parse_pr_url("https://notgithub.com/owner/repo/pull/42")


@pytest.mark.asyncio
async def test_parse_diff_node(sample_diff):
    state = create_review_state(raw_diff=sample_diff)
    result = await parse_diff_node(state)
    assert "files" in result
    assert len(result["files"]) == 1
    assert result["phase"] == "segment"


@pytest.mark.asyncio
async def test_segment_code_node(sample_diff):
    state = create_review_state(raw_diff=sample_diff)
    result = await segment_code_node(state)
    assert "segments" in result
    assert len(result["segments"]) >= 1
    assert result["phase"] == "cache_check"


@pytest.mark.asyncio
async def test_fetch_pr_node_with_mock(sample_review_state):
    mock_pr = {"number": 1, "title": "Test PR", "head": {"sha": "abc123"}}
    mock_diff = "diff --git a/test.py b/test.py\n--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new"

    mock_client = AsyncMock()
    mock_client.get_pr = AsyncMock(return_value=mock_pr)
    mock_client.get_pr_diff = AsyncMock(return_value=mock_diff)
    mock_client.close = AsyncMock()

    with patch("src.graph.nodes.fetch_pr.GitHubClient", return_value=mock_client):
        from src.graph.nodes.fetch_pr import fetch_pr_node
        result = await fetch_pr_node(sample_review_state)

    assert result["owner"] == "test"
    assert result["repo"] == "repo"
    assert result["pr_number"] == 1
    assert result["pr_metadata"] == mock_pr
    assert result["raw_diff"] == mock_diff
    assert result["phase"] == "parse"
