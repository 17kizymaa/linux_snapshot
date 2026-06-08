from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "awareness-agent"


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def xdg_config_home() -> Path:
    return _path_from_env("XDG_CONFIG_HOME", Path.home() / ".config")


def xdg_data_home() -> Path:
    return _path_from_env("XDG_DATA_HOME", Path.home() / ".local" / "share")


def xdg_state_home() -> Path:
    return _path_from_env("XDG_STATE_HOME", Path.home() / ".local" / "state")


def runtime_dir() -> Path:
    raw = os.environ.get("XDG_RUNTIME_DIR")
    return Path(raw) if raw else state_dir()


def config_dir() -> Path:
    return xdg_config_home() / APP_NAME


def data_dir() -> Path:
    return xdg_data_home() / APP_NAME


def state_dir() -> Path:
    return xdg_state_home() / APP_NAME


def db_path() -> Path:
    return data_dir() / "awareness.db"


def socket_path() -> Path:
    return runtime_dir() / f"{APP_NAME}.sock"


def pid_path() -> Path:
    return state_dir() / "daemon.pid"


def log_path() -> Path:
    return state_dir() / "daemon.log"


def secure_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except (FileNotFoundError, PermissionError, OSError):
        pass


def ensure_dirs() -> None:
    for directory in (config_dir(), data_dir(), state_dir(), runtime_dir()):
        directory.mkdir(parents=True, exist_ok=True)
        secure_chmod(directory, 0o700)


def write_default_config(overwrite: bool = False) -> None:
    ensure_dirs()

    config = config_dir() / "config.toml"
    if overwrite or not config.exists():
        config.write_text(
            """# Awareness Agent config — Spike A0
# Local-only. No network listeners. Unix socket IPC only.

[daemon]
socket = "auto"

[retention]
sessions_days = 30
commands_days = 7
model_telemetry_hours = 24

[providers.git]
enabled = true

[providers.shell]
enabled = false

[providers.editor]
enabled = false

[providers.clipboard]
enabled = false
""",
            encoding="utf-8",
        )
        secure_chmod(config, 0o600)

    redaction = config_dir() / "redaction.toml"
    if overwrite or not redaction.exists():
        redaction.write_text(
            """# Redaction rules — Spike A0
# Implementation currently uses built-in conservative regexes.

patterns = [
  "password",
  "passwd",
  "token",
  "api_key",
  "secret",
  "credential",
  "bearer"
]
""",
            encoding="utf-8",
        )
        secure_chmod(redaction, 0o600)

    ego = config_dir() / "ego.json"
    if overwrite or not ego.exists():
        ego.write_text(
            json.dumps(
                {
                    "preferences": {},
                    "goals": [],
                    "constraints": [
                        "local-first",
                        "no hidden surveillance",
                        "explicit invocation only",
                    ],
                    "budget": {
                        "preferred_model": "local",
                        "network_allowed": False,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        secure_chmod(ego, 0o600)
