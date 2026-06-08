from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from .paths import secure_chmod
from .redaction import redact_text
from .session_start import build_context_snippet

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAUDE_DIR_NAME = ".claude"
COMMANDS_DIR_NAME = "commands"
SESSION_START_HOOK_DIR_NAME = "hooks"

# SessionStart hook script content — written to .claude/hooks/awareness-session-start.sh
SESSION_START_HOOK_SCRIPT = r"""#!/usr/bin/env bash
# awareness-session-start.sh — SessionStart hook for awareness-agent
# Fail-closed: if anything goes wrong, exit 0 with no output (no delay).
#
# Contract with Claude Code:
#   - If the hook exits 0 with no stdout, nothing is injected.
#   - If the hook emits JSON with additionalContext, Claude injects it.
#
# This hook checks plugin opt-in via .claude/plugins/acknowledged-risks.json.
# If opt-in is missing, the hook is a silent no-op.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
OPT_IN_FILE="$PROJECT_ROOT/.claude/plugins/acknowledged-risks.json"

# Check opt-in — exit silently if not explicitly enabled
if [ ! -f "$OPT_IN_FILE" ]; then
  exit 0
fi

# Validate opt-in JSON has awareness session_start enabled
ENABLED=$(python3 -c "
import json, sys
try:
    with open('$OPT_IN_FILE', 'r') as f:
        data = json.load(f)
    plugins = data.get('plugins', {})
    awareness = plugins.get('awareness-agent', {})
    if awareness.get('session_start') is True:
        sys.stdout.write('1')
    else:
        sys.stdout.write('0')
except Exception:
    sys.stdout.write('0')
" 2>/dev/null) || exit 0

if [ "$ENABLED" != "1" ]; then
  exit 0
fi

# Check opt-out state file
STATE_FILE="$PROJECT_ROOT/.claude/plugins/awareness-session-start-disabled"
if [ -f "$STATE_FILE" ]; then
  exit 0
fi

# Generate context with hard timeout (2s max so we never block Claude startup)
# Use argv-style call — no shell injection
CONTEXT=$(timeout 2s python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT/tools/awareness-agent')
from awareness_agent.session_start import build_context_snippet
import os
print(build_context_snippet(cwd='$PROJECT_ROOT', max_chars=10000, timeout=1.5))
" 2>/dev/null) || exit 0

# If empty, nothing to inject
if [ -z "$CONTEXT" ]; then
  exit 0
fi

# Emit structured JSON per Claude Code SessionStart hook protocol
python3 -c "
import json
context = sys.argv[1]
output = json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': context,
    }
})
print(output)
" "$CONTEXT"

exit 0
"""

# Opt-in JSON template
OPT_IN_TEMPLATE = {
    "plugins": {
        "awareness-agent": {
            "session_start": True,
            "description": "Inject awareness context at session start (opt-in)",
        }
    }
}

# Project-local .claude/commands/awareness.md template (generic, repo-relative)
CLAUDE_COMMAND_TEMPLATE = """# /awareness — Local Context Awareness

Use the awareness agent to manage local project context, preferences, and decisions.
All data stays local. No network calls. No telemetry.

## Commands

| Command | Description |
|---------|-------------|
| `/awareness` | Show daemon status and help |
| `/awareness context` | Show current project/session context |
| `/awareness remember <text>` | Store a memory/decision/preference locally |
| `/awareness recall [query]` | Search stored memories (omit query for recent) |
| `/awareness status` | Show daemon/socket/store status |

## SessionStart context injection

If enabled, a compact awareness context block is automatically injected at session
startup. To enable:

```
awareness claude install --session-start
```

To disable:

```
awareness claude uninstall --session-start
```

## Privacy

- All storage is local SQLite.
- No cloud sync, no telemetry, no network calls.
- No conversation harvesting — only explicit `/awareness remember` calls store data.
- Secrets/tokens/passwords are redacted before storage and display.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claude_dir(project_root: Path) -> Path:
    return project_root / CLAUDE_DIR_NAME


def _commands_dir(project_root: Path) -> Path:
    return _claude_dir(project_root) / COMMANDS_DIR_NAME


def _hooks_dir(project_root: Path) -> Path:
    return _claude_dir(project_root) / SESSION_START_HOOK_DIR_NAME


def _plugins_dir(project_root: Path) -> Path:
    return _claude_dir(project_root) / "plugins"


def _opt_in_path(project_root: Path) -> Path:
    return _plugins_dir(project_root) / "acknowledged-risks.json"


def _session_start_hook_path(project_root: Path) -> Path:
    return _hooks_dir(project_root) / "awareness-session-start.sh"


def _opt_out_flag_path(project_root: Path) -> Path:
    return _plugins_dir(project_root) / "awareness-session-start-disabled"


def _write_json(path: Path, data: object, mode: int = 0o600) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    secure_chmod(path, mode)


def _write_text(path: Path, content: str, mode: int = 0o644, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    secure_chmod(path, 0o755 if executable else mode)


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def cmd_claude_install(args: argparse.Namespace) -> int:
    """Install Claude Code / FCC integration.

    Creates:
    - .claude/commands/awareness.md (slash command template)
    - .claude/hooks/awareness-session-start.sh (opt-in SessionStart hook)
    - .claude/plugins/acknowledged-risks.json (opt-in record)
    """
    project_root = Path(args.project).resolve() if args.project else Path.cwd().resolve()
    session_start = args.session_start

    # 1. Always install the command template
    cmd_path = _commands_dir(project_root) / "awareness.md"
    _write_text(cmd_path, CLAUDE_COMMAND_TEMPLATE, mode=0o644, executable=False)
    print(f"installed: {cmd_path.relative_to(project_root)}")

    # 2. Install SessionStart hook (but only enable if --session-start flag given)
    hook_path = _session_start_hook_path(project_root)
    _write_text(hook_path, SESSION_START_HOOK_SCRIPT, mode=0o755, executable=True)
    print(f"installed: {hook_path.relative_to(project_root)}")

    # 3. Handle opt-in for SessionStart
    opt_in = _opt_in_path(project_root)
    existing: dict = {}
    if opt_in.exists():
        import json
        try:
            existing = json.loads(opt_in.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    plugins_section = existing.setdefault("plugins", {})
    awareness_section = plugins_section.setdefault("awareness-agent", {})

    if session_start:
        awareness_section["session_start"] = True
        print("SessionStart injection: ENABLED")
        # Remove opt-out flag if present
        _opt_out_flag_path(project_root).unlink(missing_ok=True)
    else:
        # Hook is installed but will check opt-in — will be silent no-op
        awareness_section["session_start"] = False
        print("SessionStart injection: DISABLED (use --session-start to enable)")

    _write_json(opt_in, existing, mode=0o600)

    print(f"\ninstalled Claude integration in {project_root / '.claude'}")
    return 0


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def cmd_claude_uninstall(args: argparse.Namespace) -> int:
    """Remove Claude Code / FCC integration.

    Removes:
    - .claude/commands/awareness.md
    - .claude/hooks/awareness-session-start.sh
    - .claude/plugins/acknowledged-risks.json awareness-agent section
    - .claude/plugins/awareness-session-start-disabled (opt-out flag)
    """
    project_root = Path(args.project).resolve() if args.project else Path.cwd().resolve()

    removed: list[str] = []

    # Remove command template
    cmd_path = _commands_dir(project_root) / "awareness.md"
    if cmd_path.exists():
        cmd_path.unlink()
        removed.append("commands/awareness.md")

    # Remove SessionStart hook
    hook_path = _session_start_hook_path(project_root)
    if hook_path.exists():
        hook_path.unlink()
        removed.append("hooks/awareness-session-start.sh")

    # Clean opt-in: remove awareness-agent section
    opt_in = _opt_in_path(project_root)
    if opt_in.exists():
        import json
        try:
            existing = json.loads(opt_in.read_text(encoding="utf-8"))
            plugins = existing.get("plugins", {})
            if "awareness-agent" in plugins:
                del plugins["awareness-agent"]
                if not plugins:
                    del existing["plugins"]
                _write_json(opt_in, existing, mode=0o600)
                removed.append("plugins/acknowledged-risks.json (awareness section)")
            # If no plugins section left, remove file
            if "plugins" not in existing or not existing.get("plugins"):
                if opt_in.exists():
                    opt_in.unlink()
                    if "plugins/acknowledged-risks.json (awareness section)" not in removed:
                        removed.append("plugins/acknowledged-risks.json")
        except Exception:
            pass

    # Remove opt-out flag
    flag = _opt_out_flag_path(project_root)
    if flag.exists():
        flag.unlink()
        removed.append("plugins/awareness-session-start-disabled")

    # Clean empty directories
    for d in (_commands_dir(project_root), _hooks_dir(project_root), _plugins_dir(project_root), _claude_dir(project_root)):
        try:
            d.rmdir()  # only removes if empty
        except OSError:
            pass

    if removed:
        for item in removed:
            print(f"removed: {item}")
    else:
        print("nothing to remove — no awareness integration found")

    print(f"\nuninstalled Claude integration from {project_root / '.claude'}")
    return 0


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def cmd_claude_doctor(args: argparse.Namespace) -> int:
    """Diagnose integration state for a project."""
    project_root = Path(args.project).resolve() if args.project else Path.cwd().resolve()
    import json as _json

    print(f"awareness claude doctor — {project_root}")
    print()

    # Daemon status
    status: dict = {}
    try:
        result, daemon = _call("status", {"cwd": str(project_root)})
        status = dict(result)
        status["daemon_running"] = daemon
    except Exception as exc:
        status["error"] = str(exc)
        status["daemon_running"] = False

    print(f"daemon running: {status.get('daemon_running', False)}")
    print(f"socket: {status.get('socket_path', 'n/a')}")
    print(f"db: {status.get('db_path', 'n/a')}")
    counts = status.get("counts", {})
    print(f"memories: {counts.get('decisions', 0)}")
    print()

    # Integration files
    claude_dir = _claude_dir(project_root)
    print(f".claude dir exists: {claude_dir.exists()}")

    cmd_path = _commands_dir(project_root) / "awareness.md"
    print(f"  commands/awareness.md: {'EXISTS' if cmd_path.exists() else 'missing'}")

    hook_path = _session_start_hook_path(project_root)
    print(f"  hooks/awareness-session-start.sh: {'EXISTS' if hook_path.exists() else 'missing'}")

    opt_in = _opt_in_path(project_root)
    opt_in_enabled = False
    if opt_in.exists():
        try:
            data = _json.loads(opt_in.read_text(encoding="utf-8"))
            plugins = data.get("plugins", {})
            awareness = plugins.get("awareness-agent", {})
            opt_in_enabled = awareness.get("session_start", False)
        except Exception:
            pass
    print(f"  session_start enabled: {opt_in_enabled}")

    flag = _opt_out_flag_path(project_root)
    print(f"  opt-out flag present: {flag.exists()}")

    # SessionStart context test
    print()
    print("SessionStart context preview:")
    snippet = build_context_snippet(cwd=str(project_root), timeout=1.0)
    if snippet:
        print(snippet)
    else:
        print("  (daemon not running or no context available)")

    return 0


# ---------------------------------------------------------------------------
# Session-start
# ---------------------------------------------------------------------------


def cmd_claude_session_start(args: argparse.Namespace) -> int:
    """Print SessionStart context snippet (for testing/debugging)."""
    cwd = args.project if args.project else None
    max_chars = args.max_chars
    snippet = build_context_snippet(cwd=cwd, max_chars=max_chars)
    if snippet:
        print(snippet)
    else:
        print("(no context — daemon may not be running)")
    return 0


# ---------------------------------------------------------------------------
# Minimal protocol reuse (local import to avoid circular deps)
# ---------------------------------------------------------------------------


def _call(method: str, params: dict | None = None):
    """Re-use CLI.call without importing cli module directly."""
    from .protocol import handle_request
    from .paths import socket_path
    path = socket_path()
    if path.exists():
        import socket as _sock
        try:
            with _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(str(path))
        except OSError:
            pass
        else:
            import time as _time, json as _json
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": int(_time.time() * 1000),
            }
            with _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(str(path))
                s.sendall((_json.dumps(payload) + "\n").encode("utf-8"))
                data = b""
                while not data.endswith(b"\n"):
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    data += chunk
            if data:
                resp = _json.loads(data.decode("utf-8"))
                if resp.get("error"):
                    raise RuntimeError(resp["error"].get("message", "unknown error"))
                return resp.get("result"), True
    return handle_request(method, params or {}), False


# ---------------------------------------------------------------------------
# argparse integration (used by cli.py)
# ---------------------------------------------------------------------------

import argparse  # noqa: E402 — import at bottom to keep top clean


def add_claude_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("claude", help="Claude Code / FCC integration management")
    claude_sub = p.add_subparsers(dest="claude_command", required=True)

    # install
    inst = claude_sub.add_parser("install", help="install awareness integration into a project")
    inst.add_argument("--project", default=None, help="project root (default: cwd)")
    inst.add_argument("--session-start", action="store_true", default=False,
                       help="enable SessionStart context injection (opt-in)")
    inst.set_defaults(func=cmd_claude_install)

    # uninstall
    unin = claude_sub.add_parser("uninstall", help="remove awareness integration from a project")
    unin.add_argument("--project", default=None, help="project root (default: cwd)")
    unin.add_argument("--session-start", action="store_true", default=False,
                       help="disable SessionStart context injection")
    unin.set_defaults(func=cmd_claude_uninstall)

    # doctor
    doc = claude_sub.add_parser("doctor", help="diagnose integration state")
    doc.add_argument("--project", default=None, help="project root (default: cwd)")
    doc.set_defaults(func=cmd_claude_doctor)

    # session-start
    ss = claude_sub.add_parser("session-start", help="print SessionStart context for current project")
    ss.add_argument("--project", default=None, help="project root (default: cwd)")
    ss.add_argument("--max-chars", type=int, default=10000)
    ss.set_defaults(func=cmd_claude_session_start)
