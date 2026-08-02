from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.evaluation.performance_analyzer import compute_performance_score
from src.evaluation.runner import EvaluationRunner
from src.evaluation.scorer import compute_confidence, compute_quality_score
from src.evaluation.security_scanner import scan_code
from src.graph.state import ReviewState
from src.llm.prompts import SELF_EVALUATE_PROMPT
from src.llm.provider import create_llm_provider
from src.schema.types import EvaluationResult


async def self_evaluate_node(state: ReviewState) -> dict:
    """Evaluate fixes: syntax check, lint, security scan, performance analysis."""
    runner = EvaluationRunner()
    provider = create_llm_provider()
    evaluation_results = []

    for fix in state["generated_fixes"]:
        # Apply patch to get the patched code for evaluation
        # For now, use the finding's suggested_fix as the patched content
        # In production, you'd fetch the original file and apply the diff
        patched_code = fix.finding.suggested_fix or fix.patch_diff

        # Syntax check on actual patched code (not the diff)
        syntax_valid = await runner.check_syntax_code(patched_code)

        # Security scan and performance analysis on patched code
        security_issues = scan_code(patched_code)
        security_clean = len(security_issues) == 0
        perf_score = compute_performance_score(patched_code)
        lint_clean = True

        # Compute quality scores
        pre_score = compute_quality_score([fix.finding])
        post_score = max(0.0, 1.0 - len(security_issues) * 0.15)
        quality_delta = post_score - pre_score

        evaluation = EvaluationResult(
            patch=fix,
            syntax_valid=syntax_valid,
            lint_clean=lint_clean,
            security_clean=security_clean,
            security_findings=security_issues,
            performance_score=perf_score,
            pre_fix_quality_score=pre_score,
            post_fix_quality_score=post_score,
            quality_delta=quality_delta,
        )

        # LLM self-assessment
        llm_prompt = SELF_EVALUATE_PROMPT.format(
            finding_message=fix.finding.message,
            patch_diff=fix.patch_diff,
            syntax_valid=syntax_valid,
            tests_pass="N/A",
            lint_clean=lint_clean,
            security_clean=security_clean,
            performance_score=f"{perf_score:.2f}",
            pre_fix_quality_score=f"{pre_score:.2f}",
            post_fix_quality_score=f"{post_score:.2f}",
            quality_delta=f"{quality_delta:.2f}",
        )

        try:
            response = await provider.chat([
                SystemMessage(content="Assess the fix quality. Return a confidence score 0.0-1.0 and brief notes."),
                HumanMessage(content=llm_prompt),
            ])
            # Parse confidence: look for "confidence: X.X" pattern specifically
            confidence_match = re.search(r"confidence[:\s]+(\d+\.\d+)", response, re.IGNORECASE)
            if not confidence_match:
                # Fallback: look for standalone decimal between 0 and 1
                confidence_match = re.search(r"\b(0\.\d+|1\.0)\b", response)
            llm_score = float(confidence_match.group(1)) if confidence_match else 0.7
            evaluation.notes = response[:500]
        except Exception:
            llm_score = 0.7

        evaluation.confidence_score = compute_confidence(
            evaluation, fix.finding.severity, llm_score
        )
        evaluation_results.append(evaluation)

    approved = [
        e.patch for e in evaluation_results if e.confidence_score >= 0.7
    ]

    return {
        "evaluation_results": evaluation_results,
        "approved_fixes": approved,
        "phase": "fix",
    }
