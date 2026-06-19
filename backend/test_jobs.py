import os
import time
from src.jobs import job_manager

def run_test():
    repo_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "benchmarks", "repos", "case_01_divide_by_zero"))
    job_id = f"test-jobmgr-{int(time.time())}"
    
    print(f"Starting job {job_id}")
    job = job_manager.start_job(job_id, repo_url, "The divide function crashes.")
    
    # Let it run for 1 second (should be in the middle of setup or reproduce)
    time.sleep(1)
    
    print("Cancelling job...")
    job_manager.cancel_job(job_id)
    
    # Wait for thread to finish
    job.thread.join(timeout=10)
    
    print(f"Job Status: {job.status}")
    print(f"Job Finished At: {job.finished_at}")
    print("If status is 'cancelled' and Finished At is set, the finally block executed perfectly.")

if __name__ == "__main__":
    run_test()
