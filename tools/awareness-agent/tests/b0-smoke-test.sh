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

# Isolated XDG dirs for the daemon
export XDG_CONFIG_HOME="$TMP/xdg-config"
export XDG_DATA_HOME="$TMP/xdg-data"
export XDG_STATE_HOME="$TMP/xdg-state"
export XDG_RUNTIME_DIR="$TMP/xdg-run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR"

# ---- Create a fake project for integration tests ----
PROJECT_DIR="$TMP/fake-project"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
git init -q 2>/dev/null || true
git config user.email "test@test.local"
git config user.name "Test"
echo "print('hello')" > main.py
git add -A && git commit -q -m "init" 2>/dev/null || true

# ============================================================
# Section 1: Existing A0 smoke test still passes
# ============================================================
echo "=== Section 1: A0 smoke test ==="

awareness init >/dev/null
awareness start >/dev/null

awareness status --json > "$TMP/a0-status.json"
python3 - "$TMP/a0-status.json" <<'PYJSON'
import json, sys
with open(sys.argv[1], "r") as f:
    data = json.load(f)
assert data.get("daemon") is True, data
assert str(data.get("socket_path", "")).endswith("awareness-agent.sock"), data
PYJSON

A0TOKEN="a0-smoke-$(date +%s)-$$"
awareness remember "test: $A0TOKEN decision" >/dev/null
awareness recall "$A0TOKEN" > "$TMP/a0-recall.txt"
grep -Fq "$A0TOKEN" "$TMP/a0-recall.txt"

awareness stop >/dev/null
echo "[ok] A0 smoke test still passes"

# Restart daemon for B0 tests
awareness start >/dev/null

# ============================================================
# Section 2: Claude integration install
# ============================================================
echo "=== Section 2: Claude integration install ==="

cd "$PROJECT_DIR"

# Install without --session-start (hook installed but disabled)
awareness claude install --project "$PROJECT_DIR" > "$TMP/install1.txt" 2>&1
grep -q "commands/awareness.md" "$TMP/install1.txt"
grep -q "hooks/awareness-session-start.sh" "$TMP/install1.txt"
grep -q "DISABLED" "$TMP/install1.txt"

# Verify files were created
test -f "$PROJECT_DIR/.claude/commands/awareness.md"
test -x "$PROJECT_DIR/.claude/hooks/awareness-session-start.sh"
test -f "$PROJECT_DIR/.claude/plugins/acknowledged-risks.json"

# Verify opt-in is disabled
python3 - "$PROJECT_DIR/.claude/plugins/acknowledged-risks.json" <<'PYJSON'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data["plugins"]["awareness-agent"]["session_start"] is False, data
PYJSON

echo "[ok] install (without --session-start) works"

# Install with --session-start
awareness claude install --project "$PROJECT_DIR" --session-start > "$TMP/install2.txt" 2>&1
grep -q "ENABLED" "$TMP/install2.txt"

# Verify opt-in is now enabled
python3 - "$PROJECT_DIR/.claude/plugins/acknowledged-risks.json" <<'PYJSON'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert data["plugins"]["awareness-agent"]["session_start"] is True, data
PYJSON

echo "[ok] install with --session-start works"

# ---- Idempotency ----
awareness claude install --project "$PROJECT_DIR" --session-start > "$TMP/install3.txt" 2>&1
# Should succeed and show ENABLED again
grep -q "ENABLED" "$TMP/install3.txt"
echo "[ok] install is idempotent"

# ============================================================
# Section 3: SessionStart context generation
# ============================================================
echo "=== Section 3: SessionStart context ==="

# Store a project-scoped decision through the daemon
B0TOKEN="b0-test-$(date +%s)-$$"
awareness remember "decision: use pytest for tests $B0TOKEN" >/dev/null
awareness remember "preference: prefer functional style $B0TOKEN" >/dev/null
awareness remember "note: architecture uses Hexagonal pattern $B0TOKEN" >/dev/null

# Generate context snippet
CONTEXT=$(awareness claude session-start --project "$PROJECT_DIR" --max-chars 10000 2>/dev/null)
echo "$CONTEXT" > "$TMP/context1.txt"

grep -q "<awareness-context>" "$TMP/context1.txt"
grep -q "</awareness-context>" "$TMP/context1.txt"
grep -q "Project:" "$TMP/context1.txt"
grep -q "fake-project" "$TMP/context1.txt"

echo "[ok] SessionStart context generated with project info"

# ---- Bounded output ----
CONTEXT_LIMITED=$(awareness claude session-start --project "$PROJECT_DIR" --max-chars 50 2>/dev/null)
LEN=${#CONTEXT_LIMITED}
if [ "$LEN" -gt 53 ]; then  # allow a bit of slack for "..." truncation
  echo "[fail] context exceeded max-chars: $LEN > 50" >&2
  exit 1
fi
echo "[ok] context respects max-chars limit"

# ============================================================
# Section 4: Redaction in context output
# ============================================================
echo "=== Section 4: Redaction ==="

FAKE_SECRET="sk-fakekey1234567890abcdef"
awareness remember "redaction test secret=$FAKE_SECRET" >/dev/null

CONTEXT_REDACTED=$(awareness claude session-start --project "$PROJECT_DIR" --max-chars 10000 2>/dev/null)
if echo "$CONTEXT_REDACTED" | grep -q "$FAKE_SECRET"; then
  echo "[fail] raw secret leaked through context output" >&2
  exit 1
fi
echo "[ok] secrets are redacted in context output"

# ============================================================
# Section 5: Graceful degradation (no daemon)
# ============================================================
echo "=== Section 5: Graceful degradation ==="

awareness stop >/dev/null

# session-start should not crash when daemon is down
CONTEXT_NO_DAEMON=$(awareness claude session-start --project "$PROJECT_DIR" --max-chars 10000 2>&1) || true
# Should either be empty or contain the "no context" message — no stack trace
if echo "$CONTEXT_NO_DAEMON" | grep -qi "traceback\|error:\|exception"; then
  echo "[fail] session-start crashed when daemon is down: $CONTEXT_NO_DAEMON" >&2
  exit 1
fi
echo "[ok] session-start degrades gracefully when daemon is down"

# SessionStart hook should also not crash
HOOK_OUTPUT=$("$PROJECT_DIR/.claude/hooks/awareness-session-start.sh" 2>&1) || true
if echo "$HOOK_OUTPUT" | grep -qi "traceback\|error:\|exception"; then
  echo "[fail] hook crashed: $HOOK_OUTPUT" >&2
  exit 1
fi
echo "[ok] SessionStart hook degrades gracefully when daemon is down"

# ============================================================
# Section 6: Doctor
# ============================================================
echo "=== Section 6: Doctor ==="

# Restart daemon for doctor test
awareness start >/dev/null

DOCTOR_OUTPUT=$(awareness claude doctor --project "$PROJECT_DIR" 2>&1)
echo "$DOCTOR_OUTPUT" > "$TMP/doctor.txt"
grep -q "daemon running: True" "$TMP/doctor.txt"
grep -q "commands/awareness.md: EXISTS" "$TMP/doctor.txt"
grep -q "session_start enabled: True" "$TMP/doctor.txt"
echo "[ok] doctor reports correct state"

# ============================================================
# Section 7: Uninstall
# ============================================================
echo "=== Section 7: Uninstall ==="

awareness claude uninstall --project "$PROJECT_DIR" > "$TMP/uninstall.txt" 2>&1
grep -q "removed" "$TMP/uninstall.txt"

# Verify files removed
test ! -f "$PROJECT_DIR/.claude/commands/awareness.md" || { echo "[fail] commands/awareness.md still exists"; exit 1; }
test ! -f "$PROJECT_DIR/.claude/hooks/awareness-session-start.sh" || { echo "[fail] hook still exists"; exit 1; }

echo "[ok] uninstall removes integration files"

# ---- Idempotent uninstall ----
awareness claude uninstall --project "$PROJECT_DIR" > "$TMP/uninstall2.txt" 2>&1
grep -q "nothing to remove" "$TMP/uninstall2.txt"
echo "[ok] uninstall is idempotent"

# ============================================================
# Section 8: Generated files don't contain real home paths
# ============================================================
echo "=== Section 8: No real home paths in generated files ==="

# Reinstall to check generated content
awareness claude install --project "$PROJECT_DIR" --session-start >/dev/null 2>&1

# The command template should not contain absolute home paths
CMD_CONTENT=$(cat "$PROJECT_DIR/.claude/commands/awareness.md")
if echo "$CMD_CONTENT" | grep -q "/home/$USER"; then
  echo "[fail] command template contains real home path" >&2
  exit 1
fi

# The hook script should reference $PROJECT_ROOT (not hardcoded home)
HOOK_CONTENT=$(cat "$PROJECT_DIR/.claude/hooks/awareness-session-start.sh")
if echo "$HOOK_CONTENT" | grep -qE "/home/[a-z]"; then
  echo "[fail] hook contains hardcoded home path" >&2
  exit 1
fi

echo "[ok] generated files use relative/repo-safe paths"

# Cleanup
awareness claude uninstall --project "$PROJECT_DIR" >/dev/null 2>&1

# ============================================================
# Section 9: Tests don't mutate real user dirs
# ============================================================
echo "=== Section 9: No mutation of real user dirs ==="

# Verify real .claude dir was not touched
if [ -f "$REPO_ROOT/.claude/commands/awareness.md" ]; then
  echo "[fail] test created awareness.md in real .claude" >&2
  exit 1
fi
if [ -f "$REPO_ROOT/.claude/hooks/awareness-session-start.sh" ]; then
  echo "[fail] test created hook in real .claude" >&2
  exit 1
fi

echo "[ok] real user .claude not mutated"

# ============================================================
echo ""
echo "[ok] awareness-agent spike B0 smoke test passed"
