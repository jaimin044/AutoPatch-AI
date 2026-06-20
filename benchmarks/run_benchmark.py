import json
import time
import uuid
import os
import sys

# Ensure backend can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from src.orchestrator import build_graph
from src.state import AgentState
from src.sandbox import cleanup_sandbox

def run_benchmarks():
    cases_file = os.path.join(os.path.dirname(__file__), "cases.json")
    results_file = os.path.join(os.path.dirname(__file__), "results.json")
    
    with open(cases_file, "r") as f:
        cases = json.load(f)
        
    graph = build_graph()
    
    results = {
        "summary": {
            "cases": len(cases),
            "solved": 0,
            "success_rate": 0,
            "avg_attempts": 0,
            "avg_runtime": 0,
            "patch_failures": 0,
            "replacement_fallbacks": 0,
            "timeouts": 0
        },
        "cases": []
    }
    
    total_runtime = 0
    total_attempts = 0

    print("Starting PHANTOM Lite Benchmark Suite...\n")
    
    for case in cases:
        print(f"Running Case: {case['name']} ({case['id']})")
        job_id = f"bench-{uuid.uuid4().hex[:8]}"
        
        initial_state = AgentState(
            job_id=job_id,
            repo_url=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", case["local_path"])),
            issue_text=case["issue_text"],
            sandbox_id="",
            network_name="",
            repo_path="",
            repo_index=[],
            retrieved_files=[],
            retrieved_context="",
            test_command=case["test_command"],
            target_file="",
            target_code="",
            baseline_error="",
            proposed_patch="",
            replacement_file="",
            replacement_code="",
            validation_error="",
            validation_passed=False,
            attempt=0,
            max_attempts=3,
            status="pending",
            logs=[]
        )
        
        start_time = time.time()
        final_state = {}
        crashed = False
        
        try:
            # We invoke the graph synchronously
            final_state = graph.invoke(initial_state, config={"configurable": {}})
        except Exception as e:
            print(f"Graph execution crashed: {e}")
            crashed = True
        finally:
            cleanup_sandbox(job_id)
            
        runtime = time.time() - start_time
        
        # Analyze outcome
        status = final_state.get("status", "failed") if not crashed else "crashed"
        solved = status == "success"
        attempts = final_state.get("attempt", 0)
        
        if solved:
            results["summary"]["solved"] += 1
            
        total_attempts += attempts
        total_runtime += runtime
        
        # Count patch issues based on logs
        logs = final_state.get("logs", [])
        patch_failures = sum(1 for log in logs if "Patch apply failed" in log)
        replacements = sum(1 for log in logs if "Fallback Replacement: " in log)
        
        results["summary"]["patch_failures"] += patch_failures
        results["summary"]["replacement_fallbacks"] += replacements
        
        case_result = {
            "id": case["id"],
            "name": case["name"],
            "status": status,
            "runtime_seconds": round(runtime, 2),
            "attempts": attempts,
            "patch_failures": patch_failures,
            "replacement_fallbacks": replacements,
            "error": final_state.get("validation_error", "") if not solved else ""
        }
        results["cases"].append(case_result)
        
        print(f"  Status: {status}")
        print(f"  Attempts: {attempts}")
        print(f"  Runtime: {round(runtime, 2)}s\n")
        
    # Finalize summary
    if len(cases) > 0:
        results["summary"]["success_rate"] = round((results["summary"]["solved"] / len(cases)) * 100, 2)
        results["summary"]["avg_attempts"] = round(total_attempts / len(cases), 2)
        results["summary"]["avg_runtime"] = round(total_runtime / len(cases), 2)
        
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print("Benchmark complete!")
    print(f"Solved: {results['summary']['solved']}/{len(cases)} ({results['summary']['success_rate']}%)")
    print(f"Results saved to {results_file}")

if __name__ == "__main__":
    run_benchmarks()
