import asyncio
import json
import uuid
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import queue

from src.jobs import job_manager

app = FastAPI(title="PHANTOM Lite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobRequest(BaseModel):
    repo_url: str
    issue_text: str

@app.post("/api/jobs")
async def create_job(req: JobRequest):
    if not req.repo_url or not req.issue_text:
        raise HTTPException(status_code=400, detail="repo_url and issue_text are required")
        
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job = job_manager.start_job(job_id, req.repo_url, req.issue_text)
    
    return {"job_id": job.job_id, "status": job.status}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "job_id": job.job_id,
        "repo_url": job.repo_url,
        "status": job.status,
        "created_at": job.created_at,
        "finished_at": job.finished_at
    }

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_manager.cancel_job(job_id)
    return {"message": "Job cancellation requested", "status": "cancelling"}

@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    print(f"Browser disconnected for job {job_id}. Cancelling.")
                    job_manager.cancel_job(job_id)
                    break

                try:
                    # Non-blocking check with short timeout to allow disconnect polling
                    # Using thread-safe queue.get() in an async context isn't ideal but works for a fast 0.1s poll
                    event_data = await asyncio.to_thread(job.queue.get, True, 0.1)
                    
                    event_type = event_data.get("event", "message")
                    data = event_data.get("data", "")
                    
                    if not isinstance(data, str):
                        data = json.dumps(data)
                        
                    yield {
                        "event": event_type,
                        "data": data
                    }
                    
                    if event_type == "done":
                        break
                        
                except queue.Empty:
                    # Check if job naturally terminated without sending 'done'
                    if job.status in ("success", "failed", "cancelled", "crashed"):
                        yield {
                            "event": "done",
                            "data": ""
                        }
                        break
                    continue
        except asyncio.CancelledError:
            print(f"Browser disconnect detected via CancelledError for job {job_id}. Cancelling.")
            job_manager.cancel_job(job_id)
            raise
        except Exception as e:
            print(f"Error in SSE stream for job {job_id}: {e}")
            yield {
                "event": "error",
                "data": str(e)
            }

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
