from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import ReviewState
from src.llm.prompts import FIX_GENERATION_PROMPT
from src.llm.provider import create_llm_provider
from src.schema.types import FixPatch, ReviewFinding


async def _generate_patch(finding: ReviewFinding) -> FixPatch | None:
    """Generate a unified diff patch for a single finding."""
    if not finding.suggested_fix:
        return None

    prompt = FIX_GENERATION_PROMPT.format(
        message=finding.message,
        severity=finding.severity,
        suggested_fix=finding.suggested_fix,
        current_content="",  # Could provide full file content here
    )

    provider = create_llm_provider()
    messages = [
        SystemMessage(content="Generate a unified diff patch. Return ONLY the diff."),
        HumanMessage(content=prompt),
    ]

    try:
        response = await provider.chat(messages)
        # Extract diff if wrapped in code blocks
        patch_diff = response.strip()
        if patch_diff.startswith("```"):
            patch_diff = patch_diff.split("\n", 1)[1]
            if patch_diff.endswith("```"):
                patch_diff = patch_diff[:-3]
            patch_diff = patch_diff.strip()

        return FixPatch(
            finding=finding,
            patch_diff=patch_diff,
            description=finding.message,
        )
    except Exception:
        return None


async def suggest_fixes_node(state: ReviewState) -> dict:
    """Generate fix patches for findings that have suggested_fix."""
    fixable = [
        s for s in state["suggestions"]
        if s.severity in ("warning", "suggestion", "nit") and s.suggested_fix is not None
    ]

    generated_fixes = []
    for finding in fixable:
        patch = await _generate_patch(finding)
        if patch:
            generated_fixes.append(patch)

    return {
        "generated_fixes": generated_fixes,
        "phase": "evaluate",
    }
