import threading
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

from .state import AgentState
from .sandbox import create_sandbox, install_dependencies, disable_network, cleanup_sandbox, run_untrusted_command, Sandbox
from .patcher import apply_patch, apply_full_replacement

def get_cancel_event(config: RunnableConfig) -> threading.Event:
    return config.get("configurable", {}).get("cancel_event", threading.Event())

def ingest(state: AgentState, config: RunnableConfig):
    # Dummy for Role 2
    return {"logs": ["Started ingestion"]}

def setup_sandbox_node(state: AgentState, config: RunnableConfig):
    cancel_event = get_cancel_event(config)
    job_id = state["job_id"]
    repo_url = state["repo_url"]
    
    sandbox = create_sandbox(job_id, repo_url, cancel_event)
    install_dependencies(sandbox, cancel_event)
    disable_network(sandbox)
    
    return {
        "sandbox_id": sandbox.container_id,
        "network_name": sandbox.network_name,
        "repo_path": sandbox.repo_path,
        "logs": ["Sandbox created and dependencies installed"]
    }

def index_repo(state: AgentState, config: RunnableConfig):
    # Dummy for Role 2
    return {"logs": ["Indexed repository"]}

def reproduce(state: AgentState, config: RunnableConfig):
    cancel_event = get_cancel_event(config)
    sandbox = Sandbox(
        job_id=state["job_id"],
        container_id=state["sandbox_id"],
        network_name=state["network_name"],
        repo_path=state["repo_path"]
    )
    
    test_command = state.get("test_command", "pytest")
    if not test_command:
        test_command = "pytest"
        
    res = run_untrusted_command(sandbox, test_command, cancel_event)
    return {
        "baseline_error": res["stderr"] if res["returncode"] != 0 else "",
        "logs": [f"Reproduced issue: returncode={res['returncode']}"]
    }

def retrieve_context(state: AgentState, config: RunnableConfig):
    # Dummy for Role 2
    return {"logs": ["Retrieved context"]}

def generate_patch(state: AgentState, config: RunnableConfig):
    # Dummy for Role 2
    attempt = state.get("attempt", 0) + 1
    return {
        "attempt": attempt,
        "logs": [f"Generated patch candidate (attempt {attempt})"]
    }

def validate(state: AgentState, config: RunnableConfig):
    cancel_event = get_cancel_event(config)
    sandbox = Sandbox(
        job_id=state["job_id"],
        container_id=state["sandbox_id"],
        network_name=state["network_name"],
        repo_path=state["repo_path"]
    )
    
    # 1. Apply patch using patcher
    # In full app, Role 2 connects patcher here.
    # For now, we just simulate running tests against whatever state exists.
    
    test_command = state.get("test_command", "pytest")
    if not test_command:
        test_command = "pytest"
        
    res = run_untrusted_command(sandbox, test_command, cancel_event)
    
    passed = (res["returncode"] == 0)
    
    return {
        "validation_passed": passed,
        "validation_error": res["stderr"] if not passed else "",
        "logs": [f"Validation run: passed={passed}"]
    }

def success(state: AgentState, config: RunnableConfig):
    return {
        "status": "success",
        "logs": ["Job completed successfully"]
    }

def failed(state: AgentState, config: RunnableConfig):
    return {
        "status": "failed",
        "logs": ["Job failed to fix issue"]
    }

def cleanup(state: AgentState, config: RunnableConfig):
    cleanup_sandbox(state["job_id"])
    return {
        "logs": ["Cleaned up sandbox"]
    }

def after_validate(state: AgentState):
    if state.get("validation_passed", False):
        return "success"
    if state.get("attempt", 0) >= state.get("max_attempts", 3):
        return "failed"
    return "generate_patch"

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("ingest", ingest)
    workflow.add_node("setup_sandbox", setup_sandbox_node)
    workflow.add_node("index_repo", index_repo)
    workflow.add_node("reproduce", reproduce)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_patch", generate_patch)
    workflow.add_node("validate", validate)
    workflow.add_node("success", success)
    workflow.add_node("failed", failed)
    workflow.add_node("cleanup", cleanup)
    
    workflow.set_entry_point("ingest")
    
    workflow.add_edge("ingest", "setup_sandbox")
    workflow.add_edge("setup_sandbox", "index_repo")
    workflow.add_edge("index_repo", "reproduce")
    workflow.add_edge("reproduce", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_patch")
    workflow.add_edge("generate_patch", "validate")
    
    workflow.add_conditional_edges("validate", after_validate)
    
    workflow.add_edge("success", "cleanup")
    workflow.add_edge("failed", "cleanup")
    
    workflow.add_edge("cleanup", END)
    
    return workflow.compile()
