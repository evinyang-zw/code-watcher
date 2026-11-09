"""Unit tests for the review-evaluation metrics (no network, no LLM)."""

from __future__ import annotations

import pytest

from eval.guards import apply_guard
from eval.metrics import (
    match_instance,
    summarize,
    wilson_interval,
)
from eval.schema import Finding, GoldComment, Instance, infer_category, is_actionable_comment


def make_instance(gold: list[GoldComment], kind: str = "bug") -> Instance:
    return Instance(
        id=f"{kind}-1",
        repo="acme/demo",
        pr_number=1,
        title="fix: demo",
        kind=kind,  # type: ignore[arg-type]
        patch="",
        gold=gold,
    )


def finding(path: str, line: int) -> Finding:
    return Finding(file=path, line=line, severity="warning", dimension="correctness", message="x")


def test_matching_within_tolerance():
    instance = make_instance([GoldComment(path="a.py", line=10, body="bug here")])
    result = match_instance(instance, [finding("a.py", 12)])
    assert result.matched_gold == 1
    assert result.matched_findings == 1


def test_matching_outside_tolerance():
    instance = make_instance([GoldComment(path="a.py", line=10, body="bug here")])
    result = match_instance(instance, [finding("a.py", 20)])
    assert result.matched_gold == 0
    assert result.matched_findings == 0
    assert result.unmatched_gold and result.unmatched_findings


def test_matching_requires_same_file():
    instance = make_instance([GoldComment(path="a.py", line=10, body="bug here")])
    result = match_instance(instance, [finding("b.py", 10)])
    assert result.matched_gold == 0


def test_one_to_one_matching():
    instance = make_instance(
        [
            GoldComment(path="a.py", line=10, body="bug one"),
            GoldComment(path="a.py", line=40, body="bug two"),
        ]
    )
    result = match_instance(instance, [finding("a.py", 10), finding("a.py", 10)])
    assert result.matched_gold == 1
    assert result.matched_findings == 1


def test_summarize_two_instances():
    bug = make_instance(
        [
            GoldComment(path="a.py", line=10, body="bug", category="bug"),
            GoldComment(path="a.py", line=30, body="style", category="style"),
        ]
    )
    clean = make_instance([], kind="clean")
    results = [
        match_instance(bug, [finding("a.py", 11)]),
        match_instance(clean, []),
    ]
    summary = summarize(results)
    assert summary.instances == 2
    assert summary.bug_instances == 1
    assert summary.clean_instances == 1
    assert summary.gold_total == 2
    assert summary.findings_total == 1
    assert summary.matched_gold == 1
    assert summary.recall == pytest.approx(0.5)
    assert summary.precision == pytest.approx(1.0)
    assert summary.false_positive_rate == 0.0
    assert summary.recall_by_category["bug"]["matched"] == 1
    assert summary.missed_by_category["style"] == 1


def test_defect_recall_uses_category_subset():
    bug = make_instance(
        [
            GoldComment(path="a.py", line=10, body="crash here", category="bug"),
            GoldComment(path="a.py", line=30, body="rename this", category="style"),
        ]
    )
    result = match_instance(bug, [finding("a.py", 10)])
    summary = summarize([result])
    assert summary.defect_total == 1
    assert summary.defect_matched == 1
    assert summary.defect_recall == pytest.approx(1.0)


def test_suggestion_subset_recall():
    bug = make_instance(
        [
            GoldComment(path="a.py", line=5, body="```suggestion\nx = 1\n```", has_suggestion=True),
            GoldComment(path="a.py", line=40, body="please reorder", has_suggestion=False),
        ]
    )
    result = match_instance(bug, [finding("a.py", 5)])
    summary = summarize([result])
    assert summary.suggestion_total == 1
    assert summary.suggestion_matched == 1
    assert summary.suggestion_recall == pytest.approx(1.0)


def test_clean_pr_with_findings_counts_as_false_positive():
    clean_with_finding = make_instance([], kind="clean")
    result = match_instance(clean_with_finding, [finding("a.py", 1)])
    summary = summarize([result])
    assert summary.false_positive_rate == 1.0


def test_wilson_interval():
    low, high = wilson_interval(30, 50)
    assert 0.46 < low < 0.48
    assert 0.71 < high < 0.73
    assert wilson_interval(0, 0) == (0.0, 1.0)
    assert wilson_interval(0, 10)[0] == 0.0


def test_apply_guard_filters_dedupes_and_caps():
    findings = [
        Finding(file="a.py", line=1, severity="nit", dimension="style", message="n"),
        Finding(file="a.py", line=2, severity="warning", dimension="correctness", message="w"),
        Finding(file="a.py", line=2, severity="warning", dimension="correctness", message="dup"),
        Finding(file="b.py", line=9, severity="critical", dimension="security", message="c"),
    ]
    guarded = apply_guard(findings, min_severity="warning", max_findings=5)
    assert [f.severity for f in guarded] == ["warning", "critical"]

    capped = apply_guard(
        [
            Finding(file="a.py", line=i, severity="warning", dimension="correctness", message="x")
            for i in range(10)
        ],
        min_severity="warning",
        max_findings=3,
    )
    assert len(capped) == 3


def test_comment_filters():
    assert not is_actionable_comment("LGTM")
    assert not is_actionable_comment("thanks!")
    assert is_actionable_comment("This will raise KeyError when the cache is empty")
    assert infer_category("hard-coded credential") == "security"
    assert infer_category("this is slow for large n") == "performance"
    assert infer_category("wrong result on empty input") == "bug"
    assert infer_category("rename this variable") == "style"
    assert infer_category("consider extracting a helper") == "other"
