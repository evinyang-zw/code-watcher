"""Graph-level end-to-end tests.

These are the tests the original repository was missing: every test called a
node function directly, so the compiled graph (state injection, conditional
edges, reducers, interrupt/resume) was never exercised. Everything here runs
against the offline fixtures: no token, no network, no real LLM.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.cache.review_cache import get_cache
from src.graph.state import create_review_state
from src.graph.workflow import compile_workflow

WARNINGS_FIXTURE = "fixtures/pr-102"
CRITICAL_FIXTURE = "fixtures/pr-101"
PR_102 = "https://github.com/acme/demo/pull/102"
PR_101 = "https://github.com/acme/demo/pull/101"


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    """Point the factories at fixtures + mock LLM for every test here."""
    monkeypatch.setenv("CODEWATCHER_GITHUB", "fake")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("GITHUB_TOKEN", "offline")
    get_cache().clear()
    yield
    get_cache().clear()


def configure(fixture: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEWATCHER_FIXTURE_DIR", fixture)
    monkeypatch.setenv("MOCK_LLM_FIXTURE", f"{fixture}/mock_llm.json")


def _config(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}, "recursion_limit": 50}


@pytest.mark.asyncio
async def test_graph_runs_end_to_end(monkeypatch):
    configure(WARNINGS_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())

    result = await workflow.ainvoke(create_review_state(pr_url=PR_102), _config("e2e-1"))

    assert result["phase"] == "done"
    assert "__interrupt__" not in result
    findings = result["all_findings"]
    assert len(findings) == 2
    assert {f.file_path for f in findings} == {"src/calculator.py"}
    # The LLM reports line numbers relative to the new content; findings must
    # be converted to absolute file lines (hunk starts at line 1 here).
    assert {f.line for f in findings} == {3, 8}


@pytest.mark.asyncio
async def test_graph_reviews_every_segment(monkeypatch):
    """Regression: the old ``len(segments) - 1`` check skipped the last segment."""
    configure(CRITICAL_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())

    result = await workflow.ainvoke(create_review_state(pr_url=PR_101), _config("e2e-2"))

    snapshot = await workflow.aget_state(_config("e2e-2"))
    findings = snapshot.values["all_findings"]
    assert len(findings) == 3
    assert {f.file_path for f in findings} == {
        "src/calculator.py",
        "src/config.py",
    }
    # The critical finding routes to the human gate instead of posting.
    assert "__interrupt__" in result


@pytest.mark.asyncio
async def test_graph_auto_fix_dry_run(monkeypatch):
    configure(WARNINGS_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())

    result = await workflow.ainvoke(
        create_review_state(pr_url=PR_102, auto_fix_enabled=True, dry_run=True),
        _config("e2e-3"),
    )

    assert result["fix_attempts"] == 1
    assert result["evaluation_results"], "self-evaluation should have run"
    assert result["approved_fixes"], "valid fixes should be approved"
    assert all(patch.commit_sha is None for patch in result["approved_fixes"])
    assert "Dry run" in result["review_summary"]
    assert "__interrupt__" not in result


@pytest.mark.asyncio
async def test_graph_resumes_after_interrupt(monkeypatch):
    """Human-in-the-loop: interrupt -> Command(resume) -> completed run."""
    configure(CRITICAL_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())
    config = _config("e2e-4")

    paused = await workflow.ainvoke(create_review_state(pr_url=PR_101), config)
    assert "__interrupt__" in paused
    payload = [getattr(item, "value", item) for item in paused["__interrupt__"]]
    assert payload[0]["findings"], "the human gate must show findings"
    severities = {f["severity"] for f in payload[0]["findings"]}
    assert "critical" in severities

    resumed = await workflow.ainvoke(
        Command(resume={"approved_fixes": [], "feedback": "reviewed"}),
        config,
    )
    assert resumed["phase"] == "done"
    assert resumed["human_feedback"] == "reviewed"


@pytest.mark.asyncio
async def test_second_run_uses_cache(monkeypatch):
    configure(WARNINGS_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())

    first = await workflow.ainvoke(create_review_state(pr_url=PR_102), _config("e2e-5a"))
    second = await workflow.ainvoke(create_review_state(pr_url=PR_102), _config("e2e-5b"))

    assert first["metadata"].cache_misses >= 1
    assert second["metadata"].cache_hits >= 1
    assert len(second["all_findings"]) == len(first["all_findings"])


@pytest.mark.asyncio
async def test_auto_fix_loop_is_bounded(monkeypatch):
    """Regression: auto-fix used to loop until GraphRecursionError."""
    configure(WARNINGS_FIXTURE, monkeypatch)
    workflow = compile_workflow(MemorySaver())

    result = await workflow.ainvoke(
        create_review_state(pr_url=PR_102, auto_fix_enabled=True, dry_run=True),
        _config("e2e-6"),
    )
    assert result["fix_attempts"] == 1
    assert result["phase"] == "done"
