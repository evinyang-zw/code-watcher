from __future__ import annotations

from langgraph.types import interrupt

from src.graph.state import ReviewState


async def human_review_node(state: ReviewState) -> dict:
    """Interrupt graph for human review of findings and proposed fixes."""
    findings_summary = [
        {"id": f.finding_id, "file": f.file_path, "line": f.line,
         "severity": f.severity, "message": f.message}
        for f in state["suggestions"]
    ]
    fixes_summary = [
        {"finding_id": f.finding.finding_id, "description": f.description,
         "confidence": f.finding.confidence}
        for f in state["approved_fixes"]
    ]

    human_response = interrupt({
        "message": "Review findings and proposed fixes. Approve, modify, or reject.",
        "findings": findings_summary,
        "proposed_fixes": fixes_summary,
    })

    # Handle None response (interrupt not properly resumed)
    if human_response is None:
        human_response = {}

    return {
        "human_approved_fixes": human_response.get("approved_fixes", []),
        "human_feedback": human_response.get("feedback", ""),
        "phase": "post",
    }
