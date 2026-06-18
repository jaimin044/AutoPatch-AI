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

ANALYZE_ISSUE_PROMPT = """You are an expert debugging assistant analyzing a bug report for a Python repository.

Repository summary:
{repo_summary}

Bug report / Issue:
{issue_text}

Your task: Analyze this issue and predict:
1. The test command to reproduce the bug (usually `pytest` or a specific test file)
2. The likely target file that contains the bug
3. A brief analysis of what the bug might be

Return ONLY valid JSON with no markdown, no commentary, no explanation outside the JSON.

Return between these markers:
<PHANTOM_JSON>
{{
  "test_command": "pytest tests/test_example.py",
  "target_file": "src/example.py",
  "analysis": "Brief description of the suspected bug"
}}
</PHANTOM_JSON>
"""

GENERATE_PATCH_PROMPT = """You are an expert Python developer fixing a bug.

Bug report:
{issue_text}

Failing test output:
{failing_output}

Retrieved source files:
{retrieved_context}

{retry_context}

Your task: Generate a MINIMAL unified diff patch to fix this bug.

Rules:
- Generate a standard unified diff (like `git diff` output)
- Paths must be relative to the repository root
- Paths must EXACTLY match one of the retrieved file paths above
- Make the MINIMAL change needed to fix the bug
- Do NOT add unnecessary imports or changes
- Do NOT include markdown fences
- Do NOT include explanation outside the JSON

Return ONLY valid JSON:

<PHANTOM_JSON>
{{
  "target_file": "path/to/file.py",
  "unified_diff": "--- a/path/to/file.py\\n+++ b/path/to/file.py\\n@@ -line,count +line,count @@\\n context\\n-old line\\n+new line\\n context"
}}
</PHANTOM_JSON>
"""

GENERATE_REPLACEMENT_PROMPT = """You are an expert Python developer fixing a bug.

Bug report:
{issue_text}

Failing test output:
{failing_output}

The file that needs to be fixed:
File: {target_file}
Current contents:
```python
{target_code}
```

The diff-based patch failed to apply. Generate the COMPLETE corrected file contents instead.

Rules:
- Return the ENTIRE file contents, not just the changed part
- Fix the bug with minimal changes
- Keep all existing code that doesn't need changing
- Do NOT include markdown fences in the file contents
- Do NOT include explanation outside the JSON

Return ONLY valid JSON:

<PHANTOM_JSON>
{{
  "target_file": "{target_file}",
  "complete_file_contents": "...entire corrected file here..."
}}
</PHANTOM_JSON>
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
    Generates a unified diff patch for the bug.
    
    Returns:
        dict with keys: target_file, unified_diff
    """
    retry_context = ""
    if attempt > 1 and previous_error:
        retry_context = (
            f"IMPORTANT: This is attempt {attempt}. "
            f"Previous patch failed with error:\n{previous_error}\n"
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
