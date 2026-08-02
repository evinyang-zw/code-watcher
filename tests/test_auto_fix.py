from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.graph.nodes.auto_fix import _extract_path_from_diff, auto_fix_node
from src.graph.state import create_review_state
from src.schema.types import FixPatch, ReviewFinding


def test_extract_path_from_diff():
    diff = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new"
    assert _extract_path_from_diff(diff) == "src/app.py"


def test_extract_path_from_diff_no_match():
    diff = "some random text"
    assert _extract_path_from_diff(diff) == "unknown"


@pytest.mark.asyncio
async def test_auto_fix_dry_run():
    finding = ReviewFinding(
        file_path="a.py", line=1, severity="warning",
        dimension="style", message="test",
    )
    fix_patch = FixPatch(finding=finding, patch_diff="diff", description="fix")
    state = create_review_state(
        dry_run=True,
        approved_fixes=[fix_patch],
        owner="test",
        repo="repo",
        pr_number=1,
    )
    result = await auto_fix_node(state)
    assert result["phase"] == "re_review"
    assert "Dry run" in result.get("review_summary", "")


@pytest.mark.asyncio
async def test_auto_fix_with_mock_github():
    finding = ReviewFinding(
        file_path="a.py", line=1, severity="warning",
        dimension="style", message="test",
    )
    # Valid unified diff format
    valid_diff = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new"
    fix_patch = FixPatch(finding=finding, patch_diff=valid_diff, description="fix")

    mock_client = AsyncMock()
    mock_client.get_pr = AsyncMock(return_value={
        "head": {"sha": "abc123", "ref": "main"}
    })
    mock_client.get_file_content = AsyncMock(return_value="original")
    mock_client.get_tree = AsyncMock(return_value={"sha": "tree123"})
    mock_client.create_tree = AsyncMock(return_value={"sha": "newtree"})
    mock_client.create_commit = AsyncMock(return_value="commit123")
    mock_client.update_ref = AsyncMock()
    mock_client.close = AsyncMock()

    state = create_review_state(
        dry_run=False,
        approved_fixes=[fix_patch],
        owner="test",
        repo="repo",
        pr_number=1,
    )

    with patch("src.graph.nodes.auto_fix.GitHubClient", return_value=mock_client):
        result = await auto_fix_node(state)

    assert result["phase"] == "re_review"
    mock_client.create_commit.assert_called_once()
    mock_client.update_ref.assert_called_once()
