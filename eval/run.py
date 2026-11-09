"""Run the Code Watcher review agent over a gold set and score it.

Each instance is served to the workflow through the offline fake GitHub client
(the PR diff comes from the dataset), while the LLM comes from the configured
real provider. Findings are matched against human review comments.

Usage::

    LLM_PROVIDER=deepseek LLM_MODEL=deepseek-flash \
    LLM_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=sk-... \
    python -m eval.run --dataset eval/data/gold_review.jsonl --limit 5

The full run writes ``eval/results/<run_id>.jsonl`` and
``eval/results/<run_id>-summary.json``; ``python -m eval.report`` renders the
markdown report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from eval.collect import load
from eval.metrics import InstanceResult, match_instance, summarize
from eval.schema import Finding, Instance
from src.cache.review_cache import get_cache
from src.graph.state import create_review_state
from src.graph.workflow import compile_workflow


def _mock_llm_payload(instance: Instance) -> dict[str, Any]:
    """Deterministic mock responses so the eval pipeline can smoke-test offline.

    Only used when ``LLM_PROVIDER=mock`` (never for a reported run): every
    changed Python file gets one finding on its first line.
    """
    paths = re.findall(r"^\+\+\+ b/(.+)$", instance.patch, re.MULTILINE)
    review = {
        path: [
            {
                "severity": "warning",
                "dimension": "correctness",
                "line": 1,
                "message": "mock finding for pipeline smoke test",
                "suggested_fix": None,
            }
        ]
        for path in paths
        if path.endswith(".py")
    }
    return {
        "review": review,
        "default": "mock",
        "fix": "",
        "self_evaluate": "confidence: 0.8",
    }


def _write_fixture(directory: Path, instance: Instance) -> None:
    """Materialize an instance as an offline fixture PR."""
    meta = {
        "number": instance.pr_number,
        "title": instance.title,
        "state": "closed",
        "user": {"login": "eval"},
        "head": {"sha": f"eval-head-{instance.pr_number}", "ref": "eval"},
        "base": {"sha": f"eval-base-{instance.pr_number}", "ref": "main"},
        "html_url": instance.url or instance.pr_url,
    }
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (directory / "diff.patch").write_text(instance.patch, encoding="utf-8")
    (directory / "files_at_head.json").write_text("{}", encoding="utf-8")
    if os.environ.get("LLM_PROVIDER", "").lower() == "mock":
        (directory / "mock_llm.json").write_text(
            json.dumps(_mock_llm_payload(instance)), encoding="utf-8"
        )
        os.environ["MOCK_LLM_FIXTURE"] = str(directory / "mock_llm.json")


async def run_instance(instance: Instance) -> tuple[list[Finding], str | None]:
    """Review one PR instance and return its findings."""
    with tempfile.TemporaryDirectory(prefix="cw-eval-") as tmp:
        fixture_dir = Path(tmp)
        _write_fixture(fixture_dir, instance)

        os.environ["CODEWATCHER_GITHUB"] = "fake"
        os.environ["CODEWATCHER_FIXTURE_DIR"] = str(fixture_dir)
        get_cache().clear()

        workflow = compile_workflow(MemorySaver())
        config = {
            "configurable": {"thread_id": f"eval-{instance.id}"},
            "recursion_limit": 50,
        }
        error: str | None = None
        try:
            await workflow.ainvoke(create_review_state(pr_url=instance.pr_url), config)
        except Exception as exc:  # network/LLM failure: keep the instance in the report
            error = str(exc)

        snapshot = await workflow.aget_state(config)
        values: dict[str, Any] = dict(snapshot.values or {})
        findings = [
            Finding(
                file=f.file_path,
                line=f.line,
                severity=f.severity,
                dimension=f.dimension,
                message=f.message,
            )
            for f in (values.get("all_findings") or [])
        ]
        return findings, error


async def evaluate(
    dataset: list[Instance], limit: int | None = None, verbose: bool = True
) -> tuple[list[InstanceResult], list[dict[str, Any]]]:
    results: list[InstanceResult] = []
    raw: list[dict[str, Any]] = []
    selected = dataset[:limit] if limit else dataset

    for index, instance in enumerate(selected, start=1):
        started = time.monotonic()
        findings, error = await run_instance(instance)
        duration = time.monotonic() - started
        result = match_instance(instance, findings)
        result.error = error
        results.append(result)
        raw.append(
            {
                "instance_id": instance.id,
                "kind": instance.kind,
                "repo": instance.repo,
                "pr": instance.pr_number,
                "title": instance.title,
                "duration_s": round(duration, 1),
                "findings": [finding.to_dict() for finding in findings],
                "result": result.to_dict(),
                "error": error,
            }
        )
        if verbose:
            print(
                f"[{index}/{len(selected)}] {instance.id:<28} "
                f"gold={len(instance.gold)} findings={len(findings)} "
                f"matched={result.matched_gold}/{result.matched_findings}"
                f"{' ERROR=' + error if error else ''}",
                file=sys.stderr,
            )
    return results, raw


def run_id_from_env(prefix: str = "run") -> str:
    return os.environ.get("EVAL_RUN_ID") or f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Code Watcher on a gold set")
    parser.add_argument("--dataset", default="eval/data/gold_review.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N")
    parser.add_argument("--out-dir", default="eval/results")
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Allow LLM_PROVIDER=mock (pipeline smoke test only, not a valid score)",
    )
    args = parser.parse_args(argv)

    if not os.environ.get("LLM_PROVIDER"):
        print(
            "LLM_PROVIDER is not set. Configure a real provider "
            "(e.g. deepseek/openai/anthropic) before running eval.",
            file=sys.stderr,
        )
        return 2
    if os.environ.get("LLM_PROVIDER", "").lower() == "mock" and not args.allow_mock:
        print(
            "Refusing to evaluate with LLM_PROVIDER=mock "
            "(pass --allow-mock for a pipeline smoke test only)",
            file=sys.stderr,
        )
        return 2

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(
            f"Dataset not found: {dataset_path}. Run `python -m eval.collect` first.",
            file=sys.stderr,
        )
        return 2

    run_id = args.run_id or run_id_from_env()
    dataset = load(dataset_path)
    print(
        f"Evaluating {len(dataset)} instances with LLM_PROVIDER="
        f"{os.environ['LLM_PROVIDER']} run_id={run_id}",
        file=sys.stderr,
    )

    results, raw = asyncio.run(evaluate(dataset, limit=args.limit))
    summary = summarize(results)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{run_id}.jsonl").open("w", encoding="utf-8") as fh:
        for row in raw:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out_dir / f"{run_id}-summary.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "run_id": run_id,
                "dataset": str(dataset_path),
                "provider": os.environ.get("LLM_PROVIDER"),
                "model": os.environ.get("LLM_MODEL", ""),
                "summary": summary.to_dict(),
            },
            fh,
            indent=2,
            ensure_ascii=False,
        )

    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    print(f"\nresults: {out_dir / (run_id + '.jsonl')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
