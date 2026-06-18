import os
import time
import threading
from pathlib import Path
from src.state import AgentState
from src.orchestrator import build_graph

def run_test():
    repo_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "benchmarks", "repos", "case_01_divide_by_zero"))
    job_id = f"test-orchestrator-{int(time.time())}"
    
    cancel_event = threading.Event()
    
    initial_state = AgentState(
        job_id=job_id,
        repo_url=repo_url,
        issue_text="The divide function crashes with ZeroDivisionError when dividing by zero instead of raising a ValueError with a helpful message.",
        sandbox_id="",
        network_name="",
        repo_path="",
        repo_index=[],
        retrieved_files=[],
        retrieved_context="",
        test_command="pytest tests/test_math_utils.py -v",
        target_file="",
        target_code="",
        baseline_error="",
        proposed_patch="",
        replacement_file="",
        replacement_code="",
        validation_error="",
        validation_passed=False,
        attempt=0,
        max_attempts=1, # Stop quickly for test
        status="",
        logs=[]
    )
    
    graph = build_graph()
    
    config = {
        "configurable": {
            "cancel_event": cancel_event
        }
    }
    
    print(f"Starting orchestration job: {job_id}")
    
    try:
        final_state = graph.invoke(initial_state, config=config)
        print("\n--- Final State ---")
        print("Status:", final_state.get("status"))
        print("Logs:")
        for log in final_state.get("logs", []):
            print(f" - {log}")
    except Exception as e:
        print(f"Graph failed: {e}")
        # Even if it crashes, check if cleanup ran? 
        # Actually LangGraph will only run cleanup if the graph execution reached it.
        # But wait, we specified "always run" and put it at the end. 
        # If an exception happens inside a node, LangGraph raises it. The job manager is supposed to catch it and run cleanup_sandbox directly!
        # This is a critical edge case mentioned in the master plan:
        # "cleanup runs in finally" (in jobs.py, not just the graph node).
        # We'll see if the nodes succeed.

if __name__ == "__main__":
    run_test()
