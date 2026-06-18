"""
json_utils.py — Safe JSON extraction from LLM output.

Uses json.JSONDecoder().raw_decode instead of regex.
Handles nested JSON, markdown fences, model commentary, and partial output.
"""

import json
import re


def extract_json(raw: str) -> dict:
    """
    Extracts the first valid JSON object from LLM output.
    
    Strategy:
    1. Try to extract from PHANTOM_JSON markers if present
    2. Strip markdown fences if the whole response is fenced
    3. Scan for the first valid JSON object using raw_decode
    4. Raise clean error if no JSON found
    """
    if not raw or not raw.strip():
        raise ValueError("Empty LLM response — no JSON to extract.")

    # Strategy 1: Check for PHANTOM_JSON markers
    marker_match = re.search(
        r"<PHANTOM_JSON>\s*(.*?)\s*</PHANTOM_JSON>", raw, re.DOTALL
    )
    if marker_match:
        try:
            return json.loads(marker_match.group(1))
        except json.JSONDecodeError:
            pass  # Fall through to other strategies

    # Strategy 2: Strip markdown fences if entire response is fenced
    stripped = raw.strip()
    if stripped.startswith("```"):
        # Remove opening fence (with optional language tag)
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        # Remove closing fence
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        stripped = stripped.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass  # Fall through to scanning

    # Strategy 3: Scan for first valid JSON object using raw_decode
    decoder = json.JSONDecoder()
    text = raw.strip()

    for i in range(len(text)):
        if text[i] == '{':
            try:
                obj, end_idx = decoder.raw_decode(text, i)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue

    raise ValueError(
        f"No valid JSON object found in LLM output. "
        f"First 200 chars: {raw[:200]}"
    )


def safe_get(data: dict, key: str, expected_type: type = str, default=None):
    """
    Safely retrieves a key from a dict with type checking.
    Returns default if key is missing or wrong type.
    """
    value = data.get(key, default)
    if value is None:
        return default
    if not isinstance(value, expected_type):
        return default
    return value
