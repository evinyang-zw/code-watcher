from __future__ import annotations

REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Review the following code segment from a pull request. You are reviewing ONLY this segment — do not speculate about code outside the shown context.

Review dimensions: {dimensions}

For EACH issue found, respond with a JSON object in this exact format:
{{
  "severity": "critical" | "warning" | "suggestion" | "nit",
  "dimension": "correctness" | "style" | "security" | "performance" | "test_coverage",
  "line": <line_number_within_new_content>,
  "message": "<clear, actionable description>",
  "suggested_fix": "<optional: specific code change or null>"
}}

Return a JSON array of findings. If no issues found, return an empty array [].

IMPORTANT:
- Line numbers refer to the NEW content (after the change).
- Be specific: reference variable names, function names, exact patterns.
- False positives waste developer time. Only report genuine issues.
- Critical = will cause bugs, data loss, or security vulnerabilities.
- Warning = likely problematic, should be addressed before merge.
- Suggestion = code smell or improvement opportunity.
- Nit = style preference, optional.
"""

REVIEW_USER_PROMPT = """File: {file_path}
Language: {language}

--- Context (unchanged lines for reference) ---
{context_before}

--- New Code (being added/modified) ---
{new_content}

--- End ---
"""

REVIEW_OVERVIEW_PROMPT = """You are an expert code reviewer. Review this code segment at a HIGH LEVEL.
Focus only on: critical bugs, security vulnerabilities, and major logic errors.
Ignore style issues, nits, and minor suggestions.

Return JSON array with ONLY critical/warning severity findings.
If no critical issues, return empty array [].

File: {file_path}
Language: {language}

--- New Code ---
{new_content}

--- End ---
"""

REVIEW_DETAIL_PROMPT = """You are an expert code reviewer. Do a DETAILED review of this code segment.
Focus on: style, performance, test coverage, and minor improvements.

Return JSON array with ALL severity levels (critical/warning/suggestion/nit).

File: {file_path}
Language: {language}

--- New Code ---
{new_content}

--- End ---
"""

FIX_GENERATION_PROMPT = """You are an expert developer. Generate a unified diff patch to fix the following issue in the code below.

Issue: {message}
Severity: {severity}
Suggested fix from reviewer: {suggested_fix}

Current code:
{current_content}

Generate ONLY the unified diff (unified format, @@ markers). Do not include explanations.
The patch must apply cleanly to the current code.
"""

SELF_EVALUATE_PROMPT = """You are a code quality evaluator. A fix has been generated for a review finding. Assess the fix's quality.

Original finding: {finding_message}
Generated patch:
{patch_diff}

After running the patch, these were the results:
- Syntax valid: {syntax_valid}
- Tests pass: {tests_pass}
- Lint clean: {lint_clean}
- Security scan: {security_clean}
- Performance score: {performance_score}

Pre-fix quality score: {pre_fix_quality_score}
Post-fix quality score: {post_fix_quality_score}
Quality delta: {quality_delta}

Provide:
1. confidence_score (0.0-1.0): How confident are you this fix is correct?
2. notes: Brief explanation considering: Does the fix address the issue? Could it introduce new bugs? Is it the minimal change needed?
"""

DOMAIN_PROMPTS = {
    "react": """Review this React component. Focus on:
- Hook dependency arrays (missing deps)
- Unnecessary re-renders
- Key prop usage in lists
- Memory leaks (useEffect cleanup)
- Accessibility (aria attributes)
""",
    "fastapi": """Review this FastAPI endpoint. Focus on:
- Input validation (Pydantic models)
- Error handling (HTTPException)
- Database session management
- Rate limiting
- Authentication/authorization
""",
    "sqlalchemy": """Review this SQLAlchemy code. Focus on:
- N+1 query problems
- Missing indexes
- Transaction management
- Connection pool settings
- Query optimization
""",
}
