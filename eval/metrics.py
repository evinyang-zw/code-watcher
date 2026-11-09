"""Metrics for the code-review evaluation.

Matching rule: a finding matches a gold comment when it targets the same file
and its line is within ``LINE_TOLERANCE`` of the comment line. Precision is
computed against human comments only, so an unmatched finding is *not
necessarily* wrong — it is simply not corroborated by the reviewer. The report
labels this limitation explicitly.

Proportions are reported with Wilson score intervals: at n≈100 the normal
approximation is optimistic, and the interval is what keeps "68% recall" from
being over-read.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from eval.schema import Finding, Instance

LINE_TOLERANCE = 3
WILSON_Z = 1.96


@dataclass
class InstanceResult:
    """Evaluation outcome for a single PR."""

    instance_id: str
    kind: str
    gold_count: int
    finding_count: int
    matched_gold: int
    matched_findings: int
    gold_by_category: dict[str, int] = field(default_factory=dict)
    matched_by_category: dict[str, int] = field(default_factory=dict)
    suggestion_total: int = 0
    suggestion_matched: int = 0
    unmatched_gold: list[dict[str, object]] = field(default_factory=list)
    unmatched_findings: list[dict[str, object]] = field(default_factory=list)
    error: str | None = None

    @property
    def is_clean(self) -> bool:
        return self.kind == "clean"

    def to_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "kind": self.kind,
            "gold_count": self.gold_count,
            "finding_count": self.finding_count,
            "matched_gold": self.matched_gold,
            "matched_findings": self.matched_findings,
            "gold_by_category": self.gold_by_category,
            "matched_by_category": self.matched_by_category,
            "suggestion_total": self.suggestion_total,
            "suggestion_matched": self.suggestion_matched,
            "unmatched_gold": self.unmatched_gold,
            "unmatched_findings": self.unmatched_findings,
            "error": self.error,
        }


def match_instance(
    instance: Instance, findings: Sequence[Finding], tolerance: int = LINE_TOLERANCE
) -> InstanceResult:
    """Greedy one-to-one matching between agent findings and human comments."""
    used_gold: set[int] = set()
    used_findings: set[int] = set()

    for finding_index, finding in enumerate(findings):
        for gold_index, gold in enumerate(instance.gold):
            if gold_index in used_gold:
                continue
            if finding.file != gold.path:
                continue
            if abs(finding.line - gold.line) > tolerance:
                continue
            used_gold.add(gold_index)
            used_findings.add(finding_index)
            break

    gold_by_category: dict[str, int] = {}
    for gold in instance.gold:
        gold_by_category[gold.category] = gold_by_category.get(gold.category, 0) + 1

    matched_by_category: dict[str, int] = {}
    for gold_index, gold in enumerate(instance.gold):
        if gold_index in used_gold:
            matched_by_category[gold.category] = matched_by_category.get(gold.category, 0) + 1

    suggestion_total = sum(1 for gold in instance.gold if gold.has_suggestion)
    suggestion_matched = sum(
        1
        for gold_index, gold in enumerate(instance.gold)
        if gold_index in used_gold and gold.has_suggestion
    )

    unmatched_gold = [
        {
            "path": gold.path,
            "line": gold.line,
            "category": gold.category,
            "body": gold.body[:160],
        }
        for gold_index, gold in enumerate(instance.gold)
        if gold_index not in used_gold
    ]
    unmatched_findings = [
        {
            "file": finding.file,
            "line": finding.line,
            "severity": finding.severity,
            "dimension": finding.dimension,
            "message": finding.message[:160],
        }
        for finding_index, finding in enumerate(findings)
        if finding_index not in used_findings
    ]

    return InstanceResult(
        instance_id=instance.id,
        kind=instance.kind,
        gold_count=len(instance.gold),
        finding_count=len(findings),
        matched_gold=len(used_gold),
        matched_findings=len(used_findings),
        gold_by_category=gold_by_category,
        matched_by_category=matched_by_category,
        suggestion_total=suggestion_total,
        suggestion_matched=suggestion_matched,
        unmatched_gold=unmatched_gold,
        unmatched_findings=unmatched_findings,
    )


def wilson_interval(successes: int, total: int, z: float = WILSON_Z) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


@dataclass
class Summary:
    """Aggregate metrics across the dataset."""

    instances: int
    bug_instances: int
    clean_instances: int
    gold_total: int
    findings_total: int
    matched_gold: int
    matched_findings: int
    clean_with_findings: int
    findings_per_bug_pr: float
    recall: float
    recall_ci: tuple[float, float]
    precision: float
    precision_ci: tuple[float, float]
    f1: float
    false_positive_rate: float
    fpr_ci: tuple[float, float]
    recall_by_category: dict[str, dict[str, float]]
    missed_by_category: dict[str, int]
    defect_matched: int = 0
    defect_total: int = 0
    defect_recall: float = 0.0
    defect_ci: tuple[float, float] = (0.0, 1.0)
    suggestion_matched: int = 0
    suggestion_total: int = 0
    suggestion_recall: float = 0.0
    suggestion_ci: tuple[float, float] = (0.0, 1.0)

    def to_dict(self) -> dict[str, object]:
        return {
            "instances": self.instances,
            "bug_instances": self.bug_instances,
            "clean_instances": self.clean_instances,
            "gold_total": self.gold_total,
            "findings_total": self.findings_total,
            "matched_gold": self.matched_gold,
            "matched_findings": self.matched_findings,
            "clean_with_findings": self.clean_with_findings,
            "findings_per_bug_pr": round(self.findings_per_bug_pr, 2),
            "recall": round(self.recall, 4),
            "recall_ci": [round(x, 4) for x in self.recall_ci],
            "precision": round(self.precision, 4),
            "precision_ci": [round(x, 4) for x in self.precision_ci],
            "f1": round(self.f1, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "fpr_ci": [round(x, 4) for x in self.fpr_ci],
            "recall_by_category": self.recall_by_category,
            "missed_by_category": self.missed_by_category,
            "defect_matched": self.defect_matched,
            "defect_total": self.defect_total,
            "defect_recall": round(self.defect_recall, 4),
            "defect_ci": [round(x, 4) for x in self.defect_ci],
            "suggestion_matched": self.suggestion_matched,
            "suggestion_total": self.suggestion_total,
            "suggestion_recall": round(self.suggestion_recall, 4),
            "suggestion_ci": [round(x, 4) for x in self.suggestion_ci],
        }


def summarize(results: Iterable[InstanceResult]) -> Summary:
    """Aggregate per-instance results into precision/recall/FPR with Wilson CIs."""
    results = list(results)
    bug = [r for r in results if not r.is_clean]
    clean = [r for r in results if r.is_clean]

    gold_total = sum(r.gold_count for r in bug)
    findings_total = sum(r.finding_count for r in bug)
    matched_gold = sum(r.matched_gold for r in bug)
    matched_findings = sum(r.matched_findings for r in bug)
    clean_with_findings = sum(1 for r in clean if r.finding_count > 0)

    recall = matched_gold / gold_total if gold_total else 0.0
    precision = matched_findings / findings_total if findings_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = clean_with_findings / len(clean) if clean else 0.0

    category_totals: dict[str, int] = {}
    category_matched: dict[str, int] = {}
    missed_by_category: dict[str, int] = {}
    for result in bug:
        for category, total in result.gold_by_category.items():
            category_totals[category] = category_totals.get(category, 0) + total
        for category, matched in result.matched_by_category.items():
            category_matched[category] = category_matched.get(category, 0) + matched
        for item in result.unmatched_gold:
            category = str(item.get("category", "other"))
            missed_by_category[category] = missed_by_category.get(category, 0) + 1

    recall_by_category = {
        category: {
            "matched": category_matched.get(category, 0),
            "total": total,
            "recall": round(category_matched.get(category, 0) / total, 4) if total else 0.0,
        }
        for category, total in sorted(category_totals.items())
    }

    defect_categories = {"bug", "security", "performance"}
    defect_matched = sum(
        matched for category, matched in category_matched.items() if category in defect_categories
    )
    defect_total = sum(
        total for category, total in category_totals.items() if category in defect_categories
    )
    defect_recall = defect_matched / defect_total if defect_total else 0.0

    suggestion_total = sum(r.suggestion_total for r in bug)
    suggestion_matched = sum(r.suggestion_matched for r in bug)
    suggestion_recall = suggestion_matched / suggestion_total if suggestion_total else 0.0

    return Summary(
        instances=len(results),
        bug_instances=len(bug),
        clean_instances=len(clean),
        gold_total=gold_total,
        findings_total=findings_total,
        matched_gold=matched_gold,
        matched_findings=matched_findings,
        clean_with_findings=clean_with_findings,
        findings_per_bug_pr=(findings_total / len(bug)) if bug else 0.0,
        recall=recall,
        recall_ci=wilson_interval(matched_gold, gold_total),
        precision=precision,
        precision_ci=wilson_interval(matched_findings, findings_total),
        f1=f1,
        false_positive_rate=fpr,
        fpr_ci=wilson_interval(clean_with_findings, len(clean)),
        recall_by_category=recall_by_category,
        missed_by_category=missed_by_category,
        defect_matched=defect_matched,
        defect_total=defect_total,
        defect_recall=defect_recall,
        defect_ci=wilson_interval(defect_matched, defect_total),
        suggestion_matched=suggestion_matched,
        suggestion_total=suggestion_total,
        suggestion_recall=suggestion_recall,
        suggestion_ci=wilson_interval(suggestion_matched, suggestion_total),
    )
