from __future__ import annotations

from src.evaluation.performance_analyzer import analyze_code, compute_performance_score
from src.evaluation.scorer import compute_confidence, compute_quality_score
from src.evaluation.security_scanner import scan_code
from src.schema.types import EvaluationResult, FixPatch, ReviewFinding


def _make_finding(severity: str = "warning") -> ReviewFinding:
    return ReviewFinding(
        file_path="a.py",
        line=1,
        severity=severity,
        dimension="style",
        message="test issue",
    )


def test_scan_code_clean():
    code = "print('hello')"
    findings = scan_code(code)
    assert len(findings) == 0


def test_scan_code_sql_injection():
    code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
    findings = scan_code(code)
    assert len(findings) >= 1
    assert any("sql_injection" in f for f in findings)


def test_scan_code_eval():
    code = "result = eval(user_input)"
    findings = scan_code(code)
    assert len(findings) >= 1
    assert any("eval_usage" in f for f in findings)


def test_analyze_code_clean():
    code = "x = 1"
    issues = analyze_code(code)
    assert len(issues) == 0


def test_analyze_code_nested_loop():
    code = "for i in range(10):\n    for j in range(10):\n        pass"
    issues = analyze_code(code)
    assert len(issues) >= 1


def test_compute_performance_score_clean():
    score = compute_performance_score("x = 1")
    assert score == 1.0


def test_compute_performance_score_issues():
    code = "for i in range(10):\n    for j in range(10):\n        pass"
    score = compute_performance_score(code)
    assert score < 1.0


def test_compute_quality_score_no_findings():
    score = compute_quality_score([])
    assert score == 1.0


def test_compute_quality_score_critical():
    finding = _make_finding("critical")
    score = compute_quality_score([finding])
    assert score < 0.7


def test_compute_quality_score_nit():
    finding = _make_finding("nit")
    score = compute_quality_score([finding])
    assert score > 0.9


def test_compute_confidence_syntax_fail():
    evaluation = EvaluationResult(
        patch=FixPatch(finding=_make_finding(), patch_diff="", description="test"),
        syntax_valid=False,
    )
    score = compute_confidence(evaluation, "warning")
    assert score == 0.0


def test_compute_confidence_all_pass():
    evaluation = EvaluationResult(
        patch=FixPatch(finding=_make_finding(), patch_diff="", description="test"),
        syntax_valid=True,
        tests_pass=True,
        lint_clean=True,
        security_clean=True,
        performance_score=1.0,
    )
    score = compute_confidence(evaluation, "warning")
    assert score > 0.7


def test_compute_confidence_critical_penalty():
    evaluation = EvaluationResult(
        patch=FixPatch(finding=_make_finding(), patch_diff="", description="test"),
        syntax_valid=True,
        tests_pass=True,
        lint_clean=True,
        security_clean=True,
        performance_score=1.0,
    )
    score_warning = compute_confidence(evaluation, "warning")
    score_critical = compute_confidence(evaluation, "critical")
    assert score_critical < score_warning
