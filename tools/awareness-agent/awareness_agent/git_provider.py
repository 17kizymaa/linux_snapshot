from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .redaction import redact_text


def _git(cwd: Path, args: list[str], *, redact: bool = True) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""

    if proc.returncode != 0:
        return ""

    out = proc.stdout.strip()
    return redact_text(out) if redact else out


def _infer_stack(root: Path) -> dict[str, str | None]:
    language: str | None = None
    framework: str | None = None

    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists() or any(root.glob("*.py")):
        language = "python"

    if (root / "package.json").exists():
        language = "javascript/typescript" if language is None else f"{language}+javascript"

    if (root / "docker-compose.yml").exists() or (root / "compose.yml").exists():
        framework = "docker-compose"

    return {"language": language, "framework": framework}


def collect_project(cwd: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    current = Path(cwd or os.getcwd()).expanduser().resolve()

    root_text = _git(current, ["rev-parse", "--show-toplevel"], redact=False)
    if not root_text:
        return {
            "is_git_repo": False,
            "path": str(current),
            "root": None,
            "name": current.name,
            "branch": None,
            "dirty_count": 0,
            "remotes": [],
            "recent_commits": [],
            "language": None,
            "framework": None,
        }

    root = Path(root_text).expanduser().resolve()
    branch = _git(root, ["branch", "--show-current"]) or _git(root, ["rev-parse", "--short", "HEAD"])
    remotes_text = _git(root, ["remote", "-v"])
    status_text = _git(root, ["status", "--short", "--untracked-files=no"])
    commits_text = _git(root, ["log", "-5", "--pretty=format:%h %s"])

    remotes: list[str] = []
    for line in remotes_text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            remotes.append(parts[1])

    status_lines = [line for line in status_text.splitlines() if line.strip()]
    commits = [line for line in commits_text.splitlines() if line.strip()]
    stack = _infer_stack(root)

    return {
        "is_git_repo": True,
        "path": str(current),
        "root": str(root),
        "name": root.name,
        "branch": branch or None,
        "dirty_count": len(status_lines),
        "status_sample": status_lines[:10],
        "remotes": sorted(set(remotes))[:10],
        "recent_commits": commits,
        **stack,
    }
