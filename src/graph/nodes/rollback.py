from __future__ import annotations

from src.github.client import GitHubClient
from src.graph.state import ReviewState


async def rollback_node(state: ReviewState) -> dict:
    """Rollback failed fixes, restore to pre-fix state."""
    github = GitHubClient()
    try:
        pr = await github.get_pr(state["owner"], state["repo"], state["pr_number"])
        original_sha = pr["head"]["sha"]
        branch_name = pr["head"]["ref"]

        # Reset branch to original state (force needed for rollback)
        await github.update_ref(
            state["owner"], state["repo"],
            f"heads/{branch_name}",
            original_sha,
            force=True,
        )
    finally:
        await github.close()

    return {
        "error": "Auto-fix introduced new issues, rolled back",
        "phase": "human",
    }
