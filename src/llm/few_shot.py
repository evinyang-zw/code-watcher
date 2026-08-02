from __future__ import annotations

FEW_SHOT_EXAMPLES = {
    "python": [
        {
            "code": '''def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return db.execute(query)''',
            "findings": [
                {
                    "severity": "critical",
                    "dimension": "security",
                    "line": 2,
                    "message": "SQL injection risk: user input directly interpolated into SQL query via f-string",
                    "suggested_fix": 'query = "SELECT * FROM users WHERE id = %s"\nreturn db.execute(query, (id,))',
                }
            ],
        },
        {
            "code": """for item in items:
    result = []
    for sub in item.subs:
        result.append(transform(sub))""",
            "findings": [
                {
                    "severity": "warning",
                    "dimension": "performance",
                    "line": 1,
                    "message": "Repeated append in loop; use list comprehension for better performance",
                    "suggested_fix": "result = [transform(sub) for sub in item.subs]",
                }
            ],
        },
    ],
    "typescript": [
        {
            "code": "const data = JSON.parse(userInput);",
            "findings": [
                {
                    "severity": "critical",
                    "dimension": "security",
                    "line": 1,
                    "message": "Parsing untrusted input directly can lead to injection attacks",
                    "suggested_fix": "const data = JSON.parse(sanitizeInput(userInput));",
                }
            ],
        }
    ],
}


def get_few_shot_prompt(language: str) -> str:
    """Format few-shot examples for a given language."""
    examples = FEW_SHOT_EXAMPLES.get(language, [])
    if not examples:
        return ""

    lines = ["Here are example reviews for reference:\n"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i}:")
        lines.append(f"Code:\n{ex['code']}")
        lines.append(f"Findings:\n{json_dumps(ex['findings'])}")
        lines.append("")

    return "\n".join(lines)


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, indent=2, ensure_ascii=False)
