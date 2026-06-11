from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

from .config import apply_runtime_config
from .mcp import serve_forever as serve_mcp_forever
from .paths import ensure_dirs, log_path, pid_path, secure_chmod, socket_path, write_default_config
from .protocol import handle_request
from .server import serve_forever


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def rpc_call(method: str, params: dict[str, Any] | None = None, timeout: float = 1.0) -> Any:
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


def call(method: str, params: dict[str, Any] | None = None) -> tuple[Any, bool]:
    try:
        return rpc_call(method, params), True
    except Exception:
        apply_runtime_config()
        return handle_request(method, params or {}), False


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def cmd_init(_args: argparse.Namespace) -> int:
    write_default_config()
    apply_runtime_config()
    print("initialized awareness-agent config/state")
    return 0


def cmd_serve(_args: argparse.Namespace) -> int:
    write_default_config()
    apply_runtime_config()
    asyncio.run(serve_forever())
    return 0


def cmd_mcp_serve(_args: argparse.Namespace) -> int:
    write_default_config()
    apply_runtime_config()
    asyncio.run(serve_mcp_forever())
    return 0


def cmd_start(_args: argparse.Namespace) -> int:
    write_default_config()

    try:
        health = rpc_call("health")
        print(f"already running: {health['socket_path']}")
        return 0
    except Exception:
        pass

    apply_runtime_config()
    ensure_dirs()
    pkg_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pkg_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log, "a", encoding="utf-8")
    secure_chmod(log, 0o600)

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "awareness_agent.cli", "serve"],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    finally:
        log_file.close()

    for _ in range(30):
        if proc.poll() is not None:
            print(f"failed to start; see {log}", file=sys.stderr)
            return 1
        try:
            health = rpc_call("health", timeout=0.2)
            print(f"started awareness-agent: {health['socket_path']}")
            return 0
        except Exception:
            time.sleep(0.1)

    print(f"timed out waiting for daemon; see {log}", file=sys.stderr)
    return 1


def cmd_stop(_args: argparse.Namespace) -> int:
    path = pid_path()
    if not path.exists():
        print("not running: no pid file")
        return 0

    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        path.unlink(missing_ok=True)
        print("removed invalid pid file")
        return 0

    if not _pid_alive(pid):
        path.unlink(missing_ok=True)
        print("not running: stale pid removed")
        return 0

    os.kill(pid, signal.SIGTERM)

    for _ in range(30):
        if not _pid_alive(pid):
            print("stopped awareness-agent")
            return 0
        time.sleep(0.1)

    print(f"daemon did not stop cleanly: pid={pid}", file=sys.stderr)
    return 1


def cmd_restart(args: argparse.Namespace) -> int:
    stop_code = cmd_stop(args)
    if stop_code != 0:
        return stop_code
    time.sleep(0.2)
    return cmd_start(args)


def cmd_status(args: argparse.Namespace) -> int:
    result, daemon = call("status", {"cwd": os.getcwd()})
    result["daemon"] = daemon

    if args.json:
        _print_json(result)
        return 0

    project = result.get("current_project") or {}
    mode = "running" if daemon else "direct/offline fallback"
    print(f"awareness-agent: {mode}")
    print(f"db: {result.get('db_path')}")
    print(f"socket: {result.get('socket_path')}")
    print(f"counts: {result.get('counts')}")
    print(f"project: {project.get('name')} ({project.get('root') or project.get('path')})")
    if project.get("is_git_repo"):
        print(f"branch: {project.get('branch')} dirty={project.get('dirty_count')}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    if args.scope != "project":
        raise ValueError(f"unsupported context scope: {args.scope}")

    result, daemon = call("context.project", {"cwd": os.getcwd()})

    if args.json:
        result = dict(result)
        result["daemon"] = daemon
        _print_json(result)
        return 0

    if not result.get("is_git_repo"):
        print(f"not a git repo: {result.get('path')}")
        return 0

    print(f"name: {result.get('name')}")
    print(f"root: {result.get('root')}")
    print(f"branch: {result.get('branch')}")
    print(f"dirty_count: {result.get('dirty_count')}")
    print(f"language: {result.get('language')}")
    print(f"framework: {result.get('framework')}")
    if result.get("remotes"):
        print("remotes:")
        for remote in result["remotes"]:
            print(f"  - {remote}")
    if result.get("recent_commits"):
        print("recent_commits:")
        for commit in result["recent_commits"]:
            print(f"  - {commit}")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip()
    result, daemon = call(
        "memory.remember",
        {
            "cwd": os.getcwd(),
            "text": text,
            "category": args.category,
            "source": "cli",
        },
    )
    result["daemon"] = daemon

    if args.json:
        _print_json(result)
    else:
        redacted = " redacted" if result.get("redacted") else ""
        print(f"remembered #{result['id']} for project={result.get('project')}{redacted}")

    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    query = " ".join(args.query).strip()
    result, daemon = call("memory.recall", {"query": query, "limit": args.limit})
    result["daemon"] = daemon

    if args.json:
        _print_json(result)
        return 0

    items = result.get("items") or []
    if not items:
        print("no memories found")
        return 0

    for item in items:
        project = item.get("project_name") or "global"
        print(f"[{item['timestamp']}] #{item['id']} {item['category']} @{project}")
        print(f"  {item['decision']}")
        if item.get("rationale"):
            print(f"  rationale: {item['rationale']}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    path = log_path()
    if not path.exists():
        print(f"no log file: {path}")
        return 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in deque(handle, maxlen=args.lines):
            print(line, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="awareness",
        description="Awareness Agent — local-first context daemon spike A0",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create default config/state dirs")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("serve", help="run daemon in foreground")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("mcp", help="run the stdio MCP façade")
    p.set_defaults(func=cmd_mcp_serve)

    p = sub.add_parser("start", help="start daemon in background")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop", help="stop daemon")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("restart", help="restart daemon")
    p.set_defaults(func=cmd_restart)

    p = sub.add_parser("status", help="show daemon/store/project status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("context", help="show current context")
    p.add_argument("scope", nargs="?", default="project", choices=["project"])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("remember", help="store a local memory/decision")
    p.add_argument("text", nargs="+")
    p.add_argument("--category", default="note")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_remember)

    p = sub.add_parser("recall", help="search local memories/decisions")
    p.add_argument("query", nargs="*")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_recall)

    p = sub.add_parser("logs", help="tail daemon logs")
    p.add_argument("--lines", type=int, default=80)
    p.set_defaults(func=cmd_logs)

    # claude integration subcommand
    from .integrations import add_claude_subparser
    add_claude_subparser(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"awareness: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
