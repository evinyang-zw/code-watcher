"""Offline (fixture-backed) GitHub client.

Used by the offline demo, the graph-level tests and the evaluation harness so
that the workflow can run end-to-end without a GitHub token or network access.
The fixture directory is expected to contain:

- ``meta.json``          PR metadata (same shape as the GitHub REST response)
- ``diff.patch``         the unified diff of the PR
- ``files_at_head.json`` optional mapping of ``{path: file content}`` at head
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FakeGitHubClient:
    """A GitHub client that reads a fixture directory instead of the network."""

    def __init__(self, fixture_dir: str | Path):
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.is_dir():
            raise ValueError(f"fixture directory not found: {self.fixture_dir}")

        self.meta: dict[str, Any] = json.loads(
            (self.fixture_dir / "meta.json").read_text(encoding="utf-8")
        )
        self.diff: str = (self.fixture_dir / "diff.patch").read_text(encoding="utf-8")

        files_path = self.fixture_dir / "files_at_head.json"
        self.files: dict[str, str] = (
            json.loads(files_path.read_text(encoding="utf-8")) if files_path.exists() else {}
        )

        # Recorded side effects (asserted by tests / printed by the demo).
        self.posted_reviews: list[dict[str, Any]] = []
        self.ref_updates: list[dict[str, Any]] = []
        self.commits: list[dict[str, Any]] = []
        self.closed = False

    async def get_pr(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self.meta

    async def get_pr_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return []

    async def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        return self.diff

    async def post_review(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
        comments: list[dict[str, Any]],
        event: str = "COMMENT",
    ) -> dict[str, Any]:
        record = {
            "owner": owner,
            "repo": repo,
            "number": number,
            "body": body,
            "comments": comments,
            "event": event,
        }
        self.posted_reviews.append(record)
        return record

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        if path not in self.files:
            raise KeyError(f"fixture has no content for {path}")
        return self.files[path]

    async def create_tree(
        self, owner: str, repo: str, base_tree: str, files: dict[str, str]
    ) -> dict[str, Any]:
        return {"sha": f"fixture-tree-{len(self.files)}"}

    async def create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parents: list[str],
    ) -> str:
        sha = f"fixture-commit-{len(self.commits) + 1}"
        self.commits.append({"sha": sha, "message": message, "parents": parents})
        return sha

    async def update_ref(
        self,
        owner: str,
        repo: str,
        ref: str,
        sha: str,
        force: bool = False,
    ) -> dict[str, Any]:
        record = {"ref": ref, "sha": sha, "force": force}
        self.ref_updates.append(record)
        return record

    async def close(self) -> None:
        self.closed = True
