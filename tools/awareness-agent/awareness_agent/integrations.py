from __future__ import annotations

import json
import os
from pathlib import Path

from .paths import secure_chmod
from .session_start import build_context_snippet

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAUDE_DIR_NAME = ".claude"
COMMANDS_DIR_NAME = "commands"
SESSION_START_HOOK_DIR_NAME = "hooks"

# SessionStart hook script content — written to .claude/hooks/awareness-session-start.sh
SESSION_START_HOOK_SCRIPT = """#!/usr/bin/env bash
# awareness-session-start.sh — SessionStart hook for awareness-agent
# Fail-closed: if anything goes wrong, exit 0 with no output (no delay).
#
# Contract with Claude Code:
#   - If the hook exits 0 with no stdout, nothing is injected.
#   - If the hook emits JSON with additionalContext, Claude injects it.
#
# This hook checks plugin opt-in via .claude/plugins/acknowledged-risks.json.
# If opt-in is missing, the hook is a silent no-op.
#
# Portability: no GNU timeout, no bashisms beyond POSIX. Works on macOS/Linux.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"

# Export for the Python child process — avoids shell interpolation of paths
# that may contain spaces, quotes, or other special characters.
export AWARENESS_PROJECT_ROOT="$PROJECT_ROOT"
export AWARENESS_OPT_IN_FILE="$PROJECT_ROOT/.claude/plugins/acknowledged-risks.json"
export AWARENESS_STATE_FLAG="$PROJECT_ROOT/.claude/plugins/awareness-session-start-disabled"

# Delegate everything to a single Python invocation:
#   1. Check opt-in (reads AWARENESS_OPT_IN_FILE)
#   2. Check opt-out flag (AWARENESS_STATE_FLAG)
#   3. Generate bounded, redacted context snippet
#   4. Emit JSON hook output
#
# Timeout is enforced inside Python via socket timeout + SIGALRM (Unix) or
# subprocess timeout fallback. No external `timeout` command needed.
exec python3 -c '
import json, os, signal, sys, time
from pathlib import Path

PROJECT_ROOT = os.environ.get("AWARENESS_PROJECT_ROOT", "")
OPT_IN_FILE = os.environ.get("AWARENESS_OPT_IN_FILE", "")
STATE_FLAG = os.environ.get("AWARENESS_STATE_FLAG", "")

# --- Opt-in check ---
if not OPT_IN_FILE or not Path(OPT_IN_FILE).exists():
    sys.exit(0)

try:
    with open(OPT_IN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    enabled = data.get("plugins", {}).get("awareness-agent", {}).get("session_start", False)
except Exception:
    sys.exit(0)

if not enabled:
    sys.exit(0)

# --- Opt-out flag ---
if STATE_FLAG and Path(STATE_FLAG).exists():
    sys.exit(0)

# --- Generate context with hard timeout ---
# Use SIGALRM on Unix; on non-Unix, rely on socket-level timeouts.
def _alarm_handler(signum, frame):
    raise TimeoutError("awareness context generation timed out")

old_handler = None
try:
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(2)  # 2-second hard timeout, works on Linux/macOS
except (AttributeError, OSError):
    pass  # SIGALRM not available (Windows); socket timeout will catch it

try:
    sys.path.insert(0, str(Path(PROJECT_ROOT) / "tools" / "awareness-agent"))
    from awareness_agent.session_start import build_context_snippet

    context = build_context_snippet(
        cwd=PROJECT_ROOT,
        max_chars=10000,
        timeout=1.5,
    )
except Exception:
    context = ""
finally:
    try:
        signal.alarm(0)
        if old_handler is not None:
            signal.signal(signal.SIGALRM, old_handler)
    except (AttributeError, OSError):
        pass

if not context:
    sys.exit(0)

# --- Emit JSON hook output ---
output = json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }
})
print(output)
'
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
    """Diagnose integration state for a project. Reports state + actionable fixes."""
    project_root = Path(args.project).resolve() if args.project else Path.cwd().resolve()
    import json as _json

    print(f"awareness claude doctor — {project_root}")
    print()

    issues: list[str] = []
    hints: list[str] = []

    # Daemon status
    daemon_running = False
    try:
        result, daemon = _call("status", {"cwd": str(project_root)})
        status = dict(result)
        daemon_running = daemon
    except Exception as exc:
        status = {"error": str(exc)}

    print(f"daemon running: {daemon_running}")
    print(f"socket: {status.get('socket_path', 'n/a')}")
    print(f"db: {status.get('db_path', 'n/a')}")
    counts = status.get("counts", {})
    print(f"memories: {counts.get('decisions', 0)}")

    if not daemon_running:
        issues.append("daemon not running")
        hints.append("run: awareness start")

    if status.get("error"):
        issues.append(f"status error: {status['error']}")

    print()

    # Integration files
    claude_dir = _claude_dir(project_root)
    print(f".claude dir exists: {claude_dir.exists()}")

    cmd_path = _commands_dir(project_root) / "awareness.md"
    cmd_exists = cmd_path.exists()
    print(f"  commands/awareness.md: {'EXISTS' if cmd_exists else 'missing'}")
    if not cmd_exists and claude_dir.exists():
        hints.append("run: awareness claude install")

    hook_path = _session_start_hook_path(project_root)
    hook_exists = hook_path.exists()
    print(f"  hooks/awareness-session-start.sh: {'EXISTS' if hook_exists else 'missing'}")
    if not hook_exists and claude_dir.exists():
        hints.append("run: awareness claude install  (to add the SessionStart hook)")

    opt_in = _opt_in_path(project_root)
    opt_in_enabled = False
    opt_in_valid = False
    if opt_in.exists():
        try:
            data = _json.loads(opt_in.read_text(encoding="utf-8"))
            opt_in_valid = True
            plugins = data.get("plugins", {})
            awareness = plugins.get("awareness-agent", {})
            opt_in_enabled = awareness.get("session_start", False)
        except Exception:
            issues.append("acknowledged-risks.json is not valid JSON")
            hints.append("fix: delete .claude/plugins/acknowledged-risks.json and re-run install")
    print(f"  session_start enabled: {opt_in_enabled}")
    if not opt_in_valid and opt_in.exists():
        print(f"  opt-in file: INVALID JSON")
    elif not opt_in.exists():
        print(f"  opt-in file: missing (run awareness claude install)")

    flag = _opt_out_flag_path(project_root)
    flag_exists = flag.exists()
    print(f"  opt-out flag present: {flag_exists}")
    if flag_exists and opt_in_enabled:
        issues.append("opt-out flag is present — injection is disabled despite opt-in")
        hints.append("fix: awareness claude install --session-start  (removes flag)")

    if opt_in_enabled and not issues:
        print()
        print("SessionStart context preview:")
        snippet = build_context_snippet(cwd=str(project_root), timeout=1.0)
        if snippet:
            print(snippet)
        else:
            print("  (daemon not running or no context available)")
            hints.append("start the daemon to see context preview: awareness start")

    # Summary
    print()
    if issues:
        print(f"issues ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    if hints:
        print(f"suggested actions:")
        for hint in hints:
            print(f"  → {hint}")
    if not issues and not hints:
        print("all clear — integration looks healthy")

    return 1 if issues else 0


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
    """Try daemon RPC first, fall back to direct call. Single socket connection."""
    from .protocol import handle_request
    from .paths import socket_path
    import socket as _sock
    import time as _time
    import json as _json

    path = socket_path()
    if path.exists():
        try:
            with _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(str(path))
                payload = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                    "id": int(_time.time() * 1000),
                }
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
        except (OSError, _json.JSONDecodeError, RuntimeError):
            pass
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
