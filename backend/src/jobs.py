import threading
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from .state import AgentState
from .orchestrator import build_graph
from .sandbox import cleanup_sandbox

@dataclass
class Job:
    job_id: str
    repo_url: str
    issue_text: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    status: str = "pending"
    thread: threading.Thread = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: str = None
    logs: List[str] = field(default_factory=list)

class JobManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance.jobs = {}
            cls._instance.graph = build_graph()
        return cls._instance
        
    def start_job(self, job_id: str, repo_url: str, issue_text: str) -> Job:
        job = Job(job_id=job_id, repo_url=repo_url, issue_text=issue_text)
        self.jobs[job_id] = job
        
        thread = threading.Thread(target=self._run_job_thread, args=(job,), daemon=True)
        job.thread = thread
        job.status = "running"
        thread.start()
        
        return job
        
    def _run_job_thread(self, job: Job):
        initial_state = AgentState(
            job_id=job.job_id,
            repo_url=job.repo_url,
            issue_text=job.issue_text,
            sandbox_id="",
            network_name="",
            repo_path="",
            repo_index=[],
            retrieved_files=[],
            retrieved_context="",
            test_command="",
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
            status="",
            logs=[]
        )
        
        config = {
            "configurable": {
                "cancel_event": job.cancel_event
            }
        }
        
        try:
            final_state = self.graph.invoke(initial_state, config=config)
            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.status = final_state.get("status", "failed")
        except Exception as e:
            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.status = "crashed"
        finally:
            # Absolute guarantee that cleanup runs regardless of graph exception
            try:
                cleanup_sandbox(job.job_id)
            except Exception:
                pass
            job.finished_at = datetime.utcnow().isoformat()
            
    def cancel_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id].cancel_event.set()
            
    def get_job(self, job_id: str) -> Job:
        return self.jobs.get(job_id)

job_manager = JobManager()
