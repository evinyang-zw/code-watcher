"""Re-score an existing eval run with a review-comment guard (no LLM calls).

The raw findings are stored in ``eval/results/<run_id>.jsonl``; this module
applies a publishing policy (severity threshold, dedupe, per-PR cap) and writes
an additional summary + report section, so the "false-positive reduction" story
does not require paying for a second evaluation run.

Usage::

    python -m eval.rescore --run-id real-2026-11-09 --min-severity warning --max-findings 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.collect import load
from eval.guards import apply_guard
from eval.metrics import InstanceResult, match_instance, summarize
from eval.schema import Finding


def _load_results(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def rescore(
    run_id: str,
    dataset_path: Path,
    results_dir: Path,
    *,
    min_severity: str = "warning",
    max_findings: int = 5,
) -> dict[str, Any]:
    dataset = {instance.id: instance for instance in load(dataset_path)}
    rows = _load_results(results_dir / f"{run_id}.jsonl")

    results: list[InstanceResult] = []
    for row in rows:
        instance = dataset.get(row["instance_id"])
        if instance is None:
            continue
        raw_findings = [
            Finding(
                file=item["file"],
                line=item["line"],
                severity=item["severity"],
                dimension=item["dimension"],
                message=item["message"],
            )
            for item in row.get("findings", [])
        ]
        guarded = apply_guard(raw_findings, min_severity=min_severity, max_findings=max_findings)
        record = match_instance(instance, guarded)
        record.error = row.get("error")
        results.append(record)

    summary = summarize(results)
    payload = {
        "run_id": f"{run_id}-guarded",
        "base_run_id": run_id,
        "dataset": str(dataset_path),
        "guard": {"min_severity": min_severity, "max_findings": max_findings},
        "summary": summary.to_dict(),
    }
    out = results_dir / f"{run_id}-guarded-summary.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    guarded_rows = [
        {
            "instance_id": result.instance_id,
            "kind": result.kind,
            "result": result.to_dict(),
        }
        for result in results
    ]
    with (results_dir / f"{run_id}-guarded.jsonl").open("w", encoding="utf-8") as fh:
        for row in guarded_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-score a run with comment guards")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dataset", default="eval/data/gold_review.jsonl")
    parser.add_argument("--results-dir", default="eval/results")
    parser.add_argument("--min-severity", default="warning")
    parser.add_argument("--max-findings", type=int, default=5)
    args = parser.parse_args(argv)

    payload = rescore(
        args.run_id,
        Path(args.dataset),
        Path(args.results_dir),
        min_severity=args.min_severity,
        max_findings=args.max_findings,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
