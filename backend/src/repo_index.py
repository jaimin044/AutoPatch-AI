"""
repo_index.py — Repository indexer for Repo-RAG.

Scans a cloned repo and builds a structured index of every relevant file:
- file path, extension, size
- imports
- function/class names (Python files via ast)
- first few lines
- whether it is a test file

Skips: .git, venv, node_modules, dist, build, __pycache__, files > 100KB, binary files.
"""

import os
import ast


# Directories to skip during indexing
SKIP_DIRS = {
    ".git", "venv", ".venv", "node_modules", "dist",
    "build", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    "egg-info", ".eggs",
}

# Max file size to index (100 KB)
MAX_FILE_SIZE = 100 * 1024

# Extensions we consider source code
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rb", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".rst",
}


def _is_binary(filepath: str) -> bool:
    """Check if a file is binary by reading first 1024 bytes."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
        return False
    except Exception:
        return True


def _is_test_file(filepath: str) -> bool:
    """Determine if a file is a test file based on naming conventions."""
    basename = os.path.basename(filepath).lower()
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or "/tests/" in filepath.replace("\\", "/")
        or "/test/" in filepath.replace("\\", "/")
    )


def _extract_python_symbols(filepath: str) -> dict:
    """
    Use Python ast to extract function names, class names, and imports
    from a .py file.
    """
    symbols = {"functions": [], "classes": [], "imports": []}
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                symbols["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                symbols["classes"].append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                symbols["imports"].append(module)
    except (SyntaxError, UnicodeDecodeError, Exception):
        pass

    return symbols


def _read_first_lines(filepath: str, n: int = 10) -> list[str]:
    """Read the first n lines of a file."""
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                lines.append(line.rstrip())
    except Exception:
        pass
    return lines


def index_repository(repo_path: str) -> list[dict]:
    """
    Walk the repository and build a structured index.

    Each entry contains:
    - path: relative path from repo root
    - extension: file extension
    - size: file size in bytes
    - is_test: whether it's a test file
    - imports: list of import strings (Python only)
    - functions: list of function names (Python only)
    - classes: list of class names (Python only)
    - first_lines: first 10 lines of the file
    """
    index = []
    repo_path = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(repo_path):
        # Filter out skip directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")]

        for filename in files:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, repo_path)

            # Skip large files
            try:
                size = os.path.getsize(filepath)
            except OSError:
                continue
            if size > MAX_FILE_SIZE:
                continue

            # Get extension
            _, ext = os.path.splitext(filename)
            ext = ext.lower()

            # Skip non-code and binary files
            if ext not in CODE_EXTENSIONS:
                continue
            if _is_binary(filepath):
                continue

            entry = {
                "path": rel_path,
                "extension": ext,
                "size": size,
                "is_test": _is_test_file(rel_path),
                "imports": [],
                "functions": [],
                "classes": [],
                "first_lines": _read_first_lines(filepath),
            }

            # Extract Python symbols
            if ext == ".py":
                symbols = _extract_python_symbols(filepath)
                entry["imports"] = symbols["imports"]
                entry["functions"] = symbols["functions"]
                entry["classes"] = symbols["classes"]

            index.append(entry)

    return index


def get_repo_summary(index: list[dict]) -> str:
    """
    Generate a brief text summary of the repo for LLM context.
    """
    file_count = len(index)
    test_count = sum(1 for f in index if f["is_test"])
    source_count = file_count - test_count
    extensions = set(f["extension"] for f in index)

    lines = [
        f"Repository contains {file_count} files ({source_count} source, {test_count} test).",
        f"Languages/extensions: {', '.join(sorted(extensions))}",
        "Files:",
    ]
    for f in index:
        marker = " [TEST]" if f["is_test"] else ""
        funcs = ", ".join(f["functions"][:5]) if f["functions"] else ""
        classes = ", ".join(f["classes"][:3]) if f["classes"] else ""
        detail = ""
        if funcs:
            detail += f"  functions: {funcs}"
        if classes:
            detail += f"  classes: {classes}"
        lines.append(f"  - {f['path']}{marker}{detail}")

    return "\n".join(lines)
