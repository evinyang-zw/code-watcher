from __future__ import annotations

import logging

from src.github.factory import get_github_client
from src.graph.state import ReviewState

logger = logging.getLogger(__name__)


async def rollback_node(state: ReviewState) -> dict:
    """Restore the PR branch to the SHA it had before auto-fix started.

    The pre-fix SHA is recorded by ``auto_fix_node``; without it there is
    nothing to roll back and the node is a no-op.
    """
    pre_fix_sha = state.get("pre_fix_sha")
    if not pre_fix_sha:
        logger.warning("Rollback requested but no pre-fix SHA was recorded")
        return {
            "error": "Rollback skipped: no pre-fix SHA recorded",
            "phase": "human",
        }

    github = get_github_client()
    try:
        pr = await github.get_pr(state["owner"], state["repo"], state["pr_number"])
        branch_name = pr["head"]["ref"]
        await github.update_ref(
            state["owner"],
            state["repo"],
            f"heads/{branch_name}",
            pre_fix_sha,
            force=True,
        )
        logger.info("Rolled back %s to %s", branch_name, pre_fix_sha)
    except Exception as exc:  # pragma: no cover - network path
        logger.error("Rollback failed: %s", exc)
        return {"error": f"Rollback failed: {exc}", "phase": "human"}
    finally:
        await github.close()

    return {
        "error": "Auto-fix introduced new issues, rolled back",
        "phase": "human",
    }
