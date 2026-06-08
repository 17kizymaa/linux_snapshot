#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$AGENT_ROOT/../.." >/dev/null 2>&1 && pwd)"

export PATH="$AGENT_ROOT/bin:$PATH"

TMP="$(mktemp -d)"
cleanup() {
  awareness stop >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

stat_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}

export XDG_CONFIG_HOME="$TMP/config"
export XDG_DATA_HOME="$TMP/data"
export XDG_STATE_HOME="$TMP/state"
export XDG_RUNTIME_DIR="$TMP/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR"

cd "$REPO_ROOT"

awareness init >/dev/null
awareness start >/dev/null

awareness status --json > "$TMP/status.json"
python3 - "$TMP/status.json" <<'PYJSON'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

assert data.get("daemon") is True, data
assert str(data.get("socket_path", "")).endswith("awareness-agent.sock"), data
assert "counts" in data, data
PYJSON

TOKEN="smoke-a0-$(date +%s)-$$"
awareness remember "test: $TOKEN decision" > "$TMP/remember.txt"
grep -Fq 'remembered #' "$TMP/remember.txt"
awareness recall "$TOKEN" > "$TMP/recall.txt"
grep -Fq "$TOKEN" "$TMP/recall.txt"

RAW_SECRET="supersecret-a0-$$"
awareness remember "redaction: token=$RAW_SECRET" --json > "$TMP/redaction.json"
awareness recall "redaction" > "$TMP/redaction.txt"
grep -Fq "token=***" "$TMP/redaction.txt"
if grep -Fq "$RAW_SECRET" "$TMP/redaction.txt"; then
  echo "[fail] raw secret leaked through recall" >&2
  exit 1
fi

awareness context project --json > "$TMP/project.json"
python3 - "$TMP/project.json" <<'PYJSON'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

assert "is_git_repo" in data, data
assert data.get("name"), data
PYJSON

SOCKET="$XDG_RUNTIME_DIR/awareness-agent.sock"
test -S "$SOCKET"
MODE="$(stat_mode "$SOCKET")"
test "$MODE" = "600"

DB="$XDG_DATA_HOME/awareness-agent/awareness.db"
test -f "$DB"
MODE="$(stat_mode "$DB")"
test "$MODE" = "600"

# Force live WAL/SHM sidecars by writing through an open store connection,
# then verify ALL sidecars exist and are mode 0600 while the daemon is running.
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PYDBMODE'
import stat
import sys
from pathlib import Path

sys.path.insert(0, "$AGENT_ROOT")
from awareness_agent.paths import db_path
from awareness_agent.store import AwarenessStore


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


with AwarenessStore() as store:
    store.remember(
        "sidecar_check: smoke db mode check",
        category="smoke",
        source="smoke-test",
    )

    paths = [
        db_path(),
        Path(str(db_path()) + "-wal"),
        Path(str(db_path()) + "-shm"),
    ]

    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise AssertionError(
            f"missing expected SQLite WAL files while connection is open: {missing}"
        )

    bad_modes = {
        str(p): oct(file_mode(p))
        for p in paths
        if file_mode(p) != 0o600
    }
    if bad_modes:
        raise AssertionError(f"bad SQLite file modes: {bad_modes}")
PYDBMODE

awareness stop >/dev/null

echo "[ok] awareness-agent spike A0 smoke test passed"
