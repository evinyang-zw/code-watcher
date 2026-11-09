"""Code Watcher CLI — review a GitHub PR with a stateful LangGraph workflow.

Examples
--------
Real PR (needs ``GITHUB_TOKEN`` + an LLM key)::

    python -m src.main https://github.com/owner/repo/pull/123

Offline demo (no token, no LLM key, no network)::

    python -m src.main --offline https://github.com/acme/demo/pull/101

Auto-fix is dry-run by default; ``--apply`` is required to push commits.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv
from langgraph.types import Command

from src.graph.state import create_review_state
from src.graph.workflow import compile_workflow

logger = logging.getLogger(__name__)

PR_URL_RE = re.compile(r"https?://github\.com/[^/]+/[^/]+/pull/\d+")
DEFAULT_FIXTURE = "fixtures/pr-101"


def _configure_offline(fixture_dir: str | None) -> str:
    """Point the process at fixtures instead of GitHub and a real LLM."""
    fixture = fixture_dir or os.environ.get("CODEWATCHER_FIXTURE_DIR") or DEFAULT_FIXTURE
    os.environ["CODEWATCHER_GITHUB"] = "fake"
    os.environ["CODEWATCHER_FIXTURE_DIR"] = fixture
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ.setdefault("MOCK_LLM_FIXTURE", os.path.join(fixture, "mock_llm.json"))
    os.environ.setdefault("GITHUB_TOKEN", "offline-demo")
    return fixture


def _interrupt_payload(result: dict[str, Any]) -> list[Any]:
    """Turn LangGraph ``Interrupt`` objects into JSON-serializable values."""
    return [getattr(item, "value", item) for item in result.get("__interrupt__", [])]


def _approved_ids(payload: list[Any]) -> list[str]:
    return [
        fix["finding_id"]
        for gate in payload
        if isinstance(gate, dict)
        for fix in gate.get("proposed_fixes", [])
    ]


def _confidence(result: dict[str, Any]) -> tuple[float, str]:
    """Overall confidence: mean of fix self-evaluations, else 'not evaluated'."""
    evaluations = result.get("evaluation_results") or []
    if evaluations:
        scores = [e.confidence_score for e in evaluations]
        return sum(scores) / len(scores), "mean fix self-evaluation"
    return 0.0, "not evaluated (no fix generated)"


def _summarize(result: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    findings = result.get("all_findings") or []
    confidence, confidence_basis = _confidence(result)
    return {
        "phase": result.get("phase", "unknown"),
        "offline": offline,
        "findings": [
            {
                "file": f.file_path,
                "line": f.line,
                "severity": f.severity,
                "dimension": f.dimension,
                "message": f.message,
            }
            for f in findings
        ],
        "finding_count": len(findings),
        "critical_count": sum(1 for f in findings if f.severity == "critical"),
        "overall_confidence": round(confidence, 2),
        "confidence_basis": confidence_basis,
        "auto_fix_enabled": bool(result.get("auto_fix_enabled")),
        "dry_run": bool(result.get("dry_run", True)),
        "applied_commits": [
            patch.commit_sha for patch in (result.get("approved_fixes") or []) if patch.commit_sha
        ],
        "review_summary": result.get("review_summary", ""),
        "error": result.get("error"),
    }


def _print_summary(summary: dict[str, Any], *, offline: bool) -> None:
    print("\n=== Code Watcher review ===")
    if offline:
        print("(offline mode: fixture PR + mock LLM)")
    print(
        f"phase: {summary['phase']}  findings: {summary['finding_count']}  "
        f"critical: {summary['critical_count']}"
    )
    for finding in summary["findings"]:
        print(
            f"  [{finding['severity']:<9}] {finding['file']}:{finding['line']} "
            f"({finding['dimension']}) {finding['message'][:100]}"
        )
    print(
        f"overall confidence: {summary['overall_confidence']:.2f} ({summary['confidence_basis']})"
    )
    if summary["auto_fix_enabled"]:
        mode = "dry-run" if summary["dry_run"] else "apply"
        print(f"auto-fix: enabled ({mode}), commits: {summary['applied_commits'] or 'none'}")
    if summary["error"]:
        print(f"error: {summary['error']}")
    print("===========================\n")


async def _run(
    workflow: Any,
    config: dict[str, Any],
    *,
    auto_fix: bool,
    apply_fixes: bool,
    offline: bool,
    resume: bool,
    json_out: str | None,
) -> dict[str, Any] | None:
    """Resume a checkpoint if asked, otherwise start the workflow and report."""
    pr_url = config["configurable"]["thread_id"].removeprefix("pr-")

    # Cross-process resume: a persisted checkpoint may already be paused.
    if resume:
        try:
            snapshot = await workflow.aget_state(config)
            pending = [item for task in snapshot.tasks for item in getattr(task, "interrupts", ())]
        except Exception as exc:  # no checkpoint backend / no state yet
            logger.debug("No resumable state found: %s", exc)
            pending = []
        if pending:
            payload = [getattr(item, "value", item) for item in pending]
            print("Resuming paused run from checkpoint...")
            print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
            approved = _approved_ids(payload)
            try:
                result = await workflow.ainvoke(
                    Command(resume={"approved_fixes": approved, "feedback": "resumed"}),
                    config,
                )
            except Exception as exc:
                print(f"Error: resume failed: {exc}", file=sys.stderr)
                return None
            summary = _summarize(result, offline=offline)
            _print_summary(summary, offline=offline)
            if json_out:
                with open(json_out, "w", encoding="utf-8") as fh:
                    json.dump(summary, fh, indent=2, ensure_ascii=False)
            return result

    state = create_review_state(
        pr_url=pr_url,
        auto_fix_enabled=auto_fix,
        dry_run=not apply_fixes,
    )
    try:
        result = await workflow.ainvoke(state, config)
    except Exception as exc:
        logger.error("Workflow failed: %s", exc)
        print(f"Error: Review workflow failed: {exc}", file=sys.stderr)
        return None

    if "__interrupt__" in result:
        payload = _interrupt_payload(result)
        print("Graph interrupted for human review.")
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        if not resume:
            _print_summary(_summarize(result, offline=offline), offline=offline)
            print("Approve and continue with --resume.")
            return result
        approved = _approved_ids(payload)
        print(f"--resume: approving {len(approved)} proposed fix(es)")
        result = await workflow.ainvoke(
            Command(
                resume={
                    "approved_fixes": approved,
                    "feedback": "approved via --resume",
                }
            ),
            config,
        )

    summary = _summarize(result, offline=offline)
    _print_summary(summary, offline=offline)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
        print(f"summary written to {json_out}")
    return result


async def review_pull_request(
    pr_url: str,
    auto_fix: bool = False,
    apply_fixes: bool = False,
    offline: bool = False,
    fixture_dir: str | None = None,
    resume: bool = False,
    persist: str | None = None,
    json_out: str | None = None,
) -> dict[str, Any] | None:
    """Run the Code Watcher review workflow on a GitHub PR."""
    if not PR_URL_RE.match(pr_url):
        print(f"Error: Invalid GitHub PR URL: {pr_url}", file=sys.stderr)
        print("Expected format: https://github.com/owner/repo/pull/123", file=sys.stderr)
        return None

    if offline:
        _configure_offline(fixture_dir)

    config = {
        "configurable": {"thread_id": f"pr-{pr_url}"},
        "recursion_limit": 50,
    }

    if persist:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        os.makedirs(os.path.dirname(persist) or ".", exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(persist) as saver:
            workflow = compile_workflow(checkpointer=saver)
            return await _run(
                workflow,
                config,
                auto_fix=auto_fix,
                apply_fixes=apply_fixes,
                offline=offline,
                resume=resume,
                json_out=json_out,
            )

    workflow = compile_workflow()
    return await _run(
        workflow,
        config,
        auto_fix=auto_fix,
        apply_fixes=apply_fixes,
        offline=offline,
        resume=resume,
        json_out=json_out,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Code Watcher - automated code review agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Auto-fix is dry-run by default; pass --apply to push commits.",
    )
    parser.add_argument("pr_url", help="GitHub PR URL")
    parser.add_argument("--auto-fix", action="store_true", help="Generate and self-evaluate fixes")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually push fixes (requires --auto-fix; default is dry-run)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run against a local fixture PR with a mock LLM (no token, no network)",
    )
    parser.add_argument(
        "--fixture-dir",
        default=None,
        help=f"Fixture directory for --offline (default: {DEFAULT_FIXTURE})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Approve and resume a run that paused for human review",
    )
    parser.add_argument(
        "--persist",
        default=None,
        help="Persist checkpoints to this SQLite file (enables cross-process resume)",
    )
    parser.add_argument("--json-out", default=None, help="Write the review summary as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    if args.apply and not args.auto_fix:
        print("Error: --apply requires --auto-fix", file=sys.stderr)
        return 2

    result = asyncio.run(
        review_pull_request(
            args.pr_url,
            auto_fix=args.auto_fix,
            apply_fixes=args.apply,
            offline=args.offline,
            fixture_dir=args.fixture_dir,
            resume=args.resume,
            persist=args.persist,
            json_out=args.json_out,
        )
    )
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
