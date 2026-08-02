from __future__ import annotations

from src.graph.state import ReviewState
from src.schema.types import FileReviewGroup, ReviewFinding


def _deduplicate_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Deduplicate findings by file + line + message."""
    seen = set()
    unique = []
    for f in findings:
        key = (f.file_path, f.line, f.message)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


async def aggregate_node(state: ReviewState) -> dict:
    """Collect and deduplicate segment reviews, group by file."""
    all_findings = []
    for review in state["segment_reviews"]:
        all_findings.extend(review.findings)

    # Deduplicate
    all_findings = _deduplicate_findings(all_findings)

    # Group by file
    file_groups: dict[str, FileReviewGroup] = {}
    for finding in all_findings:
        fp = finding.file_path
        if fp not in file_groups:
            file_groups[fp] = FileReviewGroup(file_path=fp)
        group = file_groups[fp]
        group.findings.append(finding)
        group.total_findings = len(group.findings)
        if finding.severity == "critical":
            group.critical_count += 1

    # Attach review results to groups
    for review in state["segment_reviews"]:
        fp = review.segment.file_path
        if fp in file_groups:
            file_groups[fp].review_results.append(review)

    return {
        "all_findings": all_findings,
        "file_groups": file_groups,
        "suggestions": all_findings,
        "phase": "suggest",
    }
