from __future__ import annotations

import re

PERFORMANCE_ISSUES = {
    "nested_loop": {
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n\s+for\s+\w+\s+in",
        "description": "Nested loop detected (O(n²) complexity)",
        "severity": "warning",
    },
    "n_plus_one_query": {
        "pattern": r"\.filter\(.*\)\.all\(\)|\.query\(.*\)\.all\(\)",
        "description": "Potential N+1 query problem",
        "severity": "warning",
    },
    "large_object_copy": {
        "pattern": r"copy\.deepcopy\(|\.copy\(\)",
        "description": "Large object copy detected",
        "severity": "suggestion",
    },
    "string_concat_loop": {
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n\s+.*\+=\s*['\"]",
        "description": "String concatenation in loop (use join or list comprehension)",
        "severity": "suggestion",
    },
    "unbounded_list": {
        "pattern": r"while\s+True\s*:\s*\n\s+.*\.append\(",
        "description": "Unbounded list growth in infinite loop",
        "severity": "warning",
    },
    "global_import_in_loop": {
        "pattern": r"for\s+.*:\s*\n\s+import\s+",
        "description": "Import statement inside loop",
        "severity": "nit",
    },
}


def analyze_code(code: str) -> list[str]:
    """Analyze code for performance issues. Returns list of finding descriptions."""
    findings = []
    for name, config in PERFORMANCE_ISSUES.items():
        if re.search(config["pattern"], code, re.MULTILINE):
            findings.append(f"[{name}] {config['description']}")
    return findings


def analyze_code_detailed(code: str) -> list[dict]:
    """Analyze code and return detailed findings."""
    findings = []
    for name, config in PERFORMANCE_ISSUES.items():
        matches = list(re.finditer(config["pattern"], code, re.MULTILINE))
        for match in matches:
            line_num = code[:match.start()].count("\n") + 1
            findings.append({
                "rule": name,
                "description": config["description"],
                "severity": config["severity"],
                "line": line_num,
            })
    return findings


def compute_performance_score(code: str) -> float:
    """Compute a performance score (0.0-1.0) based on detected issues."""
    issues = analyze_code(code)
    if not issues:
        return 1.0
    penalty = len(issues) * 0.15
    return max(0.0, 1.0 - penalty)
