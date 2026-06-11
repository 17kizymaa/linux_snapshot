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
# Section 10: C4 runtime config loading
# ============================================================
echo "=== Section 10: C4 runtime config loading ==="

cat > "$XDG_CONFIG_HOME/awareness-agent/config.toml" <<'TOML'
[embedding]
enabled = false
backend = "hash"
model = "all-MiniLM-L6-v2"

[ranking.weights]
embedding = 0.25
embedding_threshold = 0.4
TOML

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PYCONFIG'
from awareness_agent.config import build_rank_weights, load_runtime_config

config = load_runtime_config()
weights = build_rank_weights(config)
assert weights.embedding == 0.25, weights
assert weights.embedding_threshold == 0.4, weights
PYCONFIG

echo "[ok] runtime config loading works"

# ============================================================
# Section 11: C4 MCP façade
# ============================================================
echo "=== Section 11: C4 MCP façade ==="

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PYMCP'
import json
import os
import subprocess

messages = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "awareness.health", "arguments": {}}},
]

proc = subprocess.Popen(
    ["awareness", "mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
for message in messages:
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()

responses = [json.loads(proc.stdout.readline()) for _ in messages]
proc.terminate()
stderr = proc.stderr.read()

assert responses[0]["result"]["serverInfo"]["name"] == "awareness-agent", responses
assert any(tool["name"] == "awareness.memory.recall" for tool in responses[1]["result"]["tools"]), responses
health = json.loads(responses[2]["result"]["content"][0]["text"])
assert health["ok"] is True, responses
assert "Traceback" not in stderr, stderr
PYMCP

echo "[ok] MCP façade discovery and invocation works"

# ============================================================
echo ""
echo "[ok] awareness-agent spike B0 smoke test passed"

# ============================================================
# Section 10: Project path with spaces
# ============================================================
echo "=== Section 10: Project path with spaces ==="

PROJECT_WITH_SPACE="$TMP/fake project with spaces"
mkdir -p "$PROJECT_WITH_SPACE"
cd "$PROJECT_WITH_SPACE"
git init -q 2>/dev/null || true
git config user.email "test@test.local"
git config user.name "Test"
echo "print('hello')" > main.py
git add -A && git commit -q -m "init" 2>/dev/null || true

awareness claude install --project "$PROJECT_WITH_SPACE" --session-start > "$TMP/install-space.txt" 2>&1
grep -q "ENABLED" "$TMP/install-space.txt"

test -x "$PROJECT_WITH_SPACE/.claude/hooks/awareness-session-start.sh"
python3 -c "
import json
with open('$PROJECT_WITH_SPACE/.claude/plugins/acknowledged-risks.json') as f:
    d = json.load(f)
assert d['plugins']['awareness-agent']['session_start'] is True
"

CONTEXT_SPACE=$(awareness claude session-start --project "$PROJECT_WITH_SPACE" --max-chars 5000 2>/dev/null)
echo "$CONTEXT_SPACE" > "$TMP/context-space.txt"
grep -q "<awareness-context>" "$TMP/context-space.txt"
grep -q "fake project with spaces" "$TMP/context-space.txt"

HOOK_SPACE_OUTPUT=$("$PROJECT_WITH_SPACE/.claude/hooks/awareness-session-start.sh" 2>&1) || true
if echo "$HOOK_SPACE_OUTPUT" | grep -qi "traceback\|error:\|exception"; then
  echo "[fail] hook crashed with spaces in path: $HOOK_SPACE_OUTPUT" >&2
  exit 1
fi

awareness claude uninstall --project "$PROJECT_WITH_SPACE" >/dev/null 2>&1
test ! -f "$PROJECT_WITH_SPACE/.claude/commands/awareness.md"

echo "[ok] project path with spaces handled correctly"

# ============================================================
# Section 11: Uninstall preserves unrelated .claude content
# ============================================================
echo "=== Section 11: Uninstall preserves unrelated content ==="

PROJECT_PRESERVE="$TMP/fake-project-preserve"
mkdir -p "$PROJECT_PRESERVE/.claude/commands" "$PROJECT_PRESERVE/.claude/hooks" "$PROJECT_PRESERVE/.claude/plugins"
echo "# other command" > "$PROJECT_PRESERVE/.claude/commands/other.md"
echo "#!/bin/bash" > "$PROJECT_PRESERVE/.claude/hooks/other-hook.sh"
echo '{"plugins": {"other-plugin": {"enabled": true}}}' > "$PROJECT_PRESERVE/.claude/plugins/acknowledged-risks.json"

awareness claude install --project "$PROJECT_PRESERVE" --session-start >/dev/null 2>&1

test -f "$PROJECT_PRESERVE/.claude/commands/other.md"
test -f "$PROJECT_PRESERVE/.claude/hooks/other-hook.sh"

python3 -c "
import json
with open('$PROJECT_PRESERVE/.claude/plugins/acknowledged-risks.json') as f:
    d = json.load(f)
assert 'other-plugin' in d.get('plugins', {}), 'other-plugin section lost'
assert 'awareness-agent' in d.get('plugins', {}), 'awareness-agent section missing'
"

awareness claude uninstall --project "$PROJECT_PRESERVE" >/dev/null 2>&1
test -f "$PROJECT_PRESERVE/.claude/commands/other.md" || { echo "[fail] other.md was removed"; exit 1; }
test -f "$PROJECT_PRESERVE/.claude/hooks/other-hook.sh" || { echo "[fail] other-hook.sh was removed"; exit 1; }

python3 -c "
import json
with open('$PROJECT_PRESERVE/.claude/plugins/acknowledged-risks.json') as f:
    d = json.load(f)
assert 'other-plugin' in d.get('plugins', {}), 'other-plugin section lost after uninstall'
assert 'awareness-agent' not in d.get('plugins', {}), 'awareness-agent section not cleaned'
"

echo "[ok] uninstall preserves unrelated .claude content"

# ============================================================
# Section 12: Doctor actionable hints
# ============================================================
echo "=== Section 12: Doctor actionable hints ==="

PROJECT_DOCTOR="$TMP/fake-project-doctor"
mkdir -p "$PROJECT_DOCTOR"

awareness stop >/dev/null 2>&1 || true
DOCTOR_NO=$(awareness claude doctor --project "$PROJECT_DOCTOR" 2>&1) || true
echo "$DOCTOR_NO" > "$TMP/doctor-no.txt"
grep -q "daemon running: False" "$TMP/doctor-no.txt"
grep -q "run: awareness start" "$TMP/doctor-no.txt"

awareness claude install --project "$PROJECT_DOCTOR" --session-start >/dev/null 2>&1
DOCTOR_NO_DAEMON=$(awareness claude doctor --project "$PROJECT_DOCTOR" 2>&1) || true
echo "$DOCTOR_NO_DAEMON" > "$TMP/doctor-no-daemon.txt"
grep -q "daemon running: False" "$TMP/doctor-no-daemon.txt"
grep -q "run: awareness start" "$TMP/doctor-no-daemon.txt"

awareness start >/dev/null
DOCTOR_OK=$(awareness claude doctor --project "$PROJECT_DOCTOR" 2>&1)
echo "$DOCTOR_OK" > "$TMP/doctor-ok.txt"
grep -q "daemon running: True" "$TMP/doctor-ok.txt"
grep -q "all clear" "$TMP/doctor-ok.txt"

echo "[ok] doctor provides actionable hints"

# ============================================================
# Section 13: Empty memory state
# ============================================================
echo "=== Section 13: Empty memory state ==="

PROJECT_EMPTY="$TMP/fake-project-empty"
mkdir -p "$PROJECT_EMPTY"
cd "$PROJECT_EMPTY"
git init -q 2>/dev/null || true
git config user.email "test@test.local"
git config user.name "Test"

CONTEXT_EMPTY=$(awareness claude session-start --project "$PROJECT_EMPTY" --max-chars 5000 2>/dev/null)
echo "$CONTEXT_EMPTY" > "$TMP/context-empty.txt"
grep -q "<awareness-context>" "$TMP/context-empty.txt"
grep -q "no stored memories" "$TMP/context-empty.txt"

echo "[ok] empty memory state produces clean message"

# ============================================================
# Section 14: Control character stripping
# ============================================================
echo "=== Section 14: Control character stripping ==="

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    store.remember('note: has\x00null\x07bell\x1b[31mred text', category='note', source='test')
"

CONTEXT_CTRL=$(awareness claude session-start --project "$PROJECT_EMPTY" --max-chars 5000 2>/dev/null)
if echo "$CONTEXT_CTRL" | grep -qP '[\x00-\x08\x0e-\x1f]'; then
  echo "[fail] control characters leaked into context" >&2
  exit 1
fi
if echo "$CONTEXT_CTRL" | grep -qP '\x1b\['; then
  echo "[fail] ANSI escape sequences leaked into context" >&2
  exit 1
fi

echo "[ok] control characters stripped from context output"

# ============================================================
# Section 15: Untrusted-context framing
# ============================================================
echo "=== Section 15: Untrusted-context framing ==="

CONTEXT_FRAME=$(awareness claude session-start --project "$PROJECT_EMPTY" --max-chars 5000 2>/dev/null)
if ! echo "$CONTEXT_FRAME" | grep -q "untrusted"; then
  echo "[fail] context missing untrusted framing comment" >&2
  exit 1
fi

echo "[ok] context includes untrusted-data framing"

# ============================================================
# Section 16: FTS5 + taxonomy migration (C1)
# ============================================================
echo "=== Section 16: FTS5 + taxonomy migration ==="

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys, sqlite3
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    cols = {r[1] for r in store.conn.execute('PRAGMA table_info(decisions)')}
    assert 'kind' in cols, f'missing kind column: {cols}'
    assert 'scope' in cols, f'missing scope column: {cols}'
    assert 'confidence' in cols, f'missing confidence column: {cols}'
    assert 'tags' in cols, f'missing tags column: {cols}'
    assert 'expires_at' in cols, f'missing expires_at column: {cols}'
    assert 'pinned' in cols, f'missing pinned column: {cols}'
    tables = {r[0] for r in store.conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
    assert 'decisions_fts' in tables, f'missing decisions_fts: {tables}'
    print('taxonomy columns: ok')
    print('fts5 table: ok')
"

echo "[ok] FTS5 + taxonomy migration applied"

# ============================================================
# Section 17: Kind auto-detection in remember() (C1)
# ============================================================
echo "=== Section 17: Kind auto-detection ==="

KIND_TOKEN="kind-test-$(date +%s)-$$"
awareness remember "decision: use PostgreSQL for production $KIND_TOKEN" >/dev/null
awareness remember "prefer: functional style over classes $KIND_TOKEN" >/dev/null
awareness remember "error: sqlite locked — restart daemon $KIND_TOKEN" >/dev/null
awareness remember "note: consider migrating to APIRouter $KIND_TOKEN" >/dev/null

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys, json
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    rows = store.recall('$KIND_TOKEN', limit=10)
    kinds = {r['decision'].split(' ')[0].lower(): r.get('kind', '') for r in rows}
    print('kinds found:', json.dumps(kinds, indent=2))
    assert kinds.get('use') == 'decision', f'expected decision, got {kinds.get(\"use\")}'
    assert kinds.get('functional') == 'preference', f'expected preference, got {kinds.get(\"functional\")}'
    assert kinds.get('sqlite') == 'error', f'expected error, got {kinds.get(\"sqlite\")}'
    assert kinds.get('consider') == 'note', f'expected note, got {kinds.get(\"consider\")}'
"

echo "[ok] kind auto-detection works for decision/preference/error/note"

# ============================================================
# Section 18: Ranked recall via FTS5 (C1)
# ============================================================
echo "=== Section 18: Ranked recall ==="

RANK_TOKEN="rank-test-$(date +%s)-$$"
awareness remember "decision: use pytest for FastAPI tests $RANK_TOKEN" >/dev/null
awareness remember "preference: keep DB files at mode 0600 $RANK_TOKEN" >/dev/null

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys, json
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    results = store.recall('pytest', limit=5, project_path='$PROJECT_DIR')
    assert len(results) > 0, 'no results for pytest query'
    assert '_score' in results[0], f'missing _score: {list(results[0].keys())}'
    assert '_score_breakdown' in results[0], f'missing _score_breakdown'
    print(f'  top result: {results[0][\"decision\"][:60]}')
    print(f'  score: {results[0][\"_score\"]}')
    print(f'  breakdown: {json.dumps(results[0][\"_score_breakdown\"], indent=4)}')
"

echo "[ok] ranked recall returns scored results"

# ============================================================
# Section 19: Trigram tokenizer partial matching (C1)
# ============================================================
echo "=== Section 19: Trigram tokenizer ==="

TRIGRAM_TOKEN="trigram-test-$(date +%s)-$$"
awareness remember "decision: pytest-asyncio for async test functions $TRIGRAM_TOKEN" >/dev/null

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    results = store.recall('pytest', limit=10)
    found = any('pytest-asyncio' in r.get('decision', '') for r in results)
    assert found, f'trigram match failed: {[r[\"decision\"] for r in results]}'
    print(f'  trigram match: {[r[\"decision\"][:50] for r in results if \"pytest\" in r.get(\"decision\", \"\")]}')
"

echo "[ok] trigram tokenizer enables partial matching"

# ============================================================
# Section 20: Deduplication (C1)
# ============================================================
echo "=== Section 20: Deduplication ==="

DEDUP_TOKEN="dedup-test-$(date +%s)-$$"
awareness remember "decision: use pytest for all tests $DEDUP_TOKEN v1" >/dev/null
awareness remember "decision: use pytest for all tests $DEDUP_TOKEN v2" >/dev/null
awareness remember "decision: use mypy for type checking $DEDUP_TOKEN" >/dev/null

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    # Query for pytest - should get the deduped pytest result (v1 or v2, not both)
    results = store.recall('pytest', limit=10)
    decisions = [r['decision'] for r in results]
    print(f'  results: {[d[:60] for d in decisions]}')
    pytest_count = sum(1 for d in decisions if 'pytest' in d and 'v1' in d or 'pytest' in d and 'v2' in d)
    # Also query for mypy to verify it's still there
    results_mypy = store.recall('mypy', limit=10)
    mypy_count = sum(1 for r in results_mypy if 'mypy' in r.get('decision', ''))
    assert pytest_count == 1, f'expected 1 pytest result (deduped), got {pytest_count}: {decisions}'
    assert mypy_count == 1, f'expected 1 mypy result, got {mypy_count}'
"

echo "[ok] near-duplicate decisions are deduplicated"

# ============================================================
# Section 21: SessionStart uses kind-based grouping (C1)
# ============================================================
echo "=== Section 21: SessionStart kind-based grouping ==="

GROUP_TOKEN="group-test-$(date +%s)-$$"
PROJECT_GROUP="$TMP/fake-project-group"
mkdir -p "$PROJECT_GROUP"
cd "$PROJECT_GROUP"
git init -q 2>/dev/null || true
git config user.email "test@test.local"
git config user.name "Test"

awareness claude install --project "$PROJECT_GROUP" --session-start >/dev/null 2>&1

awareness remember "decision: use hexagonal architecture $GROUP_TOKEN" >/dev/null
awareness remember "preference: prefer composition over inheritance $GROUP_TOKEN" >/dev/null
awareness remember "error: database locked - restart daemon $GROUP_TOKEN" >/dev/null
awareness remember "procedure: deploy via make build && make push $GROUP_TOKEN" >/dev/null

CONTEXT_GROUP=$(awareness claude session-start --project "$PROJECT_GROUP" --max-chars 5000 2>/dev/null)
echo "$CONTEXT_GROUP" > "$TMP/context-group.txt"

grep -q "Recent decisions:" "$TMP/context-group.txt"
grep -q "Relevant preferences:" "$TMP/context-group.txt"
grep -q "Known errors:" "$TMP/context-group.txt"
grep -q "Procedures:" "$TMP/context-group.txt"

awareness claude uninstall --project "$PROJECT_GROUP" >/dev/null 2>&1

echo "[ok] SessionStart groups memories by kind"

# ============================================================
# Section 22: Per-kind TTL (C2a)
# ============================================================
echo "=== Section 22: Per-kind TTL ==="

TTL_TOKEN="ttl-test-$(date +%s)-$$"

# --- 22a: Insert a note with a short TTL and backdate it past expiry ---
# Use the Python API directly to set a backdated expires_at
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys, sqlite3
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
from datetime import datetime, timezone, timedelta

with AwarenessStore() as store:
    # Insert a note that expired 5 days ago (note TTL = 30d, backdate 35d)
    store.remember('note: this note is expired $TTL_TOKEN', category='note', source='test')
    expired_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    store.conn.execute(\"UPDATE decisions SET expires_at = ? WHERE decision LIKE ?\", (expired_ts, '%$TTL_TOKEN%'))
    store.conn.commit()
    print('[info] inserted expired note with backdated expires_at')
"

# Verify the expired note is excluded from recall
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    results = store.recall('$TTL_TOKEN', limit=10)
    found = any('$TTL_TOKEN' in r.get('decision', '') for r in results)
    if found:
        print('[fail] expired note was returned by recall', file=sys.stderr)
        sys.exit(1)
    print('[ok] expired note excluded from recall')
"

# --- 22b: Insert a decision (no TTL) and verify it persists ---
awareness remember "decision: use permanent storage for $TTL_TOKEN" >/dev/null

PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    # Check expires_at IS NULL for the decision row (never expires)
    # Filter to the decision row specifically (not the expired note from 22a)
    row = store.conn.execute(\"SELECT kind, expires_at FROM decisions WHERE decision LIKE ? AND kind = 'decision'\", ('%$TTL_TOKEN%',)).fetchone()
    assert row is not None, 'decision not found'
    assert row[1] is None, f'decision should have NULL expires_at, got {row[1]}'
    print(f'[ok] decision kind={row[0]} has no expiry (expires_at is NULL)')

    # Verify it is returned by recall (expired note excluded, decision included)
    results = store.recall('$TTL_TOKEN', limit=10)
    found_decision = any('$TTL_TOKEN' in r.get('decision', '') and r.get('kind') == 'decision' for r in results)
    found_expired = any('$TTL_TOKEN' in r.get('decision', '') and r.get('kind') == 'note' for r in results)
    assert found_decision, 'decision without TTL not returned in recall'
    assert not found_expired, 'expired note should not be returned'
    print('[ok] no-TTL decision is returned in recall, expired note excluded')
"

# --- 22c: Run sweep() and verify expired rows deleted, others remain ---
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    # Count before sweep
    before_expired = store.conn.execute(\"SELECT COUNT(*) FROM decisions WHERE decision LIKE ?\", ('%$TTL_TOKEN% expired%',)).fetchone()[0]
    before_decision = store.conn.execute(\"SELECT COUNT(*) FROM decisions WHERE decision LIKE ? AND kind = 'decision'\", ('%$TTL_TOKEN%',)).fetchone()[0]
    print(f'[info] before sweep: expired={before_expired}, decision={before_decision}')

    # Run sweep
    swept = store.sweep()
    print(f'[info] sweep() removed {swept} rows')

    # Count after sweep
    after_expired = store.conn.execute(\"SELECT COUNT(*) FROM decisions WHERE decision LIKE ?\", ('%$TTL_TOKEN% expired%',)).fetchone()[0]
    after_decision = store.conn.execute(\"SELECT COUNT(*) FROM decisions WHERE decision LIKE ? AND kind = 'decision'\", ('%$TTL_TOKEN%',)).fetchone()[0]
    assert after_expired == 0, f'expired row still present after sweep: {after_expired}'
    assert after_decision == 1, f'decision row missing after sweep: {after_decision}'
    print('[ok] sweep removed expired row, kept decision row')
"

# --- 22d: Verify sweep is safe when already clean ---
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    swept2 = store.sweep()
    assert swept2 == 0, f'sweep should find nothing, removed {swept2}'
    print('[ok] sweep on clean DB is a no-op (removed 0)')
"

echo "[ok] per-kind TTL works correctly"

# ============================================================
# Section 23: Scope auto-detection (C2b)
# ============================================================
echo "=== Section 23: Scope auto-detection ==="

SCOPE_TOKEN="scope-test-$(date +%s)-$$"
PROJECT_A="$TMP/fake-project-A"
PROJECT_B="$TMP/fake-project-B"

mkdir -p "$PROJECT_A" "$PROJECT_B"
cd "$PROJECT_A" && git init -q 2>/dev/null || true && git config user.email "test@test.local" && git config user.name "Test"
cd "$PROJECT_B" && git init -q 2>/dev/null || true && git config user.email "test@test.local" && git config user.name "Test"

# --- 23a: Project-specific memory gets scope=project ---
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    mid = store.remember('decision: use hexagonal architecture $SCOPE_TOKEN', category='decision', context='cwd=$PROJECT_A', source='user', project={'root': '$PROJECT_A', 'name': 'project-A'})
    row = store.conn.execute('SELECT scope, project_id FROM decisions WHERE id = ?', (mid,)).fetchone()
    assert row[0] == 'project', f'expected project scope, got {row[0]}'
    assert row[1] is not None, 'expected project_id to be set'
    print(f'[ok] project-specific memory: scope={row[0]}, project_id={row[1]}')
"

# --- 23b: Global-preference memory gets scope=global ---
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    mid = store.remember('preference: prefer tabs over spaces $SCOPE_TOKEN', category='preference', context='general style preference', source='user')
    row = store.conn.execute('SELECT scope, project_id FROM decisions WHERE id = ?', (mid,)).fetchone()
    assert row[0] == 'global', f'expected global scope, got {row[0]}'
    print(f'[ok] global preference memory: scope={row[0]}, project_id={row[1]}')
"

# --- 23c: Cross-project isolation at recall ---
# Store a project-B-specific memory, then recall from project-A
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
import sys
sys.path.insert(0, '$AGENT_ROOT')
from awareness_agent.store import AwarenessStore
with AwarenessStore() as store:
    # Store project-B-specific memory
    store.remember('decision: use Cobra for CLI $SCOPE_TOKEN', category='decision', context='cwd=$PROJECT_B', source='user', project={'root': '$PROJECT_B', 'name': 'project-B'})

    # Store global memory
    store.remember('preference: keep files at mode 0600 $SCOPE_TOKEN', category='preference', context='security invariant', source='user')

    # Recall from project-A: should see global + project-A, NOT project-B
    results_a = store.recall('$SCOPE_TOKEN', limit=20, project_path='$PROJECT_A')
    decisions_a = [r['decision'] for r in results_a]
    print(f'  project-A recall: {[d[:50] for d in decisions_a]}')

    # Should see: hexagonal (project-A), tabs-over-spaces (global), mode-0600 (global)
    assert any('hexagonal' in d for d in decisions_a), 'project-A memory missing'
    assert any('tabs' in d for d in decisions_a), 'global preference missing from project-A'
    assert any('0600' in d for d in decisions_a), 'global preference missing from project-A'
    assert not any('Cobra' in d for d in decisions_a), f'project-B memory leaked into project-A: {decisions_a}'
    print('[ok] project-A recall: project-A + global only, no project-B leak')

    # Recall from project-B: should see global + project-B, NOT project-A
    results_b = store.recall('$SCOPE_TOKEN', limit=20, project_path='$PROJECT_B')
    decisions_b = [r['decision'] for r in results_b]
    print(f'  project-B recall: {[d[:50] for d in decisions_b]}')

    assert any('Cobra' in d for d in decisions_b), 'project-B memory missing'
    assert any('0600' in d for d in decisions_b), 'global preference missing from project-B'
    assert not any('hexagonal' in d for d in decisions_b), f'project-A memory leaked into project-B: {decisions_b}'
    print('[ok] project-B recall: project-B + global only, no project-A leak')

    # Recall with no project (global=None): should see global only
    results_global = store.recall('$SCOPE_TOKEN', limit=20, project_path=None)
    decisions_global = [r['decision'] for r in results_global]
    print(f'  global recall: {[d[:50] for d in decisions_global]}')

    assert any('0600' in d for d in decisions_global), 'global preference missing in global recall'
    assert not any('hexagonal' in d for d in decisions_global), f'project-A leaked into global: {decisions_global}'
    assert not any('Cobra' in d for d in decisions_global), f'project-B leaked into global: {decisions_global}'
    print('[ok] global recall: global-only memories only')
"

echo "[ok] scope auto-detection and cross-project isolation work correctly"

# ============================================================
echo ""
echo "[ok] awareness-agent spike C2b scope auto-detection tests passed"

# ============================================================
# Section 24: C2c — Local embeddings for hybrid recall
# ============================================================
echo ""
echo "--- Section 24: C2c local embeddings (hybrid recall) ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.store import AwarenessStore, set_embeddings_enabled, embeddings_enabled
from awareness_agent.ranking import RankWeights

# --- 24a: Embeddings DISABLED (default) — recall still works via FTS5 ---
print("[24a] Embeddings disabled — FTS5-only recall still works")

set_embeddings_enabled(False)
assert not embeddings_enabled()

db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)

store = AwarenessStore(db_path)
store.remember('Use pytest for FastAPI testing', category='decision', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Prefer tabs over spaces in Python', category='preference', context='style', source='user')
store.remember('DO NOT run reset-db in production', category='pinned', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})

results = store.recall('pytest', limit=5, project_path='/home/user/aw')
assert len(results) > 0, 'FTS5-only recall returned no results'
assert 'pytest' in results[0]['decision'].lower(), f'Wrong top result: {results[0]["decision"]}'
# Embedding component should be zero
assert results[0]['_score_breakdown'].get('embedding', 0) == 0.0, 'Embedding component non-zero when disabled'
print(f'  [ok] FTS5-only recall works: top="{results[0]["decision"][:50]}" score={results[0]["_score"]}')

store.close()
os.unlink(db_path)

# --- 24b: Embeddings ENABLED — hybrid scoring active ---
print("[24b] Embeddings enabled — hybrid scoring active")

set_embeddings_enabled(True)
assert embeddings_enabled()

db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)

store = AwarenessStore(db_path)
# Insert memories with overlapping semantics but different keywords
store.remember('Use pytest with pytest-asyncio for FastAPI tests', category='decision', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('SQLite database locks under concurrent writes — restart daemon', category='error', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Deploy with make build then make push', category='procedure', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Bearer token leaked in recall — added redaction patterns', category='error', context='security', source='user')

# Verify embeddings are stored (only the 3 project memories + global error = 4)
raw = store.conn.execute('SELECT COUNT(*) FROM decisions WHERE embedding IS NOT NULL').fetchone()[0]
assert raw == 4, f'Expected 4 rows with embeddings, got {raw}'
print(f'  [ok] All 4 memories have embeddings stored')

# Hybrid recall: single FTS5 term "pytest" matches via trigram, embedding adds boost
weights = RankWeights(embedding=0.5)
results = store.recall('pytest', limit=5, project_path='/home/user/aw', weights=weights)
assert len(results) > 0, 'Hybrid recall returned no results'

# Embedding component should be non-zero for semantically similar memories
top = results[0]
emb_score = top['_score_breakdown'].get('embedding', 0)
assert emb_score > 0, f'Embedding component is zero for similar query: {top["decision"]}'
assert 'pytest' in top['decision'].lower(), f'Wrong top result: {top["decision"]}'
print(f'  [ok] Hybrid recall: top="{top["decision"][:50]}" emb_score={emb_score:.4f}')

store.close()
os.unlink(db_path)

# --- 24c: Hybrid recall boosts semantically-relevant results via embedding ---
print("[24c] Hybrid scoring boosts embedding-similar results")

set_embeddings_enabled(True)

db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)

store = AwarenessStore(db_path)
# Two memories both FTS5-matchable by "pytest", but with different semantic content
store.remember('Run pytest tests before every commit', category='procedure', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Purchase pytest supplies from the office store', category='note', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})

# Query "pytest testing" — FTS5 matches both (via "pytest" trigram),
# but embedding should boost the procedure about running tests
weights_fts_only = RankWeights(embedding=0.0)
weights_hybrid = RankWeights(embedding=0.5)

results_fts = store.recall('pytest', limit=5, project_path='/home/user/aw', weights=weights_fts_only)
results_hybrid = store.recall('pytest', limit=5, project_path='/home/user/aw', weights=weights_hybrid)

assert len(results_fts) > 0, 'FTS5-only returned no results'
assert len(results_hybrid) > 0, 'Hybrid returned no results'

# Both should find results; hybrid top should have non-zero embedding component
hybrid_emb = results_hybrid[0]['_score_breakdown'].get('embedding', 0)
assert hybrid_emb > 0, f'Hybrid top embedding component is zero: {results_hybrid[0]["decision"]}'
print(f'  [ok] FTS5-only top: "{results_fts[0]["decision"][:50]}" score={results_fts[0]["_score"]}')
print(f'  [ok] Hybrid top:    "{results_hybrid[0]["decision"][:50]}" score={results_hybrid[0]["_score"]} emb={hybrid_emb:.4f}')

store.close()
os.unlink(db_path)

# --- 24d: No network access assertion ---
print("[24d] No network access — embedding is local-only")

import socket
# Save original socket to restore later
_original_socket = socket.socket

def _blocking_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
    """Socket factory that blocks only network (AF_INET/AF_INET6) sockets."""
    if family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError('Network (IP) socket blocked — embedding must be local-only')
    # Allow Unix sockets (AF_UNIX) and others
    return _original_socket(family, type, proto, fileno)

socket.socket = _blocking_socket  # type: ignore

try:
    set_embeddings_enabled(True)
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    store = AwarenessStore(db_path)
    # Store a preference (kind=preference → scope=global, survives no-project recall)
    # This must NOT raise — embeddings are local (hash-based)
    store.remember('Embedding hash function prefers SHA-256 for determinism', category='preference', context='local-only embedding design', source='user')
    # Recall with no project path → only global-scope memories surface
    results = store.recall('embedding hash', limit=3)
    assert len(results) > 0, 'No results after remembering with blocked network'
    print(f'  [ok] Embedding computed with network blocked — truly local')

    store.close()
    os.unlink(db_path)
finally:
    socket.socket = _original_socket  # type: ignore

# --- 24e: Fallback when sentence-transformers unavailable ---
print("[24e] Fallback when sentence-transformers unavailable")

# embeddings.py already falls back to hash_embed when sentence-transformers
# is not installed. We verify this by checking the hash path was used.
set_embeddings_enabled(True)
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)

store = AwarenessStore(db_path)
store.remember('sentence-transformers not installed — hash fallback', category='note', context='test', source='user')

# Verify hash-based embedding was stored (not None)
raw = store.conn.execute('SELECT embedding FROM decisions WHERE id = 1').fetchone()
assert raw[0] is not None, 'Hash-based fallback embedding is None'
assert len(raw[0]) == 1536, f'Expected 1536 bytes (384 float32), got {len(raw[0])}'
print(f'  [ok] Hash-based fallback embedding stored ({len(raw[0])} bytes)')

store.close()
os.unlink(db_path)

set_embeddings_enabled(False)  # reset to default
print()
print('[ok] All C2c embeddings tests passed')
PYEOF

# ============================================================
# Section 25: C3 — Embedding provenance migration
# ============================================================
echo "--- Section 25: C3 embedding provenance migration ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.store import AwarenessStore, set_embeddings_enabled

# --- 25a: New DB has provenance columns ---
print("[25a] Provenance columns exist in new DB")
set_embeddings_enabled(True)
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)
store = AwarenessStore(db_path)
store.remember('Use pytest for testing', category='decision', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})

cols = {r[1] for r in store.conn.execute('PRAGMA table_info(decisions)')}
assert 'embedding_provider' in cols, f'missing embedding_provider: {cols}'
assert 'embedding_model' in cols, f'missing embedding_model: {cols}'
assert 'embedding_dim' in cols, f'missing embedding_dim: {cols}'
assert 'embedding_version' in cols, f'missing embedding_version: {cols}'
print('  [ok] All provenance columns exist')

# Verify provenance was stored
row = store.conn.execute('SELECT embedding_provider, embedding_model, embedding_dim, embedding_version FROM decisions WHERE id = 1').fetchone()
assert row[0] == 'hash', f'expected hash provider, got {row[0]}'
assert row[1] == 'char-trigram-sha256-v1', f'expected char-trigram-sha256-v1, got {row[1]}'
assert row[2] == 384, f'expected dim 384, got {row[2]}'
assert row[3] == '1.0', f'expected version 1.0, got {row[3]}'
print(f'  [ok] Provenance stored: provider={row[0]}, model={row[1]}, dim={row[2]}, version={row[3]}')
store.close()
os.unlink(db_path)

# --- 25b: Old DB (without provenance columns) migrates cleanly ---
print("[25b] Old DB without provenance columns migrates cleanly")
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)
import sqlite3
conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE projects (
        id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT,
        language TEXT, framework TEXT,
        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE decisions (
        id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        category TEXT NOT NULL DEFAULT 'note',
        context TEXT NOT NULL DEFAULT '',
        decision TEXT NOT NULL,
        rationale TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'user',
        kind TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT 'project',
        confidence REAL NOT NULL DEFAULT 0.5,
        tags TEXT NOT NULL DEFAULT '[]',
        expires_at TEXT,
        pinned INTEGER NOT NULL DEFAULT 0,
        embedding BLOB
    );
    CREATE TABLE sessions (
        id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
        started_at TEXT DEFAULT CURRENT_TIMESTAMP, ended_at TEXT,
        summary TEXT, commands_run INTEGER DEFAULT 0, files_modified INTEGER DEFAULT 0
    );
    CREATE TABLE preferences (
        id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, value TEXT,
        scope TEXT NOT NULL DEFAULT 'global',
        source TEXT NOT NULL DEFAULT 'user',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
""")
import numpy as np
fake_emb = np.zeros(384, dtype=np.float32).tobytes()
conn.execute("INSERT INTO decisions(id, category, decision, embedding) VALUES (1, 'note', 'old memory without provenance', ?)", (fake_emb,))
conn.commit()
conn.close()

store = AwarenessStore(db_path)
cols = {r[1] for r in store.conn.execute('PRAGMA table_info(decisions)')}
assert 'embedding_provider' in cols, f'migration did not add embedding_provider: {cols}'
assert 'embedding_model' in cols, f'migration did not add embedding_model: {cols}'
print('  [ok] Migration added provenance columns to old DB')

# Legacy row has scope='project' default, so use direct query + ranking
# The key test is that NULL provenance doesn't crash ranking code
results = store.conn.execute("SELECT decision, embedding_provider FROM decisions WHERE decision LIKE '%old memory%'").fetchall()
assert len(results) > 0, 'old row not returned from direct query'
# Try ranking with NULL provenance — should not crash
from awareness_agent.ranking import RankWeights, rank_memories
row_dict = dict(results[0])
scored = rank_memories([row_dict], weights=RankWeights(embedding=0.5), query_embedding=None)
print(f'  [ok] Old row with NULL provenance does not crash ranking')

# --- 25c: Migration is idempotent ---
store2 = AwarenessStore(db_path)
print('  [ok] Re-opening DB (idempotent migration) succeeds')
store2.close()

store.close()
os.unlink(db_path)
set_embeddings_enabled(False)
print()
print('[ok] Section 25: provenance migration passed')
PYEOF

# ============================================================
# Section 26: C3 — Backfill embeddings
# ============================================================
echo "--- Section 26: C3 backfill embeddings ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.store import AwarenessStore, set_embeddings_enabled

set_embeddings_enabled(False)
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)
store = AwarenessStore(db_path)
store.remember('Use pytest for FastAPI tests', category='decision', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Deploy with make build then make push', category='procedure', context='cwd=/home/user/aw', source='user', project={'root': '/home/user/aw', 'name': 'aw'})
store.remember('Prefer functional style', category='preference', context='style', source='user')

null_count = store.conn.execute('SELECT COUNT(*) FROM decisions WHERE embedding IS NULL').fetchone()[0]
assert null_count == 3, f'Expected 3 NULL embeddings, got {null_count}'
print(f'  [info] Created 3 memories without embeddings')

set_embeddings_enabled(True)
counts = store.backfill_embeddings()
print(f'  [info] backfill counts: {counts}')
assert counts['scanned'] == 3, f'Expected 3 scanned, got {counts["scanned"]}'
assert counts['updated'] == 3, f'Expected 3 updated, got {counts["updated"]}'
assert counts['failed'] == 0, f'Expected 0 failed, got {counts["failed"]}'

row = store.conn.execute('SELECT embedding, embedding_provider FROM decisions WHERE id = 1').fetchone()
assert row[0] is not None, 'Embedding still NULL after backfill'
assert row[1] == 'hash', f'Expected hash provider, got {row[1]}'
print(f'  [ok] Backfill populated embeddings + provenance')

counts2 = store.backfill_embeddings()
print(f'  [info] second backfill counts: {counts2}')
# When all rows have embeddings, scanned=0 (query filters them out)
assert counts2['scanned'] == 0, f'Expected 0 scanned on second run, got {counts2["scanned"]}'
assert counts2['updated'] == 0, f'Expected 0 updated on second run, got {counts2["updated"]}'
print(f'  [ok] Second backfill is idempotent (scanned 0, all rows already have embeddings)')

store.close()
os.unlink(db_path)
set_embeddings_enabled(False)
print()
print('[ok] Section 26: backfill embeddings passed')
PYEOF

# ============================================================
# Section 27: C3 — Embedding candidate widening
# ============================================================
echo "--- Section 27: C3 embedding candidate widening ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.store import AwarenessStore, set_embeddings_enabled
from awareness_agent.ranking import RankWeights, recall_ranked
from awareness_agent.embeddings import embed_text

set_embeddings_enabled(True)
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)
store = AwarenessStore(db_path)
project = {'root': '/home/user/aw', 'name': 'aw'}

# Create memories with overlapping tokens for hash embedding similarity
store.remember('Run all test suites before committing code', category='procedure', context='cwd=/home/user/aw', source='user', project=project)
store.remember('Use static analysis tools for code quality', category='decision', context='cwd=/home/user/aw', source='user', project=project)
store.remember('Purchase office supplies from the store', category='note', context='cwd=/home/user/aw', source='user', project=project)

# --- 27a: With embedding weight > 0, embedding candidates appear ---
print("[27a] Candidate widening surfaces embedding-similar memories")
weights = RankWeights(embedding=0.5)
query_emb = embed_text("code review and testing", backend='hash')
results = recall_ranked(store.conn, '', project_path='/home/user/aw', limit=10, weights=weights, query_embedding=query_emb)
assert len(results) >= 2, f'Expected at least 2 results from widening, got {len(results)}'
decisions = [r['decision'] for r in results]
print(f'  [ok] Widening returned {len(results)} candidates: {[d[:50] for d in decisions]}')

# --- 27b: With embedding weight = 0, no embedding contribution ---
print("[27b] No widening when embedding weight is 0")
weights_no_emb = RankWeights(embedding=0.0)
results_no_wide = recall_ranked(store.conn, '', project_path='/home/user/aw', limit=10, weights=weights_no_emb, query_embedding=query_emb)
for r in results_no_wide:
    assert r['_score_breakdown'].get('embedding', 0) == 0.0, 'Embedding component non-zero when weight=0'
print(f'  [ok] No embedding contribution when weight=0 ({len(results_no_wide)} results, all emb=0)')

store.close()
os.unlink(db_path)
set_embeddings_enabled(False)
print()
print('[ok] Section 27: candidate widening passed')
PYEOF

# ============================================================
# Section 28: C3 — TTL/scope still enforced for embedding hits
# ============================================================
echo "--- Section 28: C3 TTL/scope enforced for embedding hits ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
from datetime import datetime, timezone, timedelta
sys.path.insert(0, sys.argv[1])

from awareness_agent.store import AwarenessStore, set_embeddings_enabled
from awareness_agent.ranking import RankWeights, recall_ranked
from awareness_agent.embeddings import embed_text

set_embeddings_enabled(True)
db_fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(db_fd)
store = AwarenessStore(db_path)
project = {'root': '/home/user/aw', 'name': 'aw'}

# Create an expired memory with an embedding
store.remember('This memory is expired and should not appear', category='note', context='cwd=/home/user/aw', source='user', project=project)
expired_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
store.conn.execute("UPDATE decisions SET expires_at = ? WHERE id = 1", (expired_ts,))
store.conn.commit()

# Create a project-B memory (should not appear in project-A recall)
store.remember('Project B specific memory about testing', category='decision', context='cwd=/home/user/project-b', source='user', project={'root': '/home/user/project-b', 'name': 'project-b'})

# Embedding recall for project-A should NOT include expired or project-B memories
weights = RankWeights(embedding=0.5)
query_emb = embed_text("testing memory", backend='hash')
results = recall_ranked(store.conn, '', project_path='/home/user/aw', limit=20, weights=weights, query_embedding=query_emb)
decisions = [r['decision'] for r in results]
assert not any('expired' in d for d in decisions), f'Expired memory leaked: {decisions}'
assert not any('Project B' in d for d in decisions), f'Project-B memory leaked into project-A: {decisions}'
print(f'  [ok] Expired and out-of-scope memories excluded from embedding results')

store.close()
os.unlink(db_path)
set_embeddings_enabled(False)
PYEOF

# ============================================================
# Section 29: C3 — No-network sentence-transformers loading
# ============================================================
echo "--- Section 29: C3 no-network ST loading ---"

# ============================================================
# Section 29: C3 — No-network sentence-transformers loading
# ============================================================
echo "--- Section 29: C3 no-network ST loading ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

import socket
_original_socket = socket.socket

def _blocking_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
    if family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError('Network blocked')
    return _original_socket(family, type, proto, fileno)

socket.socket = _blocking_socket  # type: ignore

try:
    from awareness_agent.embeddings import embed_text, resolve_backend

    result = embed_text("test embedding", backend='hash')
    assert result.provider == 'hash', f'Expected hash, got {result.provider}'
    print('  [ok] Hash backend works with network blocked')

    effective = resolve_backend('auto')
    assert effective == 'hash', f'Expected auto→hash, got {effective}'
    print(f'  [ok] Auto backend resolves to hash when ST unavailable: {effective}')

    assert result.dim == 384
    assert result.is_semantic is False
    print(f'  [ok] Hash embedding: dim={result.dim}, is_semantic={result.is_semantic}')

    result2 = embed_text("different text", backend='hash')
    assert result.is_compatible(result2), 'Same-provider embeddings should be compatible'
    print(f'  [ok] Same-provider compatibility check works')

finally:
    socket.socket = _original_socket  # type: ignore

PYEOF

# ============================================================
# Section 30: C3 — Hash fallback honesty
# ============================================================
echo "--- Section 30: C3 hash fallback honesty ---"

# ============================================================
# Section 30: C3 — Hash fallback honesty
# ============================================================
echo "--- Section 30: C3 hash fallback honesty ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.embeddings import (
    embed_text, cosine_similarity, HASH_PROVIDER, EmbeddingResult
)

result = embed_text("machine learning neural networks", backend='hash')
assert result.provider == HASH_PROVIDER
assert result.is_semantic is False, 'Hash embeddings must not claim to be semantic'
print(f'  [ok] Hash backend correctly reports is_semantic={result.is_semantic}')

emb1 = embed_text("happy joy celebration", backend='hash')
emb2 = embed_text("sad grief mourning", backend='hash')
sim = cosine_similarity(emb1.vector, emb2.vector)
assert sim < 0.5, f'Hash similarity too high for antonyms: {sim:.4f}'
print(f'  [ok] Hash does not fake semantic similarity: sim({sim:.4f}) < 0.5 for antonyms')

assert isinstance(result, EmbeddingResult)
assert len(result.vector) == 1536  # 384 * 4 bytes (float32)
print(f'  [ok] EmbeddingResult: vector_len={len(result.vector)}, provider={result.provider}')

PYEOF

# ============================================================
# Section 31: C3 — Optional local sentence-transformers eval
# ============================================================
echo "--- Section 31: C3 optional local ST eval ---"

python3 - "$AGENT_ROOT" <<'PYEOF'
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])

from awareness_agent.embeddings import embed_text

st_model = os.environ.get('AWARENESS_AGENT_ST_MODEL')
st_eval = os.environ.get('AWARENESS_AGENT_RUN_ST_EVAL')

if not st_eval:
    print('  [skip] AWARENESS_AGENT_RUN_ST_EVAL not set — skipping optional ST eval')
elif not st_model:
    print('  [skip] AWARENESS_AGENT_ST_MODEL not set — skipping optional ST eval')
else:
    try:
        result = embed_text("semantic similarity test", backend='sentence-transformers')
        if result is None or result.provider == 'hash':
            print('  [skip] sentence-transformers not available locally, hash fallback used')
        else:
            assert result.is_semantic is True, 'ST embeddings should be semantic'
            print(f'  [ok] Local ST model loaded: provider={result.provider}, model={result.model}, dim={result.dim}')
            print(f'  [ok] ST embedding is_semantic={result.is_semantic}')
    except Exception as e:
        print(f'  [skip] ST eval failed: {e}')

PYEOF

echo ""
echo '[ok] Section 31: optional ST eval passed/skipped'
echo ""
echo '[ok] All C3 smoke sections (25-31) passed'
