from __future__ import annotations

import pytest

from src.graph.nodes.retry import MAX_RETRIES, RETRY_DELAYS, retry_node
from src.graph.state import create_review_state
from src.schema.types import RunMetadata


@pytest.mark.asyncio
async def test_retry_increments_count():
    state = create_review_state(metadata=RunMetadata(retry_count=0))
    result = await retry_node(state)
    assert result["metadata"].retry_count == 1


@pytest.mark.asyncio
async def test_retry_max_exceeded():
    state = create_review_state(metadata=RunMetadata(retry_count=MAX_RETRIES))
    result = await retry_node(state)
    assert result["error"] is not None
    assert result["phase"] == "human"


@pytest.mark.asyncio
async def test_retry_delays():
    assert len(RETRY_DELAYS) >= MAX_RETRIES
    assert RETRY_DELAYS[0] < RETRY_DELAYS[1] < RETRY_DELAYS[2]
