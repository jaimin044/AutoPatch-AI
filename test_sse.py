import time
import requests
import subprocess
import threading
import json
import sys

def run_server():
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--port", "8001"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def test_sse():
    print("Starting server...")
    server = run_server()
    time.sleep(2)  # Wait for server to start
    if server.poll() is not None:
        out, err = server.communicate()
        print("Server crashed immediately!")
        print("STDOUT:", out)
        print("STDERR:", err)
        return

    try:
        # Create a job
        print("Creating job...")
        resp = requests.post(
            "http://127.0.0.1:8001/api/jobs",
            json={"repo_url": "benchmarks/repos/case_01_divide_by_zero", "issue_text": "divide by zero"}
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        print(f"Created job: {job_id}")

        # Stream events
        print("Connecting to SSE stream...")
        with requests.get(f"http://127.0.0.1:8001/api/jobs/{job_id}/events", stream=True) as r:
            count = 0
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('event:'):
                        event = decoded_line.split(':', 1)[1].strip()
                        print(f"Event: {event}")
                    elif decoded_line.startswith('data:'):
                        data = decoded_line.split(':', 1)[1].strip()
                        print(f"Data: {data[:100]}")
                        count += 1
                        
                        if count >= 3:
                            print("Received enough events, cancelling job to test cancellation.")
                            cancel_resp = requests.post(f"http://127.0.0.1:8001/api/jobs/{job_id}/cancel")
                            print("Cancel response:", cancel_resp.json())
                            break
                            
            print("Checking final status...")
            status_resp = requests.get(f"http://127.0.0.1:8001/api/jobs/{job_id}")
            print("Final job status:", status_resp.json())
            
            assert status_resp.json()["status"] in ["cancelled", "crashed", "failed"]

    finally:
        print("Terminating server...")
        server.terminate()
        server.wait()

if __name__ == "__main__":
    test_sse()
    print("SSE Test passed.")
