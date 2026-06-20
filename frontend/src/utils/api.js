import { fetchEventSource } from '@microsoft/fetch-event-source';

const API_BASE = 'http://localhost:8000/api/jobs';

export async function startJob(repoUrl, issueText) {
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, issue_text: issueText })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to start job');
  }
  
  return res.json();
}

export async function cancelJob(jobId) {
  const res = await fetch(`${API_BASE}/${jobId}/cancel`, {
    method: 'POST'
  });
  
  if (!res.ok) {
    throw new Error('Failed to cancel job');
  }
  
  return res.json();
}

export function subscribeToJobEvents(jobId, handlers) {
  const controller = new AbortController();
  
  fetchEventSource(`${API_BASE}/${jobId}/events`, {
    method: 'GET',
    signal: controller.signal,
    
    onmessage(msg) {
      if (msg.event === 'log' && handlers.onLog) {
        handlers.onLog(msg.data);
      } else if (msg.event === 'status' && handlers.onStatus) {
        handlers.onStatus(msg.data);
      } else if (msg.event === 'retrieval' && handlers.onRetrieval) {
        try {
          const files = JSON.parse(msg.data);
          handlers.onRetrieval(files);
        } catch (e) {
          console.error("Failed to parse retrieval event data", e);
        }
      } else if (msg.event === 'patch' && handlers.onPatch) {
        handlers.onPatch(msg.data);
      } else if (msg.event === 'done' || msg.event === 'error') {
        if (msg.event === 'error' && handlers.onError) {
          handlers.onError(msg.data);
        }
        controller.abort();
      }
    },
    
    onerror(err) {
      console.error("SSE Error:", err);
      if (handlers.onError) handlers.onError(err.message || 'Connection error');
      throw err; // Re-throw to prevent reconnect loop if we don't want it
    },
    
    onclose() {
      // Disconnected
    }
  });
  
  return () => controller.abort();
}
