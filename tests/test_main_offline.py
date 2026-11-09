"""End-to-end CLI tests for the offline demo (no token, no network, no LLM)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PR_101 = "https://github.com/acme/demo/pull/101"
PR_102 = "https://github.com/acme/demo/pull/102"


def _run(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    # Never let a developer's real token leak into the offline demo.
    env.pop("GITHUB_TOKEN", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-m", "src.main", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_offline_cli_halts_on_critical_finding():
    result = _run("--offline", PR_101)
    assert result.returncode == 0, result.stderr
    assert "Graph interrupted for human review" in result.stdout
    # Both files must be reviewed, and the critical finding must be shown.
    assert "src/calculator.py:3" in result.stdout
    assert "src/config.py:3" in result.stdout
    assert "critical" in result.stdout


def test_offline_cli_auto_fix_dry_run_writes_json(tmp_path):
    out = tmp_path / "summary.json"
    result = _run(
        "--offline",
        "--fixture-dir",
        "fixtures/pr-102",
        "--auto-fix",
        "--json-out",
        str(out),
        PR_102,
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run" in result.stdout

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["offline"] is True
    assert summary["finding_count"] == 2
    assert summary["dry_run"] is True
    assert summary["applied_commits"] == []
    assert summary["overall_confidence"] >= 0.7


def test_apply_requires_auto_fix():
    result = _run("--offline", "--apply", PR_102)
    assert result.returncode == 2
    assert "--apply requires --auto-fix" in result.stderr


def test_persisted_run_resumes_in_a_second_process(tmp_path):
    """SQLite checkpoint: process 1 pauses, process 2 resumes and completes."""
    db = tmp_path / "checkpoints.sqlite"
    first = _run("--offline", "--persist", str(db), PR_101)
    assert first.returncode == 0, first.stderr
    assert "Graph interrupted for human review" in first.stdout

    second = _run("--offline", "--persist", str(db), "--resume", PR_101)
    assert second.returncode == 0, second.stderr
    assert "Resuming paused run from checkpoint" in second.stdout
    assert "phase: done" in second.stdout
