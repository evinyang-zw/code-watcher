from __future__ import annotations

import hashlib
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import ReviewState
from src.llm.few_shot import get_few_shot_prompt
from src.llm.prompts import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT
from src.llm.provider import create_llm_provider
from src.schema.types import ReviewFinding, ReviewResult


async def review_segment_node(state: ReviewState) -> dict:
    """Review a single code segment using LLM."""
    idx = state["current_segment_index"]
    if idx >= len(state["segments"]):
        return {"current_segment_index": idx, "phase": "aggregate"}

    segment = state["segments"][idx]

    # Cache check is handled by cache_check_node upstream; call LLM directly
    dimensions = ", ".join(state["review_dimensions"])
    system_prompt = REVIEW_SYSTEM_PROMPT.format(dimensions=dimensions)
    few_shot = get_few_shot_prompt(segment.language)
    if few_shot:
        system_prompt += "\n\n" + few_shot

    user_prompt = REVIEW_USER_PROMPT.format(
        file_path=segment.file_path,
        language=segment.language,
        context_before=segment.old_content,
        new_content=segment.new_content,
    )

    provider = create_llm_provider()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    start = time.monotonic()
    try:
        raw = await provider.chat_json(messages)
    except Exception:
        raw = []
    duration_ms = int((time.monotonic() - start) * 1000)

    findings = []
    for item in raw:
        try:
            finding = ReviewFinding(
                finding_id=f"f-{hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()[:8]}",
                file_path=segment.file_path,
                line=item.get("line", 0),
                severity=item.get("severity", "suggestion"),
                dimension=item.get("dimension", "style"),
                message=item.get("message", ""),
                suggested_fix=item.get("suggested_fix"),
            )
            findings.append(finding)
        except Exception:
            continue

    result = ReviewResult(
        segment=segment,
        findings=findings,
        review_duration_ms=duration_ms,
    )

    # Store in cache
    cache.put(segment, result)

    new_metadata = state["metadata"].model_copy(update={
        "cache_misses": state["metadata"].cache_misses + 1,
    })

    return {
        "current_segment_index": idx + 1,
        "segment_reviews": [result],
        "metadata": new_metadata,
        "phase": "review",
    }
