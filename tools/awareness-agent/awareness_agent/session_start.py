from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .paths import socket_path
from .redaction import redact_text
from .store import AwarenessStore


def _socket_usable(path: Path, timeout: float = 0.5) -> bool:
    if not path.exists():
        return False
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(path))
        return True
    except OSError:
        return False


def _rpc_call(method: str, params: dict[str, Any] | None = None, timeout: float = 1.0) -> Any:
    import socket
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000),
    }
    path = socket_path()
    if not path.exists():
        raise ConnectionError(f"socket not found: {path}")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    if not data:
        raise ConnectionError("empty response from daemon")
    response = json.loads(data.decode("utf-8"))
    if response.get("error"):
        raise RuntimeError(response["error"].get("message", "unknown daemon error"))
    return response.get("result")


def build_context_snippet(
    cwd: str | None = None,
    max_chars: int = 10000,
    max_memories: int = 8,
    timeout: float = 1.0,
) -> str:
    """Build a compact, redacted awareness context snippet for SessionStart injection.

    Returns empty string if daemon is unreachable — fail closed/silent.
    """
    path = socket_path()
    if not _socket_usable(path, timeout=min(timeout, 0.5)):
        return ""

    try:
        result = _rpc_call("status", {"cwd": cwd or os.getcwd()}, timeout=timeout)
    except Exception:
        return ""

    project = result.get("current_project") or {}
    counts = result.get("counts") or {}

    lines: list[str] = []
    lines.append("<awareness-context>")

    name = project.get("name") or "unknown"
    root = project.get("root") or project.get("path") or ""
    branch = project.get("branch") or ""
    lines.append(f"Project: {redact_text(name)}")
    if root:
        lines.append(f"Root: {redact_text(root)}")
    if branch:
        lines.append(f"Branch: {redact_text(branch)}")

    language = project.get("language") or ""
    framework = project.get("framework") or ""
    if language:
        lines.append(f"Language: {redact_text(language)}")
    if framework:
        lines.append(f"Framework: {redact_text(framework)}")

    # Fetch recent memories
    memories: list[dict[str, Any]] = []
    try:
        with AwarenessStore() as store:
            memories = store.recall("", limit=max_memories)
    except Exception:
        pass

    preferences = [m for m in memories if m.get("category") == "preference"]
    decisions = [m for m in memories if m.get("category") == "decision"]
    notes = [m for m in memories if m.get("category") not in ("preference", "decision")]

    if preferences:
        lines.append("")
        lines.append("Relevant preferences:")
        for m in preferences[:4]:
            text = redact_text(m.get("decision", ""))
            lines.append(f"  - {text}")

    if decisions:
        lines.append("")
        lines.append("Recent decisions:")
        for m in decisions[:4]:
            text = redact_text(m.get("decision", ""))
            lines.append(f"  - {text}")

    if notes:
        lines.append("")
        lines.append("Notes:")
        for m in notes[:3]:
            text = redact_text(m.get("decision", ""))
            lines.append(f"  - {text}")

    lines.append("</awareness-context>")

    snippet = "\n".join(lines)

    # Hard truncate to max_chars
    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 3] + "..."

    return snippet
