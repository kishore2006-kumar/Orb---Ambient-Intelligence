"""Static security tests — AST analysis and file content checks."""

from __future__ import annotations

import ast
import re
from pathlib import Path

# Root of the project
_ROOT = Path(__file__).parent.parent.parent


def _py_files(*dirs: str):  # type: ignore[return]
    for d in dirs:
        yield from (_ROOT / d).rglob("*.py")


def test_no_shell_true() -> None:
    """No call in hub/ or agent_windows/ should use shell=True."""
    violations: list[str] = []
    for path in _py_files("hub", "agent_windows"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        violations.append(f"{path}:{node.lineno}")
    assert violations == [], f"shell=True found: {violations}"


def test_no_eval_or_exec() -> None:
    """No eval/exec calls in hub/ or agent_windows/."""
    violations: list[str] = []
    for path in _py_files("hub", "agent_windows"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in ("eval", "exec"):
                    violations.append(f"{path}:{node.lineno}")
    assert violations == [], f"eval/exec found: {violations}"


def test_env_ignored_in_gitignore() -> None:
    gitignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore


def test_no_secret_like_strings() -> None:
    """Scan source files for patterns resembling real secrets."""
    patterns = [
        re.compile(r"sk_[0-9a-f]{20,}"),
        re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ]
    exclude_paths = {"tests", ".env.example"}
    extensions = {".py", ".json", ".md", ".yml"}
    violations: list[str] = []

    for path in _ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        # Exclude test files and .env.example
        rel = path.relative_to(_ROOT)
        parts = rel.parts
        if any(p in exclude_paths for p in parts):
            continue
        if ".git" in parts:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for pat in patterns:
            if pat.search(content):
                violations.append(str(path))
                break

    assert violations == [], f"Secret-like strings found: {violations}"
