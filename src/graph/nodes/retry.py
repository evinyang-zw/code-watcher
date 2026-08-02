from __future__ import annotations

import asyncio

from src.graph.state import ReviewState

MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 3.0, 10.0]


async def retry_node(state: ReviewState) -> dict:
    """Retry LLM call with exponential backoff."""
    retry_count = state["metadata"].retry_count
    if retry_count >= MAX_RETRIES:
        return {"error": f"LLM call failed {MAX_RETRIES} times", "phase": "human"}

    delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
    await asyncio.sleep(delay)

    return {
        "metadata": state["metadata"].model_copy(update={"retry_count": retry_count + 1})
    }
