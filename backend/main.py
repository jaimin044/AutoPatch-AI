"""
main.py — CLI entry point for PHANTOM Lite.

Usage:
    python main.py --repo <repo_url_or_path> --issue "<issue text>"
    python main.py --repo ../benchmarks/repos/case_01_divide_by_zero --issue "divide by zero crashes"
"""

import argparse
import threading
import time
import uuid
import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from src.orchestrator import build_graph
from src.state import AgentState
from src.sandbox import cleanup_sandbox


def main():
    parser = argparse.ArgumentParser(description="PHANTOM Lite — Autonomous Bug Fixer")
    parser.add_argument("--repo", required=True, help="GitHub repo URL or local path to clone")
    parser.add_argument("--issue", required=True, help="Bug report / issue text")
    parser.add_argument("--test-cmd", default="", help="Test command (default: auto-detect or pytest)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Max fix attempts (default: 3)")
    args = parser.parse_args()

    job_id = f"cli-{uuid.uuid4().hex[:8]}"
    cancel_event = threading.Event()

    # If it's a local path, resolve it to absolute
    repo_url = args.repo
    if os.path.isdir(repo_url):
        repo_url = os.path.abspath(repo_url)

    print("=" * 60)
    print("  PHANTOM Lite — Autonomous Bug Fixer")
    print("=" * 60)
    print(f"  Job ID:       {job_id}")
    print(f"  Repo:         {repo_url}")
    print(f"  Issue:        {args.issue[:80]}...")
    print(f"  Max Attempts: {args.max_attempts}")
    print("=" * 60)
    print()

    initial_state = AgentState(
        job_id=job_id,
        repo_url=repo_url,
        issue_text=args.issue,
        sandbox_id="",
        network_name="",
        repo_path="",
        repo_index=[],
        retrieved_files=[],
        retrieved_context="",
        test_command=args.test_cmd,
        target_file="",
        target_code="",
        baseline_error="",
        proposed_patch="",
        replacement_file="",
        replacement_code="",
        validation_error="",
        validation_passed=False,
        attempt=0,
        max_attempts=args.max_attempts,
        status="",
        logs=[],
    )

    graph = build_graph()
    config = {
        "configurable": {
            "cancel_event": cancel_event,
        }
    }

    start_time = time.time()

    try:
        final_state = graph.invoke(initial_state, config=config)

        elapsed = time.time() - start_time

        print()
        print("=" * 60)
        print("  RESULTS")
        print("=" * 60)
        print(f"  Status:   {final_state.get('status', 'unknown')}")
        print(f"  Attempts: {final_state.get('attempt', 0)}")
        print(f"  Runtime:  {elapsed:.1f}s")
        print()

        print("  --- Logs ---")
        for log in final_state.get("logs", []):
            print(f"  {log}")

        print()
        if final_state.get("status") == "success":
            print("  ✓ Bug fixed successfully!")
            if final_state.get("proposed_patch"):
                print()
                print("  --- Final Patch ---")
                print(final_state["proposed_patch"])
        else:
            print("  ✗ Failed to fix the bug.")
            if final_state.get("validation_error"):
                print(f"  Last error: {final_state['validation_error'][:300]}")

        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted! Cleaning up...")
        cancel_event.set()
        cleanup_sandbox(job_id)
        print("Cleanup done.")
    except Exception as e:
        print(f"\nCrashed: {e}")
        print("Cleaning up...")
        try:
            cleanup_sandbox(job_id)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
