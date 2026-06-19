"""
context_builder.py — Builds compact LLM context from retrieved files.

Rules (from master plan):
- Include issue text
- Include failing output
- Include retrieved files with reasons
- Cap total lines (max 400)
- Cap per-file lines (max 120)
- Max 5 files
"""

import os


# Context limits
MAX_FILES = 5
MAX_TOTAL_LINES = 400
MAX_LINES_PER_FILE = 120


def _read_file_content(filepath: str, max_lines: int = MAX_LINES_PER_FILE) -> str:
    """Read file content, capped at max_lines."""
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated after {max_lines} lines)")
                    break
                lines.append(line.rstrip())
    except Exception as e:
        lines.append(f"(Could not read file: {e})")
    return "\n".join(lines)


def build_context(
    issue_text: str,
    failing_output: str,
    retrieved_files: list[dict],
    repo_path: str,
) -> str:
    """
    Build a compact context string for the LLM.

    Args:
        issue_text: The bug report / issue description
        failing_output: stdout/stderr from the failing test run
        retrieved_files: List of dicts with 'path', 'score', 'reason'
        repo_path: Absolute path to the cloned repo

    Returns:
        Formatted context string ready for the LLM prompt
    """
    sections = []
    total_lines = 0

    # Section 1: Issue
    sections.append("=== Issue ===")
    sections.append(issue_text.strip())
    sections.append("")
    total_lines += len(issue_text.strip().splitlines()) + 2

    # Section 2: Failing output (capped)
    if failing_output:
        sections.append("=== Failing Test Output ===")
        fail_lines = failing_output.strip().splitlines()
        if len(fail_lines) > 50:
            # Keep first 20 and last 30 lines (most useful: header + traceback)
            fail_lines = fail_lines[:20] + ["... (truncated) ..."] + fail_lines[-30:]
        sections.append("\n".join(fail_lines))
        sections.append("")
        total_lines += len(fail_lines) + 2

    # Section 3: Retrieved files
    sections.append("=== Retrieved Source Files ===")
    sections.append("")

    files_to_include = retrieved_files[:MAX_FILES]

    for entry in files_to_include:
        filepath = entry["path"]
        reason = entry.get("reason", "relevant")
        score = entry.get("score", 0)

        # Check if we have budget
        if total_lines >= MAX_TOTAL_LINES:
            sections.append(f"(Skipping remaining files — context limit reached)")
            break

        # Calculate how many lines we can afford for this file
        remaining_budget = MAX_TOTAL_LINES - total_lines
        lines_for_this_file = min(MAX_LINES_PER_FILE, remaining_budget - 5)

        if lines_for_this_file < 10:
            sections.append(f"(Skipping {filepath} — context limit reached)")
            break

        # Read the file
        full_path = os.path.join(repo_path, filepath)
        content = _read_file_content(full_path, max_lines=lines_for_this_file)
        content_line_count = len(content.splitlines())

        sections.append(f"FILE: {filepath}")
        sections.append(f"Reason: {reason} (score: {score})")
        sections.append(f"```python")
        sections.append(content)
        sections.append(f"```")
        sections.append("")

        total_lines += content_line_count + 5  # 5 for headers/fences

    return "\n".join(sections)


def get_retrieved_file_paths(retrieved_files: list[dict]) -> list[str]:
    """Extract just the file paths from retrieved files list."""
    return [f["path"] for f in retrieved_files]
