"""HTTP-level tests for GitHubClient (uses `respx` to mock the GitHub API)."""

from __future__ import annotations

import httpx
import pytest
import respx

from src.github.client import GitHubClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    return GitHubClient()


def test_client_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GitHub token is required"):
        GitHubClient()


@pytest.mark.asyncio
@respx.mock
async def test_get_pr(client):
    route = respx.get("https://api.github.com/repos/acme/demo/pulls/7").mock(
        return_value=httpx.Response(200, json={"number": 7, "title": "demo"})
    )
    pr = await client.get_pr("acme", "demo", 7)
    assert pr["number"] == 7
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-token"
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_pr_diff_asks_for_diff_media_type(client):
    route = respx.get("https://api.github.com/repos/acme/demo/pulls/7").mock(
        return_value=httpx.Response(200, text="--- a/a.py\n+++ b/a.py\n")
    )
    diff = await client.get_pr_diff("acme", "demo", 7)
    assert diff.startswith("--- a/a.py")
    assert route.calls[0].request.headers["Accept"] == "application/vnd.github.v3.diff"
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_post_review_payload(client):
    route = respx.post("https://api.github.com/repos/acme/demo/pulls/7/reviews").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    await client.post_review(
        "acme",
        "demo",
        7,
        body="summary",
        comments=[{"path": "a.py", "line": 3, "body": "issue"}],
    )
    sent = route.calls[0].request
    assert sent.method == "POST"
    body = sent.read().decode()
    assert '"body": "summary"' in body or '"body":"summary"' in body
    assert "a.py" in body
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_file_content_decodes_base64(client):
    import base64

    encoded = base64.b64encode(b"print('hi')\n").decode()
    respx.get("https://api.github.com/repos/acme/demo/contents/a.py").mock(
        return_value=httpx.Response(200, json={"content": encoded, "encoding": "base64"})
    )
    assert await client.get_file_content("acme", "demo", "a.py", "sha") == "print('hi')\n"
    await client.close()
