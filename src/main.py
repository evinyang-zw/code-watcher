from __future__ import annotations

import asyncio
import json
import logging
import re
import sys

from dotenv import load_dotenv

from src.graph.workflow import compile_workflow

logger = logging.getLogger(__name__)


async def review_pull_request(
    pr_url: str,
    auto_fix: bool = False,
    dry_run: bool = False,
):
    """Run the Code Watcher review workflow on a GitHub PR."""
    # Validate PR URL format
    if not re.match(r"https?://github\.com/[^/]+/[^/]+/pull/\d+", pr_url):
        print(f"Error: Invalid GitHub PR URL: {pr_url}", file=sys.stderr)
        print("Expected format: https://github.com/owner/repo/pull/123", file=sys.stderr)
        return None

    workflow = compile_workflow()
    config = {"configurable": {"thread_id": f"pr-{pr_url}"}}

    try:
        result = await workflow.ainvoke(
            {
                "pr_url": pr_url,
                "auto_fix_enabled": auto_fix,
                "dry_run": dry_run,
            },
            config,
        )
    except Exception as e:
        logger.error("Workflow failed: %s", e)
        print(f"Error: Review workflow failed: {e}", file=sys.stderr)
        return None

    if "__interrupt__" in result:
        print("Graph interrupted for human review.")
        print(json.dumps(result["__interrupt__"], indent=2, ensure_ascii=False))
        return result

    print(f"Review complete. Phase: {result.get('phase', 'unknown')}")
    print(f"Findings: {len(result.get('all_findings', []))}")
    print(f"Confidence: {result.get('overall_confidence', 0):.2f}")
    return result


def main():
    load_dotenv()

    import argparse

    parser = argparse.ArgumentParser(description="Code Watcher - Automated Code Review")
    parser.add_argument("pr_url", help="GitHub PR URL")
    parser.add_argument("--auto-fix", action="store_true", help="Enable auto-fix")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    result = asyncio.run(review_pull_request(args.pr_url, args.auto_fix, args.dry_run))
    sys.exit(0 if result is not None else 1)


if __name__ == "__main__":
    main()
