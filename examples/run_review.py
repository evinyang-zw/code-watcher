#!/usr/bin/env python3
"""Example: run the Code Watcher workflow programmatically.

Offline (default, no keys needed)::

    python examples/run_review.py

Real PR::

    EXAMPLE_PR_URL=https://github.com/owner/repo/pull/123 \
    EXAMPLE_OFFLINE=0 python examples/run_review.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_review_state
from src.graph.workflow import compile_workflow


async def main() -> None:
    load_dotenv()

    offline = os.environ.get("EXAMPLE_OFFLINE", "1") not in ("0", "false", "False")
    pr_url = os.environ.get("EXAMPLE_PR_URL", "https://github.com/acme/demo/pull/102")

    if offline:
        os.environ["CODEWATCHER_GITHUB"] = "fake"
        os.environ.setdefault("CODEWATCHER_FIXTURE_DIR", "fixtures/pr-102")
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ.setdefault(
            "MOCK_LLM_FIXTURE",
            os.path.join(os.environ["CODEWATCHER_FIXTURE_DIR"], "mock_llm.json"),
        )

    print(f"Reviewing PR: {pr_url} (offline={offline})")
    print("=" * 60)

    workflow = compile_workflow(MemorySaver())
    config = {"configurable": {"thread_id": f"pr-{pr_url}"}, "recursion_limit": 50}

    result = await workflow.ainvoke(
        create_review_state(pr_url=pr_url, auto_fix_enabled=True, dry_run=True),
        config,
    )

    if "__interrupt__" in result:
        payload = [getattr(item, "value", item) for item in result["__interrupt__"]]
        print("\nGraph paused for human review:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        # A real integration would wait for a human and resume with Command.
        print("\nResume with Command(resume={'approved_fixes': [...], 'feedback': '...'})")
        return

    print(f"\nPhase: {result.get('phase', 'unknown')}")
    print(f"Findings: {len(result.get('all_findings', []))}")
    for finding in result.get("all_findings", []):
        print(f"  [{finding.severity}] {finding.file_path}:{finding.line} — {finding.message}")
    if result.get("review_summary"):
        print(f"\nSummary:\n{result['review_summary']}")


if __name__ == "__main__":
    asyncio.run(main())
