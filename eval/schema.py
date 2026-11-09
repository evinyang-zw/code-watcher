"""Data models for the code-review evaluation harness.

The evaluation treats *human inline review comments on merged PRs* as the
ground truth: the agent reviews the same PR diff that a human reviewed, and its
findings are matched against the comments that reviewer left. This is the same
protocol family as public code-review benchmarks, without claiming to be one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

InstanceKind = Literal["bug", "clean"]
Category = Literal["bug", "security", "performance", "style", "other"]

# Heuristics used to bucket a human comment; documented in eval/README.md.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("security", "vulnerab", "injection", "xss", "csrf", "secret", "credential")),
    ("performance", ("performance", "slow", "o(n)", "memory", "leak", "cache")),
    (
        "bug",
        (
            "bug",
            "error",
            "wrong",
            "incorrect",
            "crash",
            "exception",
            "fail",
            "broken",
            "off-by-one",
        ),
    ),
    (
        "style",
        (
            "style",
            "nit",
            "naming",
            "rename",
            "format",
            "typo",
            "docstring",
            "readability",
        ),
    ),
)

# Comments that are not actionable issues (praise, approvals, bot noise).
_NOISE_PATTERNS = (
    "lgtm",
    "looks good",
    "thanks",
    "thank you",
    "nice",
    "great",
    "awesome",
    "ship it",
    "approve",
)


def infer_category(text: str) -> Category:
    """Best-effort category label for a human review comment."""
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category  # type: ignore[return-value]
    return "other"


# Reviewers must be associated with the repository; this filters drive-by
# comments and most AI review accounts that are not flagged as bots.
TRUSTED_ASSOCIATIONS = {"MEMBER", "OWNER", "COLLABORATOR", "CONTRIBUTOR"}


def is_actionable_comment(body: str) -> bool:
    """Filter obvious praise/approval comments out of the gold set."""
    lowered = body.strip().lower()
    if len(lowered) < 15:
        return False
    return not any(pattern in lowered for pattern in _NOISE_PATTERNS)


@dataclass
class GoldComment:
    """One human inline review comment used as ground truth."""

    path: str
    line: int
    body: str
    category: Category = "other"
    author: str = ""
    has_suggestion: bool = False

    @classmethod
    def from_github(cls, payload: dict[str, Any]) -> GoldComment | None:
        path = payload.get("path")
        line = payload.get("line") or payload.get("original_line")
        body = payload.get("body") or ""
        if not path or not line or not body:
            return None
        # Replies are conversation, not independent findings.
        if payload.get("in_reply_to_id"):
            return None
        # Only reviewers associated with the repository (filters drive-bys and
        # unlabelled AI review accounts).
        if str(payload.get("author_association", "")).upper() not in TRUSTED_ASSOCIATIONS:
            return None
        if not is_actionable_comment(body):
            return None
        user = payload.get("user") or {}
        if str(user.get("type", "")).lower() == "bot":
            return None
        if str(user.get("login", "")).endswith("[bot]"):
            return None
        cleaned = body.strip()
        return cls(
            path=str(path),
            line=int(line),
            body=cleaned,
            category=infer_category(cleaned),
            author=str(user.get("login", "")),
            has_suggestion="```suggestion" in cleaned,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GoldComment:
        return cls(
            path=payload["path"],
            line=int(payload["line"]),
            body=payload["body"],
            category=payload.get("category", "other"),
            author=payload.get("author", ""),
            has_suggestion=bool(
                payload.get("has_suggestion", "```suggestion" in payload.get("body", ""))
            ),
        )


@dataclass
class Instance:
    """One PR used for evaluation (bug-fix PR with comments, or clean PR)."""

    id: str
    repo: str
    pr_number: int
    title: str
    kind: InstanceKind
    patch: str
    gold: list[GoldComment] = field(default_factory=list)
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    url: str = ""

    @property
    def pr_url(self) -> str:
        return f"https://github.com/{self.repo}/pull/{self.pr_number}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gold"] = [comment.to_dict() for comment in self.gold]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Instance:
        return cls(
            id=payload["id"],
            repo=payload["repo"],
            pr_number=int(payload["pr_number"]),
            title=payload.get("title", ""),
            kind=payload.get("kind", "bug"),
            patch=payload["patch"],
            gold=[GoldComment.from_dict(item) for item in payload.get("gold", [])],
            files_changed=int(payload.get("files_changed", 0)),
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            url=payload.get("url", ""),
        )


@dataclass
class Finding:
    """One finding produced by the agent."""

    file: str
    line: int
    severity: str
    dimension: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
