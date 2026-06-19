"""
orchestrator.py — LangGraph workflow for PHANTOM Lite.

Graph: ingest -> setup_sandbox -> index_repo -> reproduce -> retrieve_context
       -> generate_patch -> validate -> success/retry/failed -> cleanup
"""

import os
import threading
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

from .state import AgentState
from .sandbox import create_sandbox, install_dependencies, disable_network, cleanup_sandbox, run_untrusted_command, Sandbox
from .patcher import apply_patch, apply_full_replacement, rollback_changes
from .repo_index import index_repository, get_repo_summary
from .retriever import retrieve_relevant_files
from .context_builder import build_context
from .llm import analyze_issue, generate_patch as llm_generate_patch, generate_replacement


def get_cancel_event(config: RunnableConfig) -> threading.Event:
    return config.get("configurable", {}).get("cancel_event", threading.Event())


# ─── Node: ingest ──────────────────────────────────────────────────────

def ingest(state: AgentState, config: RunnableConfig):
    """Analyze the issue and predict test command using LLM."""
    cancel_event = get_cancel_event(config)
    if cancel_event.is_set():
        return {"logs": ["Cancelled during ingest"]}

    # We'll do a quick analysis once repo is indexed.
    # For now, just log the start.
    return {
        "logs": ["Ingested issue: " + state["issue_text"][:100] + "..."]
    }


# ─── Node: setup_sandbox ──────────────────────────────────────────────

def setup_sandbox_node(state: AgentState, config: RunnableConfig):
    """Create Docker sandbox, clone repo, install deps, disable network."""
    cancel_event = get_cancel_event(config)
    job_id = state["job_id"]
    repo_url = state["repo_url"]

    sandbox = create_sandbox(job_id, repo_url, cancel_event)

    logs = ["Sandbox created, installing dependencies..."]

    install_dependencies(sandbox, cancel_event)
    logs.append("Dependencies installed, disabling network...")

    disable_network(sandbox)
    logs.append("Network disabled — sandbox is now isolated")

    return {
        "sandbox_id": sandbox.container_id,
        "network_name": sandbox.network_name,
        "repo_path": sandbox.repo_path,
        "logs": logs,
    }


# ─── Node: index_repo ─────────────────────────────────────────────────

def index_repo(state: AgentState, config: RunnableConfig):
    """Scan the cloned repo and build the structured index."""
    cancel_event = get_cancel_event(config)
    if cancel_event.is_set():
        return {"logs": ["Cancelled during indexing"]}

    repo_path = state["repo_path"]
    index = index_repository(repo_path)

    # Use LLM to analyze issue and predict test command
    repo_summary = get_repo_summary(index)
    try:
        analysis = analyze_issue(state["issue_text"], repo_summary)
        test_command = analysis.get("test_command", "pytest")
        target_file = analysis.get("target_file", "")
        logs = [
            f"Indexed {len(index)} files",
            f"LLM analysis: {analysis.get('analysis', 'N/A')}",
            f"Predicted test command: {test_command}",
        ]
    except Exception as e:
        test_command = "pytest"
        target_file = ""
        logs = [
            f"Indexed {len(index)} files",
            f"LLM analysis failed ({e}), defaulting to pytest",
        ]

    return {
        "repo_index": index,
        "test_command": test_command,
        "target_file": target_file,
        "logs": logs,
    }


# ─── Node: reproduce ──────────────────────────────────────────────────

def reproduce(state: AgentState, config: RunnableConfig):
    """Run the test command to reproduce the failing test."""
    cancel_event = get_cancel_event(config)
    sandbox = Sandbox(
        job_id=state["job_id"],
        container_id=state["sandbox_id"],
        network_name=state["network_name"],
        repo_path=state["repo_path"],
    )

    test_command = state.get("test_command") or "pytest"
    res = run_untrusted_command(sandbox, test_command, cancel_event)

    combined_output = res["stdout"] + "\n" + res["stderr"]

    return {
        "baseline_error": combined_output if res["returncode"] != 0 else "",
        "logs": [
            f"Reproduce: ran '{test_command}' — returncode={res['returncode']}",
            f"Output preview: {combined_output[:200]}...",
        ],
    }


# ─── Node: retrieve_context ───────────────────────────────────────────

def retrieve_context(state: AgentState, config: RunnableConfig):
    """Use Repo-RAG to retrieve relevant files for patch generation."""
    cancel_event = get_cancel_event(config)
    if cancel_event.is_set():
        return {"logs": ["Cancelled during retrieval"]}

    repo_index = state.get("repo_index", [])
    issue_text = state["issue_text"]
    baseline_error = state.get("baseline_error", "")

    retrieved = retrieve_relevant_files(repo_index, issue_text, baseline_error)

    # Build context pack
    context = build_context(
        issue_text=issue_text,
        failing_output=baseline_error,
        retrieved_files=retrieved,
        repo_path=state["repo_path"],
    )

    retrieved_paths = [f["path"] for f in retrieved]
    logs = [f"Retrieved {len(retrieved)} relevant files:"]
    for r in retrieved:
        logs.append(f"  - {r['path']} (score: {r['score']}, reason: {r['reason']})")

    return {
        "retrieved_files": retrieved_paths,
        "retrieved_context": context,
        "logs": logs,
    }


# ─── Node: generate_patch ─────────────────────────────────────────────

def generate_patch(state: AgentState, config: RunnableConfig):
    """Call LLM to generate a patch using retrieved context."""
    cancel_event = get_cancel_event(config)
    if cancel_event.is_set():
        return {"logs": ["Cancelled during patch generation"]}

    attempt = state.get("attempt", 0) + 1
    previous_error = state.get("validation_error", "")

    try:
        patch_result = llm_generate_patch(
            issue_text=state["issue_text"],
            failing_output=state.get("baseline_error", ""),
            retrieved_context=state.get("retrieved_context", ""),
            attempt=attempt,
            previous_error=previous_error,
        )
        target_file = patch_result.get("target_file", "")
        unified_diff = patch_result.get("unified_diff", "")

        logs = [
            f"LLM generated patch (attempt {attempt})",
            f"Target file: {target_file}",
            f"Diff preview: {unified_diff[:150]}...",
        ]

        return {
            "attempt": attempt,
            "target_file": target_file,
            "proposed_patch": unified_diff,
            "logs": logs,
        }
    except Exception as e:
        return {
            "attempt": attempt,
            "proposed_patch": "",
            "logs": [f"Patch generation failed (attempt {attempt}): {e}"],
        }


# ─── Node: validate ───────────────────────────────────────────────────

def validate(state: AgentState, config: RunnableConfig):
    """Apply the patch, run tests, and check if the fix works."""
    cancel_event = get_cancel_event(config)
    sandbox = Sandbox(
        job_id=state["job_id"],
        container_id=state["sandbox_id"],
        network_name=state["network_name"],
        repo_path=state["repo_path"],
    )
    repo_path = state["repo_path"]

    logs = []

    # 1. Rollback any previous changes
    rollback_result = rollback_changes(repo_path, cancel_event)
    logs.append(f"Rollback: {rollback_result['message']}")

    # 2. Try to apply the patch
    proposed_patch = state.get("proposed_patch", "")
    target_file = state.get("target_file", "")
    patch_applied = False

    if proposed_patch:
        patch_result = apply_patch(repo_path, proposed_patch, cancel_event)
        logs.append(f"Patch apply: {patch_result['message']}")
        patch_applied = patch_result["success"]

    # 3. If patch failed, try full-file replacement
    if not patch_applied and target_file:
        logs.append("Patch apply failed, trying full-file replacement...")
        try:
            replacement = generate_replacement(
                issue_text=state["issue_text"],
                failing_output=state.get("baseline_error", ""),
                retrieved_context=state.get("retrieved_context", ""),
                target_file=target_file,
                target_code=_read_target_file(repo_path, target_file),
            )
            repl_file = replacement.get("target_file", target_file)
            repl_code = replacement.get("complete_file_contents", "")
            if repl_code:
                repl_result = apply_full_replacement(repo_path, repl_file, repl_code)
                logs.append(f"Replacement: {repl_result['message']}")
                patch_applied = repl_result["success"]
        except Exception as e:
            logs.append(f"Replacement generation failed: {e}")

    if not patch_applied:
        return {
            "validation_passed": False,
            "validation_error": "Could not apply any patch.",
            "logs": logs,
        }

    # 4. Run tests to validate the fix
    test_command = state.get("test_command") or "pytest"
    res = run_untrusted_command(sandbox, test_command, cancel_event)

    passed = res["returncode"] == 0
    combined_output = res["stdout"] + "\n" + res["stderr"]

    logs.append(f"Validation test: {'PASSED ✓' if passed else 'FAILED ✗'}")
    if not passed:
        logs.append(f"Test output: {combined_output[:300]}...")

    return {
        "validation_passed": passed,
        "validation_error": combined_output if not passed else "",
        "logs": logs,
    }


def _read_target_file(repo_path: str, target_file: str) -> str:
    """Read a target file's content for replacement generation."""
    full_path = os.path.join(repo_path, target_file)
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


# ─── Node: success ─────────────────────────────────────────────────────

def success(state: AgentState, config: RunnableConfig):
    return {
        "status": "success",
        "logs": ["✓ Job completed successfully — bug fixed!"],
    }


# ─── Node: failed ──────────────────────────────────────────────────────

def failed(state: AgentState, config: RunnableConfig):
    return {
        "status": "failed",
        "logs": [f"✗ Job failed after {state.get('attempt', 0)} attempts"],
    }


# ─── Node: cleanup ─────────────────────────────────────────────────────

def cleanup(state: AgentState, config: RunnableConfig):
    cleanup_sandbox(state["job_id"])
    return {"logs": ["Cleaned up sandbox"]}


# ─── Conditional Router ────────────────────────────────────────────────

def after_validate(state: AgentState):
    if state.get("validation_passed", False):
        return "success"
    if state.get("attempt", 0) >= state.get("max_attempts", 3):
        return "failed"
    return "generate_patch"


# ─── Graph Builder ─────────────────────────────────────────────────────

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
