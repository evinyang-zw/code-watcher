from __future__ import annotations

import base64
import os

import httpx


class GitHubClient:
    """Async GitHub REST API v3 client."""

    BASE = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable "
                "or pass token parameter."
            )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_pr(self, owner: str, repo: str, number: int) -> dict:
        resp = await self.client.get(f"{self.BASE}/repos/{owner}/{repo}/pulls/{number}")
        resp.raise_for_status()
        return resp.json()

    async def get_pr_files(self, owner: str, repo: str, number: int) -> list[dict]:
        files = []
        page = 1
        while True:
            resp = await self.client.get(
                f"{self.BASE}/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            files.extend(batch)
            page += 1
        return files

    async def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        resp = await self.client.get(
            f"{self.BASE}/repos/{owner}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    async def post_review(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
        comments: list[dict],
        event: str = "COMMENT",
    ) -> dict:
        resp = await self.client.post(
            f"{self.BASE}/repos/{owner}/{repo}/pulls/{number}/reviews",
            json={"body": body, "comments": comments, "event": event},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        resp = await self.client.get(
            f"{self.BASE}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        resp.raise_for_status()
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8")

    async def get_tree(self, owner: str, repo: str, sha: str) -> dict:
        resp = await self.client.get(f"{self.BASE}/repos/{owner}/{repo}/git/trees/{sha}")
        resp.raise_for_status()
        return resp.json()

    async def create_blob(self, owner: str, repo: str, content: str, encoding: str = "utf-8") -> dict:
        resp = await self.client.post(
            f"{self.BASE}/repos/{owner}/{repo}/git/blobs",
            json={"content": content, "encoding": encoding},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_tree(
        self, owner: str, repo: str, base_tree: str, files: dict[str, str]
    ) -> dict:
        tree = [
            {"path": path, "mode": "100644", "type": "blob", "content": content}
            for path, content in files.items()
        ]
        resp = await self.client.post(
            f"{self.BASE}/repos/{owner}/{repo}/git/trees",
            json={"base_tree": base_tree, "tree": tree},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parents: list[str],
    ) -> str:
        resp = await self.client.post(
            f"{self.BASE}/repos/{owner}/{repo}/git/commits",
            json={"message": message, "tree": tree_sha, "parents": parents},
        )
        resp.raise_for_status()
        return resp.json()["sha"]

    async def update_ref(
        self, owner: str, repo: str, ref: str, sha: str, force: bool = False
    ) -> dict:
        resp = await self.client.patch(
            f"{self.BASE}/repos/{owner}/{repo}/git/refs/{ref}",
            json={"sha": sha, "force": force},
        )
        resp.raise_for_status()
        return resp.json()
