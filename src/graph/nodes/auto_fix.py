from __future__ import annotations

import logging
import re

from src.github.client import GitHubClient
from src.graph.state import ReviewState

logger = logging.getLogger(__name__)


def _extract_path_from_diff(patch_diff: str) -> str:
    """Extract file path from a unified diff."""
    match = re.search(r"^\+\+\+ b/(.+)$", patch_diff, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r"^--- a/(.+)$", patch_diff, re.MULTILINE)
    if match:
        return match.group(1)
    return "unknown"


def _apply_unified_diff(original: str, patch_diff: str) -> tuple[str, bool]:
    """Apply a unified diff to original content. Returns (patched_content, success).

    This is a simplified patch application that handles basic line replacements.
    For production use, consider using the `patch` or `unidiff` library properly.
    """
    try:
        original_lines = original.splitlines(keepends=True)
        result_lines = []
        orig_idx = 0

        for line in patch_diff.splitlines():
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            elif line.startswith("-"):
                # Removed line - skip from original
                orig_idx += 1
            elif line.startswith("+"):
                # Added line - add to result
                result_lines.append(line[1:] + "\n")
            elif line.startswith(" "):
                # Context line - keep from original
                if orig_idx < len(original_lines):
                    result_lines.append(original_lines[orig_idx])
                orig_idx += 1
            else:
                # Unknown line type - skip
                continue

        # Append any remaining original lines (not in diff)
        while orig_idx < len(original_lines):
            result_lines.append(original_lines[orig_idx])
            orig_idx += 1

        return "".join(result_lines), True
    except Exception as e:
        logger.warning("Failed to apply patch: %s", e)
        return original, False


async def auto_fix_node(state: ReviewState) -> dict:
    """Apply approved patches, create per-file commits on PR branch."""
    if state["dry_run"]:
        return {
            "phase": "re_review",
            "review_summary": f"Dry run: would apply {len(state['approved_fixes'])} fixes",
        }

    github = GitHubClient()
    try:
        pr = await github.get_pr(state["owner"], state["repo"], state["pr_number"])
        base_sha = pr["head"]["sha"]
        branch_name = pr["head"]["ref"]

        for patch in state["approved_fixes"]:
            file_path = _extract_path_from_diff(patch.patch_diff)

            try:
                original = await github.get_file_content(
                    state["owner"], state["repo"], file_path, base_sha
                )

                # Apply the unified diff
                patched, success = _apply_unified_diff(original, patch.patch_diff)
                if not success:
                    patch.commit_sha = None
                    continue

                new_tree = await github.create_tree(
                    state["owner"], state["repo"], base_sha, {file_path: patched}
                )
                commit_sha = await github.create_commit(
                    state["owner"], state["repo"],
                    message=f"fix({file_path}): {patch.description}",
                    tree_sha=new_tree["sha"],
                    parents=[base_sha],
                )

                await github.update_ref(
                    state["owner"], state["repo"],
                    f"heads/{branch_name}",
                    commit_sha,
                )

                patch.commit_sha = commit_sha
                base_sha = commit_sha

            except Exception as e:
                logger.warning("Failed to apply fix for %s: %s", file_path, e)
                patch.commit_sha = None
                continue

    finally:
        await github.close()

    return {"phase": "re_review"}
