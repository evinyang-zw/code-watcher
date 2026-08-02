from __future__ import annotations

import re

SECURITY_PATTERNS = {
    "sql_injection": {
        "pattern": r"f['\"].*\{.*\}|execute\(.*%s|\.format\(.*\)",
        "description": "Potential SQL injection via string interpolation",
    },
    "xss": {
        "pattern": r"innerHTML|dangerouslySetInnerHTML|document\.write",
        "description": "Potential XSS vulnerability",
    },
    "hardcoded_secret": {
        "pattern": r"(?:password|secret|token|api_key)\s*=\s*['\"][^'\"]{8,}",
        "description": "Hardcoded secret or credential",
    },
    "path_traversal": {
        "pattern": r"\.\.\/|os\.path\.join\(.*\.\.",
        "description": "Potential path traversal vulnerability",
    },
    "eval_usage": {
        "pattern": r"\beval\(|exec\(",
        "description": "Use of eval/exec can lead to code injection",
    },
    "insecure_random": {
        "pattern": r"\brandom\.(random|randint|choice)\b",
        "description": "Insecure random number generation (use secrets module for security)",
    },
    "hardcoded_ip": {
        "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "description": "Hardcoded IP address",
    },
}


def scan_code(code: str) -> list[str]:
    """Scan code for security vulnerabilities. Returns list of finding descriptions."""
    findings = []
    for name, config in SECURITY_PATTERNS.items():
        if re.search(config["pattern"], code):
            findings.append(f"[{name}] {config['description']}")
    return findings


def scan_code_detailed(code: str) -> list[dict]:
    """Scan code and return detailed findings."""
    findings = []
    for name, config in SECURITY_PATTERNS.items():
        matches = list(re.finditer(config["pattern"], code))
        for match in matches:
            line_num = code[:match.start()].count("\n") + 1
            findings.append({
                "rule": name,
                "description": config["description"],
                "line": line_num,
                "match": match.group(),
            })
    return findings
