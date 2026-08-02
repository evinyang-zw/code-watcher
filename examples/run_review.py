#!/usr/bin/env python3
"""Example script demonstrating the Code Watcher workflow."""

from __future__ import annotations

import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from src.graph.workflow import compile_workflow


async def main():
    load_dotenv()

    # Example PR URL (replace with a real one)
    pr_url = os.environ.get("EXAMPLE_PR_URL", "https://github.com/example/repo/pull/1")

    print(f"Reviewing PR: {pr_url}")
    print("=" * 60)

    workflow = compile_workflow()
    config = {"configurable": {"thread_id": f"pr-{pr_url}"}}

    result = await workflow.ainvoke(
        {
            "pr_url": pr_url,
            "auto_fix_enabled": True,
            "dry_run": True,  # Start with dry run
        },
        config,
    )

    # Check if interrupted for human review
    if "__interrupt__" in result:
        print("\nGraph interrupted for human review.")
        print("Interrupt data:")
        print(json.dumps(result["__interrupt__"], indent=2, ensure_ascii=False))
        print("\nTo resume, call workflow.ainvoke with human feedback.")
        return

    # Print results
    print(f"\nPhase: {result.get('phase', 'unknown')}")
    print(f"Findings: {len(result.get('all_findings', []))}")
    print(f"Confidence: {result.get('overall_confidence', 0):.2f}")

    if result.get("review_summary"):
        print(f"\nSummary:\n{result['review_summary']}")


if __name__ == "__main__":
    asyncio.run(main())
