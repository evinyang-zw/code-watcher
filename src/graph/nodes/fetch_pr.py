from __future__ import annotations

import re

from src.github.client import GitHubClient
from src.graph.state import ReviewState


def _parse_pr_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo, pr_number from a GitHub PR URL."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        raise ValueError(f"Invalid PR URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


async def fetch_pr_node(state: ReviewState) -> dict:
    """Fetch PR metadata and raw diff from GitHub."""
    try:
        owner, repo, pr_number = _parse_pr_url(state["pr_url"])
    except Exception as e:
        return {"error": str(e), "phase": "fetch"}

    github = GitHubClient()
    try:
        pr_metadata = await github.get_pr(owner, repo, pr_number)
        raw_diff = await github.get_pr_diff(owner, repo, pr_number)
    except Exception as e:
        return {"error": f"Failed to fetch PR: {e}", "phase": "fetch"}
    finally:
        await github.close()

    return {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "pr_metadata": pr_metadata,
        "raw_diff": raw_diff,
        "phase": "parse",
    }
