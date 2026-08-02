from __future__ import annotations

from src.llm.prompts import (
    FIX_GENERATION_PROMPT,
    REVIEW_DETAIL_PROMPT,
    REVIEW_OVERVIEW_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_PROMPT,
    SELF_EVALUATE_PROMPT,
)


def test_review_system_prompt_format():
    prompt = REVIEW_SYSTEM_PROMPT.format(dimensions="correctness, security")
    assert "correctness, security" in prompt
    assert "JSON" in prompt
    assert "critical" in prompt


def test_review_user_prompt_format():
    prompt = REVIEW_USER_PROMPT.format(
        file_path="src/app.py",
        language="python",
        context_before="import os",
        new_content="print('hello')",
    )
    assert "src/app.py" in prompt
    assert "python" in prompt
    assert "import os" in prompt
    assert "print('hello')" in prompt


def test_review_overview_prompt_format():
    prompt = REVIEW_OVERVIEW_PROMPT.format(
        file_path="src/app.py",
        language="python",
        new_content="print('hello')",
    )
    assert "HIGH LEVEL" in prompt
    assert "src/app.py" in prompt


def test_review_detail_prompt_format():
    prompt = REVIEW_DETAIL_PROMPT.format(
        file_path="src/app.py",
        language="python",
        new_content="print('hello')",
    )
    assert "DETAILED" in prompt
    assert "src/app.py" in prompt


def test_fix_generation_prompt_format():
    prompt = FIX_GENERATION_PROMPT.format(
        message="SQL injection",
        severity="critical",
        suggested_fix="Use parameterized query",
        current_content='query = f"SELECT * FROM users WHERE id = {id}"',
    )
    assert "SQL injection" in prompt
    assert "critical" in prompt
    assert "parameterized" in prompt


def test_self_evaluate_prompt_format():
    prompt = SELF_EVALUATE_PROMPT.format(
        finding_message="SQL injection",
        patch_diff="-old\n+new",
        syntax_valid=True,
        tests_pass=True,
        lint_clean=True,
        security_clean=True,
        performance_score=0.9,
        pre_fix_quality_score=0.5,
        post_fix_quality_score=0.9,
        quality_delta=0.4,
    )
    assert "SQL injection" in prompt
    assert "True" in prompt
    assert "0.9" in prompt
