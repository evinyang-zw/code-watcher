"""Render the markdown evaluation report from an eval run.

Usage::

    python -m eval.report                    # latest run in eval/results/
    python -m eval.report --run-id run-... --out eval/report.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ci(interval: list[float] | tuple[float, float]) -> str:
    low, high = interval
    return f"[{low * 100:.1f}, {high * 100:.1f}]"


def _latest_summary(results_dir: Path) -> Path:
    candidates = sorted(results_dir.glob("*-summary.json"))
    if not candidates:
        raise SystemExit(f"no summary files in {results_dir}; run eval.run first")
    return candidates[-1]


def render(summary_path: Path, results_path: Path | None) -> str:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    summary: dict[str, Any] = payload["summary"]

    smoke = str(payload.get("provider", "")).lower() == "mock"
    lines = [
        "# Code Watcher · Review benchmark",
        "",
        "> **SMOKE TEST (mock LLM) — not a valid score.** "
        "This report only proves the pipeline runs end to end."
        if smoke
        else "",
        "",
        f"- run_id: `{payload.get('run_id', '')}`",
        f"- dataset: `{payload.get('dataset', '')}`",
        f"- provider: `{payload.get('provider', '')}` / model: `{payload.get('model', '') or 'n/a'}`",
        f"- instances: {summary['instances']} "
        f"({summary['bug_instances']} bug-fix PRs + {summary['clean_instances']} clean PRs)",
        "",
        "## Headline",
        "",
        "| Metric | Value | 95% CI (Wilson) | n |",
        "|---|---|---|---|",
        f"| Recall (human comments found) | {_pct(summary['recall'])} | {_ci(summary['recall_ci'])} "
        f"| {summary['matched_gold']}/{summary['gold_total']} |",
        f"| Precision (findings matching a comment) | {_pct(summary['precision'])} "
        f"| {_ci(summary['precision_ci'])} | {summary['matched_findings']}/{summary['findings_total']} |",
        f"| Recall on defect-like comments (bug/security/performance) "
        f"| {_pct(summary.get('defect_recall', 0.0))} "
        f"| {_ci(summary.get('defect_ci', [0, 1]))} "
        f"| {summary.get('defect_matched', 0)}/{summary.get('defect_total', 0)} |",
        f"| F1 | {summary['f1']:.3f} | — | — |",
        f"| False-positive rate (clean PRs) | {_pct(summary['false_positive_rate'])} "
        f"| {_ci(summary['fpr_ci'])} | {summary['clean_with_findings']}/{summary['clean_instances']} |",
        f"| Findings per bug-fix PR | {summary['findings_per_bug_pr']:.2f} | — "
        f"| {summary['findings_total']} findings |",
        "",
        "> Precision is measured against human review comments only: an unmatched "
        "finding is not necessarily wrong, just not corroborated by the reviewer.",
        "",
        "## Recall by human-comment category",
        "",
        "| Category | Recall | Matched / total |",
        "|---|---|---|",
    ]
    for category, values in summary.get("recall_by_category", {}).items():
        lines.append(
            f"| {category} | {_pct(values['recall'])} | {values['matched']}/{values['total']} |"
        )

    lines += [
        "",
        "## Failure taxonomy (missed human comments)",
        "",
        "| Category | Missed |",
        "|---|---|",
    ]
    missed = summary.get("missed_by_category", {})
    if missed:
        for category, count in sorted(missed.items(), key=lambda item: -item[1]):
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("| — | 0 |")

    if results_path and results_path.exists():
        rows = [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lines += [
            "",
            "## Per-instance results",
            "",
            "| Instance | Kind | Gold | Findings | Matched gold | Error |",
            "|---|---|---|---|---|---|",
        ]
        for row in rows:
            result = row["result"]
            lines.append(
                f"| {row['instance_id']} | {row['kind']} | {result['gold_count']} "
                f"| {result['finding_count']} | {result['matched_gold']} "
                f"| {row.get('error') or ''} |"
            )

        lines += ["", "## Sample misses (human comments the agent did not cover)", ""]
        count = 0
        for row in rows:
            for item in row["result"].get("unmatched_gold", [])[:2]:
                lines.append(
                    f"- `{row['instance_id']}` {item['path']}:{item['line']} "
                    f"({item['category']}) — {item['body'][:120]}"
                )
                count += 1
                if count >= 10:
                    break
            if count >= 10:
                break

        lines += ["", "## Sample unmatched findings (not corroborated)", ""]
        count = 0
        for row in rows:
            for item in row["result"].get("unmatched_findings", [])[:2]:
                lines.append(
                    f"- `{row['instance_id']}` {item['file']}:{item['line']} "
                    f"[{item['severity']}] {item['message'][:120]}"
                )
                count += 1
                if count >= 10:
                    break
            if count >= 10:
                break

    lines += [
        "",
        "## Limitations",
        "",
        "- Gold = human inline review comments; praise/approval comments are filtered out heuristically, "
        "so both the gold set and the categories carry labeling noise.",
        "- Matching uses file + line tolerance (±3); a correct finding on a different line counts as a miss.",
        "- Unmatched findings may still be valid issues the reviewer did not comment on (precision is a lower bound).",
        "- Single reviewer, single run, one model: use the CIs, not the point estimates, for comparisons.",
        "- This is a self-built review benchmark; it is **not** SWE-bench and its numbers are not comparable to leaderboards.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the eval markdown report")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--results-dir", default="eval/results")
    parser.add_argument("--out", default="eval/report.md")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    if args.run_id:
        summary_path = results_dir / f"{args.run_id}-summary.json"
        results_path: Path | None = results_dir / f"{args.run_id}.jsonl"
    else:
        summary_path = _latest_summary(results_dir)
        run_id = summary_path.name.removesuffix("-summary.json")
        results_path = results_dir / f"{run_id}.jsonl"

    if not summary_path.exists():
        raise SystemExit(f"summary not found: {summary_path}")

    markdown = render(summary_path, results_path)
    Path(args.out).write_text(markdown, encoding="utf-8")
    print(f"report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
