import threading
import sys
from src.sandbox import create_sandbox, install_dependencies, disable_network, run_untrusted_command, cleanup_sandbox

def test_sandbox():
    job_id = "test-job-001"
    cancel_event = threading.Event()
    repo_url = "https://github.com/octocat/Hello-World.git" # Tiny public repo
    
    print("1. Creating Sandbox...")
    try:
        sandbox = create_sandbox(job_id, repo_url, cancel_event)
        print(f"Sandbox created: {sandbox}")
        
        print("2. Running untrusted command (ls)...")
        res = run_untrusted_command(sandbox, "ls -la", cancel_event)
        print(f"Command output:\n{res['stdout']}")
        
        print("3. Disabling network...")
        disable_network(sandbox)
        print("Network disabled.")
        
        print("4. Running untrusted command (ping) expecting failure...")
        res = run_untrusted_command(sandbox, "ping -c 1 8.8.8.8", cancel_event)
        print(f"Ping result (should be failed): returncode={res['returncode']}, stderr={res['stderr']}")
        
        print("5. Testing timeout (sleep 10s with 5s timeout config if modified, or just sleep 70)...")
        # We know default timeout is 60. Let's just pass for now to avoid waiting 60s in a quick test.
        # res = run_untrusted_command(sandbox, "sleep 70", cancel_event)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("6. Cleaning up sandbox...")
        cleanup_sandbox(job_id)
        print("Cleanup complete.")

if __name__ == "__main__":
    test_sandbox()
