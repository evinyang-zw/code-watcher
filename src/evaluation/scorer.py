from __future__ import annotations

from src.evaluation.performance_analyzer import compute_performance_score
from src.evaluation.security_scanner import scan_code
from src.schema.types import EvaluationResult, FixPatch, ReviewFinding


def compute_quality_score(findings: list[ReviewFinding]) -> float:
    """Compute code quality score (0.0-1.0) based on findings."""
    if not findings:
        return 1.0

    severity_weights = {
        "critical": 0.4,
        "warning": 0.2,
        "suggestion": 0.05,
        "nit": 0.01,
    }
    penalty = sum(severity_weights.get(f.severity, 0) for f in findings)
    return max(0.0, 1.0 - penalty)


def compute_confidence(
    evaluation: EvaluationResult,
    finding_severity: str,
    llm_assessment_score: float = 0.8,
) -> float:
    """
    Weighted confidence score:
    - syntax_valid:  0.20 (hard gate — if false, score is 0)
    - tests_pass:    0.25 (strongest signal)
    - lint_clean:    0.10
    - security:      0.15
    - performance:   0.10
    - llm_assessment: 0.20
    """
    if not evaluation.syntax_valid:
        return 0.0

    test_score = 1.0 if evaluation.tests_pass else (0.5 if evaluation.tests_pass is None else 0.0)
    lint_score = 1.0 if evaluation.lint_clean else 0.3
    security_score = 1.0 if evaluation.security_clean else 0.2
    perf_score = evaluation.performance_score

    score = (
        0.20 * 1.0  # syntax
        + 0.25 * test_score
        + 0.10 * lint_score
        + 0.15 * security_score
        + 0.10 * perf_score
        + 0.20 * llm_assessment_score
    )

    # Critical findings require higher confidence to auto-fix
    if finding_severity == "critical":
        score *= 0.8

    return round(min(score, 1.0), 3)


def evaluate_fix(
    patch: FixPatch,
    original_code: str,
    patched_code: str,
    syntax_valid: bool,
    tests_pass: bool | None,
    lint_clean: bool,
) -> EvaluationResult:
    """Evaluate a fix and return an EvaluationResult."""
    pre_score = compute_quality_score([patch.finding])
    security_issues = scan_code(patched_code)
    post_score = max(0.0, 1.0 - len(security_issues) * 0.15)
    quality_delta = post_score - pre_score
    perf_score = compute_performance_score(patched_code)

    evaluation = EvaluationResult(
        patch=patch,
        syntax_valid=syntax_valid,
        tests_pass=tests_pass,
        lint_clean=lint_clean,
        security_clean=len(security_issues) == 0,
        security_findings=security_issues,
        performance_score=perf_score,
        pre_fix_quality_score=pre_score,
        post_fix_quality_score=post_score,
        quality_delta=quality_delta,
    )

    evaluation.confidence_score = compute_confidence(
        evaluation, patch.finding.severity
    )
    return evaluation
