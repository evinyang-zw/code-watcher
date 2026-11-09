from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.cache.review_cache import get_cache
from src.graph.state import ReviewState
from src.llm.few_shot import get_few_shot_prompt
from src.llm.prompts import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT
from src.llm.provider import create_llm_provider
from src.schema.types import ReviewFinding, ReviewResult

logger = logging.getLogger(__name__)


def _as_finding_list(raw: Any) -> list[dict]:
    """Normalize the LLM response into a list of finding dicts."""
    if isinstance(raw, dict):
        for key in ("findings", "issues", "results"):
            if isinstance(raw.get(key), list):
                return [item for item in raw[key] if isinstance(item, dict)]
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _absolute_line(segment_line: int, relative_line: Any) -> int:
    """Convert a 1-based line inside the new content to a file line number.

    The LLM is asked for ``line_number_within_new_content``; GitHub review
    comments need the absolute line in the new file. ``segment.hunk_start`` is
    the new-file line of the hunk's first line, so absolute = start + rel - 1.
    """
    try:
        rel = int(relative_line)
    except (TypeError, ValueError):
        rel = 1
    rel = max(1, rel)
    return segment_line + rel - 1


async def review_segment_node(state: ReviewState) -> dict:
    """Review a single code segment using the configured LLM."""
    idx = state["current_segment_index"]
    if idx >= len(state["segments"]):
        return {"current_segment_index": idx, "phase": "aggregate"}

    segment = state["segments"][idx]

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
    except Exception as exc:  # LLM/JSON failures must not kill the whole run
        logger.warning("Review call failed for %s: %s", segment.file_path, exc)
        raw = []
    duration_ms = int((time.monotonic() - start) * 1000)

    findings: list[ReviewFinding] = []
    for item in _as_finding_list(raw):
        try:
            finding = ReviewFinding(
                finding_id=(
                    "f-" + hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()[:8]
                ),
                file_path=segment.file_path,
                line=_absolute_line(segment.hunk_start, item.get("line", 1)),
                severity=item.get("severity", "suggestion"),
                dimension=item.get("dimension", "style"),
                message=item.get("message", ""),
                suggested_fix=item.get("suggested_fix"),
            )
            findings.append(finding)
        except Exception as exc:
            logger.debug("Dropping malformed finding %s: %s", item, exc)

    result = ReviewResult(
        segment=segment,
        findings=findings,
        review_duration_ms=duration_ms,
    )

    # Populate the cache so re-runs (and the graph-level re-review loop) are cheap.
    try:
        get_cache().put(segment, result)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Cache write failed: %s", exc)

    return {
        "current_segment_index": idx + 1,
        "segment_reviews": [result],
        "phase": "review",
    }
