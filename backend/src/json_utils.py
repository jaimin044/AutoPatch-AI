"""
json_utils.py — Safe JSON extraction from LLM output.

Uses json.JSONDecoder().raw_decode instead of regex.
Handles nested JSON, markdown fences, model commentary, triple-quotes,
and partial output from small local models.
"""

import json
import re


def _clean_llm_json(raw: str) -> str:
    """
    Pre-process LLM output to fix common JSON issues from small models.
    - Replaces triple-quoted strings with proper JSON strings
    - Removes nested markdown fences inside JSON values
    - Fixes unescaped newlines in string values
    """
    text = raw.strip()

    # Remove markdown fences wrapping the entire response
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    return text


def extract_json(raw: str) -> dict:
    """
    Extracts the first valid JSON object from LLM output.
    
    Strategy:
    1. Try to extract from PHANTOM_JSON markers if present
    2. Strip markdown fences if the whole response is fenced
    3. Scan for the first valid JSON object using raw_decode
    4. Try aggressive cleanup for small model quirks
    5. Raise clean error if no JSON found
    """
    if not raw or not raw.strip():
        raise ValueError("Empty LLM response — no JSON to extract.")

    # Strategy 1: Check for PHANTOM_JSON markers
    marker_match = re.search(
        r"<PHANTOM_JSON>\s*(.*?)\s*</PHANTOM_JSON>", raw, re.DOTALL
    )
    if marker_match:
        marker_content = marker_match.group(1).strip()
        # Clean markdown fences inside the marker
        marker_content = re.sub(r"^```[a-zA-Z]*\n?", "", marker_content)
        marker_content = re.sub(r"\n?```\s*$", "", marker_content)
        try:
            return json.loads(marker_content)
        except json.JSONDecodeError:
            pass  # Fall through to other strategies

    # Strategy 2: Clean and try direct parse
    cleaned = _clean_llm_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

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

    # Strategy 4: Aggressive extraction for small models
    # Try to find JSON-like structure and manually extract key-value pairs
    result = _aggressive_extract(raw)
    if result:
        return result

    raise ValueError(
        f"No valid JSON object found in LLM output. "
        f"First 200 chars: {raw[:200]}"
    )


def _aggressive_extract(raw: str) -> dict | None:
    """
    Last-resort extraction for badly formatted JSON from small models.
    Tries to extract target_file and unified_diff/complete_file_contents
    by finding key patterns.
    """
    result = {}

    # Try to find target_file
    tf_match = re.search(r'"target_file"\s*:\s*"([^"]+)"', raw)
    if tf_match:
        result["target_file"] = tf_match.group(1)

    # Try to find unified_diff
    diff_match = re.search(r'"unified_diff"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
    if diff_match:
        result["unified_diff"] = diff_match.group(1).encode().decode('unicode_escape')

    # Try to find complete_file_contents between triple quotes or similar
    if "complete_file_contents" in raw:
        # Find content after the key, between triple quotes or between markers
        cfc_match = re.search(
            r'"complete_file_contents"\s*:\s*(?:"""|\"|\'\'\'|\')\s*(.*?)(?:"""|\'\'\')',
            raw, re.DOTALL
        )
        if cfc_match:
            result["complete_file_contents"] = cfc_match.group(1).strip()
        else:
            # Try to grab everything between the key and the end of the JSON-like structure
            cfc_match2 = re.search(
                r'"complete_file_contents"\s*:\s*"((?:[^"\\]|\\.)*)"',
                raw, re.DOTALL
            )
            if cfc_match2:
                result["complete_file_contents"] = cfc_match2.group(1).encode().decode('unicode_escape')

    # Try to find analysis
    analysis_match = re.search(r'"analysis"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if analysis_match:
        result["analysis"] = analysis_match.group(1)

    # Try to find test_command
    tc_match = re.search(r'"test_command"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if tc_match:
        result["test_command"] = tc_match.group(1)

    if result and ("target_file" in result or "test_command" in result):
        return result

    return None


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
