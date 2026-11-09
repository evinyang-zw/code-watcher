"""Collect a code-review gold set from merged GitHub PRs.

The ground truth is *human inline review comments*: for every merged PR we keep
the comments a reviewer left on specific lines, and the agent is later asked to
review the same diff. "Clean" PRs are merged PRs with no actionable inline
comments; they measure the false-positive rate.

Usage::

    GITHUB_TOKEN=ghp_xxx python -m eval.collect \
        --repos psf/requests,pallets/flask --bug 30 --clean 15 \
        --out eval/data/gold_review.jsonl

Data source is public; only a token for rate limits is needed (read-only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from eval.schema import GoldComment, Instance

API = "https://api.github.com"

PYTHON_RE = re.compile(r"^\+\+\+ b/.*\.py$", re.MULTILINE)
MAX_COMMITS = 5


class GitHub:
    """Minimal read-only GitHub REST client."""

    def __init__(self, token: str = ""):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(base_url=API, headers=headers, timeout=30.0)

    def get(self, path: str, **params: Any) -> Any:
        for attempt in range(3):
            response = self.client.get(path, params=params or None)
            if response.status_code in (403, 429) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"GitHub request failed: {path}")

    def get_diff(self, repo: str, number: int) -> str:
        response = self.client.get(
            f"/repos/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        self.client.close()


def _is_merged(pr: dict[str, Any]) -> bool:
    return bool(pr.get("merged_at"))


def _labels(pr: dict[str, Any]) -> set[str]:
    return {str(label.get("name", "")).lower() for label in pr.get("labels", [])}


def _size_ok(pr: dict[str, Any]) -> bool:
    """List responses omit additions/deletions, so callers pass PR details."""
    changed = pr.get("changed_files") or 0
    additions = pr.get("additions") or 0
    deletions = pr.get("deletions") or 0
    commits = pr.get("commits") or 0
    return 0 < changed <= 10 and 3 <= additions + deletions <= 250 and 0 < commits <= MAX_COMMITS


def _pr_detail(gh: GitHub, repo: str, number: int) -> dict[str, Any]:
    """Fetch the PR detail (list responses omit additions/deletions)."""
    return gh.get(f"/repos/{repo}/pulls/{number}")


def _has_approval(gh: GitHub, repo: str, number: int) -> bool:
    """A clean PR is one a reviewer approved AND left no actionable comments on."""
    try:
        reviews = gh.get(f"/repos/{repo}/pulls/{number}/reviews", per_page=100)
    except Exception:  # pragma: no cover - network
        return False
    return any(str(review.get("state", "")).upper() == "APPROVED" for review in reviews)


def _inline_comments(gh: GitHub, repo: str, number: int) -> list[GoldComment]:
    payload = gh.get(f"/repos/{repo}/pulls/{number}/comments", per_page=100)
    comments = []
    for item in payload:
        comment = GoldComment.from_github(item)
        if comment is not None:
            comments.append(comment)
    return comments


def _make_instance(
    gh: GitHub, repo: str, pr: dict[str, Any], kind: str, gold: list[GoldComment]
) -> Instance | None:
    patch = gh.get_diff(repo, pr["number"])
    if not PYTHON_RE.search(patch):
        return None
    return Instance(
        id=f"{repo.replace('/', '_')}-{pr['number']}",
        repo=repo,
        pr_number=int(pr["number"]),
        title=str(pr.get("title", "")),
        kind=kind,  # type: ignore[arg-type]
        patch=patch,
        gold=gold,
        files_changed=int(pr.get("changed_files") or 0),
        additions=int(pr.get("additions") or 0),
        deletions=int(pr.get("deletions") or 0),
        url=str(pr.get("html_url", "")),
    )


def _iter_merged(gh: GitHub, repo: str, max_pages: int) -> Iterator[dict[str, Any]]:
    for page in range(1, max_pages + 1):
        batch = gh.get(
            f"/repos/{repo}/pulls",
            state="closed",
            sort="updated",
            direction="desc",
            per_page=50,
            page=page,
        )
        if not batch:
            return
        for pr in batch:
            if _is_merged(pr):
                yield pr


def collect(
    repos: list[str],
    want_bug: int,
    want_clean: int,
    max_pages: int = 6,
    max_gold: int = 3,
) -> list[Instance]:
    """Collect bug-fix and clean PR instances across repositories."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print(
            "[collect] no GITHUB_TOKEN: running anonymously (60 req/h — only useful "
            "for a small validation sample)",
            file=sys.stderr,
        )
    gh = GitHub(token)
    instances: list[Instance] = []
    bug_count = 0
    clean_count = 0

    try:
        for repo in repos:
            print(f"[collect] {repo}", file=sys.stderr)
            for pr in _iter_merged(gh, repo, max_pages):
                if bug_count >= want_bug and clean_count >= want_clean:
                    break
                try:
                    detail = _pr_detail(gh, repo, pr["number"])
                except Exception as exc:  # pragma: no cover - network
                    print(f"  skip {pr['number']}: detail failed ({exc})", file=sys.stderr)
                    continue
                if not _size_ok(detail):
                    continue
                pr = {**pr, **detail}

                try:
                    comments = _inline_comments(gh, repo, pr["number"])
                except Exception as exc:  # pragma: no cover - network
                    print(f"  skip {pr['number']}: comments failed ({exc})", file=sys.stderr)
                    continue

                if comments and bug_count < want_bug:
                    if len(comments) > max_gold:
                        continue
                    instance = _make_instance(gh, repo, pr, "bug", comments)
                    if instance:
                        instances.append(instance)
                        bug_count += 1
                        print(
                            f"  reviewed {repo}#{pr['number']}: {len(comments)} comments",
                            file=sys.stderr,
                        )
                elif not comments and clean_count < want_clean:
                    if not _has_approval(gh, repo, pr["number"]):
                        continue
                    instance = _make_instance(gh, repo, pr, "clean", [])
                    if instance:
                        instances.append(instance)
                        clean_count += 1
                        print(f"  clean {repo}#{pr['number']}", file=sys.stderr)
            if bug_count >= want_bug and clean_count >= want_clean:
                break
    finally:
        gh.close()

    print(
        f"[collect] collected {bug_count} bug + {clean_count} clean instances",
        file=sys.stderr,
    )
    return instances


def save(instances: list[Instance], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for instance in instances:
            fh.write(json.dumps(instance.to_dict(), ensure_ascii=False) + "\n")


def load(path: Path) -> list[Instance]:
    with path.open(encoding="utf-8") as fh:
        return [Instance.from_dict(json.loads(line)) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect a code-review gold set")
    parser.add_argument(
        "--repos",
        default="psf/requests,pallets/flask,encode/httpx",
        help="Comma separated owner/repo list",
    )
    parser.add_argument("--bug", type=int, default=30, help="Number of bug-fix PRs")
    parser.add_argument("--clean", type=int, default=15, help="Number of clean PRs")
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--max-gold", type=int, default=3)
    parser.add_argument("--out", default="eval/data/gold_review.jsonl")
    args = parser.parse_args(argv)

    instances = collect(
        [repo.strip() for repo in args.repos.split(",") if repo.strip()],
        want_bug=args.bug,
        want_clean=args.clean,
        max_pages=args.max_pages,
        max_gold=args.max_gold,
    )
    if not instances:
        print("No instances collected", file=sys.stderr)
        return 1
    save(instances, Path(args.out))
    print(f"wrote {len(instances)} instances to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
