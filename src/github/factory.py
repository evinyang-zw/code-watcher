"""Factory for GitHub API clients.

Nodes call :func:`get_github_client` instead of instantiating
``GitHubClient`` directly, which gives the workflow an offline mode:

- ``CODEWATCHER_GITHUB=fake`` + ``CODEWATCHER_FIXTURE_DIR=<dir>`` returns a
  :class:`~src.github.fake_client.FakeGitHubClient` backed by a fixture
  directory (no token, no network).
- otherwise the real :class:`~src.github.client.GitHubClient` is returned and
  ``GITHUB_TOKEN`` is required as usual.
"""

from __future__ import annotations

import os

from src.github.client import GitHubClient
from src.github.fake_client import FakeGitHubClient

OFFLINE_MODES = {"fake", "offline", "fixture"}

GitHubClientLike = GitHubClient | FakeGitHubClient


def is_offline() -> bool:
    """Whether the process should talk to fixtures instead of GitHub."""
    return os.environ.get("CODEWATCHER_GITHUB", "").strip().lower() in OFFLINE_MODES


def get_github_client() -> GitHubClientLike:
    """Return the GitHub client configured for this process."""
    if is_offline():
        fixture_dir = os.environ.get("CODEWATCHER_FIXTURE_DIR", "fixtures/pr-101")
        return FakeGitHubClient(fixture_dir)
    return GitHubClient()
