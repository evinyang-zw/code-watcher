from __future__ import annotations

import logging
import re

from src.github.factory import get_github_client
from src.github.patch import PatchApplyError, apply_patch, strip_code_fences
from src.graph.state import ReviewState

logger = logging.getLogger(__name__)


def _extract_path_from_diff(patch_diff: str) -> str:
    """Extract the target file path from a unified diff."""
    text = strip_code_fences(patch_diff)
    match = re.search(r"^\+\+\+ b/(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    match = re.search(r"^--- a/(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    raise PatchApplyError("cannot determine target file from patch")


def _tail(message: str, limit: int = 400) -> str:
    return message if len(message) <= limit else message[:limit] + "…"


async def auto_fix_node(state: ReviewState) -> dict:
    """Apply approved patches as per-file commits on the PR branch.

    Safety properties:
    - dry-run by default (``state["dry_run"]`` is True unless explicitly disabled);
    - the pre-fix head SHA is recorded so ``rollback`` can restore it;
    - every patch is applied against the *current* file content and verified
      by ``apply_patch`` before a commit is created;
    - one attempt per run: ``fix_attempts`` bounds the graph loop.
    """
    approved = list(state.get("approved_fixes") or [])
    attempts = int(state.get("fix_attempts") or 0)
    next_attempts = attempts + 1

    if state.get("dry_run", True):
        summary = (
            f"Dry run: generated {len(approved)} fix(es), none applied. "
            "Re-run with --apply to push fixes."
        )
        logger.info(summary)
        return {
            "fix_attempts": next_attempts,
            "phase": "post",
            "review_summary": _append_summary(state, summary),
        }

    github = get_github_client()
    applied = 0
    failures: list[str] = []
    pre_fix_sha: str | None = None
    try:
        pr = await github.get_pr(state["owner"], state["repo"], state["pr_number"])
        base_sha = pr["head"]["sha"]
        pre_fix_sha = base_sha
        branch_name = pr["head"]["ref"]

        for patch in approved:
            try:
                file_path = _extract_path_from_diff(patch.patch_diff)
                original = await github.get_file_content(
                    state["owner"], state["repo"], file_path, base_sha
                )
                patched = apply_patch(original, patch.patch_diff)

                new_tree = await github.create_tree(
                    state["owner"], state["repo"], base_sha, {file_path: patched}
                )
                commit_sha = await github.create_commit(
                    state["owner"],
                    state["repo"],
                    message=f"fix({file_path}): {patch.description}",
                    tree_sha=new_tree["sha"],
                    parents=[base_sha],
                )
                await github.update_ref(
                    state["owner"],
                    state["repo"],
                    f"heads/{branch_name}",
                    commit_sha,
                )
                patch.commit_sha = commit_sha
                base_sha = commit_sha
                applied += 1
            except Exception as exc:  # one bad patch must not abort the batch
                logger.warning("Failed to apply fix %s: %s", patch.finding.finding_id, exc)
                failures.append(f"{patch.finding.finding_id}: {exc}")
    except Exception as exc:
        logger.error("Auto-fix could not start: %s", exc)
        failures.append(f"setup: {exc}")
    finally:
        await github.close()

    summary = f"Auto-fix: applied {applied}/{len(approved)} fix(es)."
    if failures:
        summary += " Failures: " + _tail("; ".join(failures))
    return {
        "fix_attempts": next_attempts,
        "pre_fix_sha": pre_fix_sha,
        "phase": "post",
        "review_summary": _append_summary(state, summary),
    }


def _append_summary(state: ReviewState, message: str) -> str:
    previous = state.get("review_summary") or ""
    return f"{previous}\n{message}".strip()
