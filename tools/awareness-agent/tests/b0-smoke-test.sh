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
echo ""
echo "[ok] awareness-agent spike C1 integration tests passed"
