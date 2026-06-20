"""
patcher.py — Patch application with safety and fallback strategies.

Responsibilities:
- Strip markdown fences from diffs
- Path traversal protection
- Write temp patch file
- Try patch apply strategies (git apply, --3way, --ignore-whitespace)
- Rollback failed attempts
- Full-file replacement fallback
"""

import os
import tempfile
import re
from .subprocesses import run_cancellable_subprocess
import threading


def strip_diff_fences(diff_text: str) -> str:
    """
    Remove markdown code fences wrapping a diff.
    Handles ```diff, ```patch, ``` etc.
    """
    text = diff_text.strip()

    # Remove opening fence with optional language tag
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)

    return text.strip()


def validate_path(repo_path: str, relative_path: str) -> str:
    """
    Validates that a relative path resolves within the repo root.
    Returns the absolute path if safe, raises ValueError if traversal detected.
    """
    # Normalize the repo path
    repo_abs = os.path.abspath(repo_path)
    # Resolve the target
    full_path = os.path.abspath(os.path.join(repo_path, relative_path))

    if not full_path.startswith(repo_abs + os.sep) and full_path != repo_abs:
        raise ValueError(
            f"Path traversal detected: '{relative_path}' resolves outside repo root."
        )

    return full_path


def apply_patch(
    repo_path: str,
    diff_text: str,
    cancel_event: threading.Event,
    timeout: int = 30,
) -> dict:
    """
    Attempts to apply a unified diff patch using multiple strategies.
    
    Strategy order:
    1. git apply
    2. git apply --3way
    3. git apply --ignore-whitespace
    
    Returns dict with 'success' bool and 'message' str.
    """
    cleaned_diff = strip_diff_fences(diff_text)

    if not cleaned_diff:
        return {"success": False, "message": "Empty diff after stripping fences."}

    # Write diff to a temp file
    patch_file = None
    try:
        patch_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, dir=repo_path
        )
        patch_file.write(cleaned_diff)
        patch_file.flush()
        patch_file.close()
        patch_path = patch_file.name

        strategies = [
            (["git", "apply", patch_path], "git apply"),
            (["git", "apply", "--3way", patch_path], "git apply --3way"),
            (
                ["git", "apply", "--ignore-whitespace", patch_path],
                "git apply --ignore-whitespace",
            ),
        ]

        for cmd, strategy_name in strategies:
            result = run_cancellable_subprocess(
                cmd, timeout, cancel_event, cwd=repo_path
            )
            if result["returncode"] == 0:
                return {
                    "success": True,
                    "message": f"Patch applied successfully with {strategy_name}.",
                }
            
            # Rollback any partial/failed changes before trying the next strategy
            rollback_changes(repo_path, cancel_event, timeout)

        # All strategies failed
        last_stderr = result["stderr"] if result else "unknown error"
        return {
            "success": False,
            "message": f"All patch strategies failed. Last error: {last_stderr}",
        }

    finally:
        # Clean up temp patch file
        if patch_file and os.path.exists(patch_file.name):
            try:
                os.unlink(patch_file.name)
            except OSError:
                pass


def apply_full_replacement(
    repo_path: str,
    target_file: str,
    complete_contents: str,
) -> dict:
    """
    Full-file replacement fallback.
    Used when unified diff application repeatedly fails.
    
    Validates path safety before writing.
    """
    try:
        full_path = validate_path(repo_path, target_file)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    # Ensure target directory exists
    target_dir = os.path.dirname(full_path)
    if not os.path.exists(target_dir):
        return {
            "success": False,
            "message": f"Target directory does not exist: {target_dir}",
        }

    # Check that the file already exists (don't create random new files)
    if not os.path.exists(full_path):
        return {
            "success": False,
            "message": f"Target file does not exist: {target_file}. "
                       f"Refusing to create new files via replacement.",
        }

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(complete_contents)
        return {
            "success": True,
            "message": f"Full-file replacement applied to {target_file}.",
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to write file: {e}"}


def apply_search_replace(
    repo_path: str,
    target_file: str,
    search_text: str,
    replace_text: str,
) -> dict:
    """
    Search-and-replace patching fallback.
    Finds exact search_text in the file and replaces it with replace_text.
    """
    try:
        full_path = validate_path(repo_path, target_file)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    if not os.path.exists(full_path):
        return {"success": False, "message": f"File does not exist: {target_file}"}

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        if search_text not in content:
            # Fallback: ignore trailing/leading whitespace mismatches
            if search_text.strip() in content:
                content = content.replace(search_text.strip(), replace_text.strip())
            else:
                return {
                    "success": False, 
                    "message": "Search block not found in target file."
                }
        else:
            content = content.replace(search_text, replace_text)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "message": f"Search-and-replace applied to {target_file}.",
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to perform search/replace: {e}"}




def rollback_changes(repo_path: str, cancel_event: threading.Event, timeout: int = 15) -> dict:
    """
    Rolls back any uncommitted changes in the repo using git checkout.
    Called between patch attempts to ensure clean state.
    """
    cmd = ["git", "checkout", "--", "."]
    result = run_cancellable_subprocess(cmd, timeout, cancel_event, cwd=repo_path)

    if result["returncode"] == 0:
        return {"success": True, "message": "Rollback successful."}
    else:
        return {"success": False, "message": f"Rollback failed: {result['stderr']}"}
