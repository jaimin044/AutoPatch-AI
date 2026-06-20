"""
llm.py — LLM provider interface for PHANTOM Lite.

Primary: Ollama (local, free)
Optional fallback: OpenAI-compatible API

Functions:
- analyze_issue: Predict test command and target file from issue text
- generate_patch: Generate a unified diff patch from context
- generate_replacement: Generate full-file replacement as last resort
"""

import httpx
from .config import settings
from .json_utils import extract_json


# ─── Core Call Functions ───────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """Calls local Ollama API and returns raw text response."""
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    response = httpx.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["response"]


def _call_openai(prompt: str) -> str:
    """Calls OpenAI-compatible API as fallback."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    response = httpx.post(url, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _call_llm(prompt: str) -> str:
    """Routes to the configured LLM provider."""
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return _call_ollama(prompt)
    elif provider == "openai":
        return _call_openai(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ─── Prompts ───────────────────────────────────────────────────────────

ANALYZE_ISSUE_PROMPT = """You are a debugging assistant analyzing a bug report for a Python repository.

Repository summary:
{repo_summary}

Bug report:
{issue_text}

Analyze this issue. Predict the test command and the SOURCE file (not the test file) that contains the bug.

Return ONLY valid JSON. No markdown. No commentary.

{{"test_command": "pytest tests/test_example.py", "target_file": "example.py", "analysis": "brief description"}}
"""

GENERATE_PATCH_PROMPT = """You are a Python developer fixing a bug.

Bug report:
{issue_text}

Failing test output:
{failing_output}

Source files:
{retrieved_context}

{retry_context}

IMPORTANT RULES:
1. Fix the SOURCE code file, NOT the test file. Tests describe the EXPECTED behavior.
2. The test expects certain behavior — modify the source code to match what the test expects.
3. Return a search and replace block to apply the fix.

Return ONLY this JSON (no markdown, no explanation):
{{"target_file": "source_file.py", "search_block": "exact lines to replace", "replace_block": "the fixed lines"}}
"""

GENERATE_REPLACEMENT_PROMPT = """You are a Python developer. Fix this file:

Bug report:
{issue_text}

File to fix: {target_file}
Current contents:
{target_code}

Fix the bug. Return a search and replace block containing exactly the code that needs to change.

Return ONLY this JSON (no markdown, no explanation):
{{"target_file": "{target_file}", "search_block": "exact lines to replace", "replace_block": "the fixed lines"}}
"""


# ─── Public API ────────────────────────────────────────────────────────

def analyze_issue(issue_text: str, repo_summary: str) -> dict:
    """
    Analyzes an issue to predict test command and target file.
    
    Returns:
        dict with keys: test_command, target_file, analysis
    """
    prompt = ANALYZE_ISSUE_PROMPT.format(
        issue_text=issue_text,
        repo_summary=repo_summary,
    )
    raw = _call_llm(prompt)
    return extract_json(raw)


def generate_patch(
    issue_text: str,
    failing_output: str,
    retrieved_context: str,
    attempt: int = 1,
    previous_error: str = "",
) -> dict:
    """
    Generates a fix for the bug. With small models, requests full-file
    replacement directly instead of unified diffs (more reliable).
    
    Returns:
        dict with keys: target_file, complete_file_contents (or unified_diff)
    """
    retry_context = ""
    if attempt > 1 and previous_error:
        retry_context = (
            f"IMPORTANT: This is attempt {attempt}. "
            f"Previous fix failed with error:\n{previous_error}\n"
            f"Generate a DIFFERENT fix this time."
        )

    prompt = GENERATE_PATCH_PROMPT.format(
        issue_text=issue_text,
        failing_output=failing_output,
        retrieved_context=retrieved_context,
        retry_context=retry_context,
    )
    raw = _call_llm(prompt)
    return extract_json(raw)


def generate_replacement(
    issue_text: str,
    failing_output: str,
    retrieved_context: str,
    target_file: str,
    target_code: str = "",
) -> dict:
    """
    Generates a full-file replacement when patch application keeps failing.
    
    Returns:
        dict with keys: target_file, complete_file_contents
    """
    prompt = GENERATE_REPLACEMENT_PROMPT.format(
        issue_text=issue_text,
        failing_output=failing_output,
        target_file=target_file,
        target_code=target_code,
    )
    raw = _call_llm(prompt)
    return extract_json(raw)
