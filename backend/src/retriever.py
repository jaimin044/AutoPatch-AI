"""
retriever.py — Retrieves relevant files from the repo index for Repo-RAG.

Scoring system (from master plan):
  +6  exact file path from traceback
  +5  filename mentioned in issue text
  +5  failing test file
  +4  function/class name match
  +3  exception name match
  +2  import relationship
  +1  keyword overlap

Returns top 3-5 files with scores and reasons.
"""

import re
import os


def _extract_traceback_paths(text: str) -> list[str]:
    """
    Extract file paths from Python tracebacks.
    Matches patterns like: File "path/to/file.py", line 10
    Also matches bare paths like: path/to/file.py:10
    """
    paths = []

    # Standard traceback format
    tb_pattern = re.findall(r'File "([^"]+\.py)"', text)
    paths.extend(tb_pattern)

    # Also match path:line patterns
    pathline_pattern = re.findall(r'(\S+\.py):\d+', text)
    paths.extend(pathline_pattern)

    # Normalize: strip leading slashes, workspace prefixes
    normalized = []
    for p in paths:
        # Take only the relative part if it contains common project paths
        basename = os.path.basename(p)
        normalized.append(basename)
        # Also keep the path as-is for exact matching
        normalized.append(p)

    return list(set(normalized))


def _extract_exception_names(text: str) -> list[str]:
    """Extract exception class names from text."""
    # Match patterns like: ZeroDivisionError, ValueError, etc.
    return re.findall(r'\b([A-Z][a-zA-Z]*Error|[A-Z][a-zA-Z]*Exception)\b', text)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, filtering common stop words."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "and", "but",
        "or", "not", "no", "nor", "so", "yet", "both", "each", "few", "more",
        "most", "other", "some", "such", "than", "too", "very", "just", "about",
        "it", "its", "this", "that", "these", "those", "i", "me", "my", "we",
        "our", "you", "your", "he", "him", "his", "she", "her", "they", "them",
        "their", "what", "which", "who", "when", "where", "why", "how", "all",
        "if", "then", "else", "while", "file", "function", "def", "class",
        "import", "return", "none", "true", "false",
    }
    # Split on non-alphanumeric, filter short and stop words
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
    return {w for w in words if len(w) > 2 and w not in stop_words}


def retrieve_relevant_files(
    repo_index: list[dict],
    issue_text: str,
    failing_output: str = "",
    top_k: int = 5,
) -> list[dict]:
    """
    Score and rank files from the repo index based on relevance
    to the issue text and failing test output.

    Returns list of dicts with: path, score, reason
    """
    combined_text = f"{issue_text}\n{failing_output}"

    # Pre-extract signals
    tb_paths = _extract_traceback_paths(combined_text)
    exception_names = _extract_exception_names(combined_text)
    keywords = _extract_keywords(combined_text)

    # Extract filenames mentioned in issue text
    mentioned_files = re.findall(r'\b([\w/]+\.py)\b', issue_text)
    mentioned_basenames = [os.path.basename(f) for f in mentioned_files]

    scored_files = []

    for entry in repo_index:
        score = 0.0
        reasons = []
        filepath = entry["path"]
        basename = os.path.basename(filepath)

        # +6: exact file path from traceback
        for tb_path in tb_paths:
            if tb_path == filepath or tb_path == basename:
                score += 6
                reasons.append("traceback points here")
                break

        # +5: filename mentioned in issue text
        if basename in mentioned_basenames or filepath in mentioned_files:
            score += 5
            reasons.append(f"file mentioned in issue")

        # +5: failing test file
        if entry.get("is_test") and failing_output:
            # Check if this test file appears in failing output
            if basename in failing_output or filepath in failing_output:
                score += 5
                reasons.append("failing test file")

        # +4: function/class name match
        file_symbols = entry.get("functions", []) + entry.get("classes", [])
        for symbol in file_symbols:
            if symbol.lower() in combined_text.lower():
                score += 4
                reasons.append(f"symbol '{symbol}' referenced")
                break  # Only count once per file

        # +3: exception name match
        for exc in exception_names:
            file_content_hint = " ".join(entry.get("first_lines", []))
            if exc.lower() in file_content_hint.lower():
                score += 3
                reasons.append(f"exception '{exc}' found")
                break

        # +2: import relationship
        file_imports = entry.get("imports", [])
        for imp in file_imports:
            # Check if any other mentioned file is imported by this file
            for mf in mentioned_basenames:
                module_name = mf.replace(".py", "")
                if module_name in imp:
                    score += 2
                    reasons.append(f"imports '{module_name}'")
                    break
            if reasons and "imports" in reasons[-1]:
                break

        # +1: keyword overlap
        file_text = " ".join([
            filepath,
            " ".join(entry.get("functions", [])),
            " ".join(entry.get("classes", [])),
            " ".join(entry.get("first_lines", [])),
        ]).lower()
        file_keywords = _extract_keywords(file_text)
        overlap = keywords & file_keywords
        if overlap:
            bonus = min(len(overlap) * 0.5, 3)  # Cap keyword bonus at 3
            score += bonus
            if bonus >= 1:
                reasons.append(f"keyword overlap ({len(overlap)} matches)")

        if score > 0:
            scored_files.append({
                "path": filepath,
                "score": round(score, 1),
                "reason": "; ".join(reasons) if reasons else "keyword match",
                "is_test": entry.get("is_test", False),
            })

    # Sort by score descending, return top_k
    scored_files.sort(key=lambda x: x["score"], reverse=True)
    return scored_files[:top_k]
