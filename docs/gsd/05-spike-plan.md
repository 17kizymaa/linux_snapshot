# Spike Plan — Experiment Selection

> Phase 5 — Three possible spikes, one recommendation

## Spike A: Minimal Daemon Skeleton + CLI Query

**Goal**: Prove that a local daemon can maintain context and respond to queries via Unix socket.

### Scope
- Python daemon with systemd --user service
- Unix socket IPC (JSON-RPC 2.0)
- SQLite store with `projects`, `sessions`, `decisions` tables
- CLI tool (`awareness`) for query/add/status
- Git context provider (auto-detect project)
- Config file (`~/.config/awareness-agent/config.toml`)

### Estimated Effort
- **Time**: 4-6 hours
- **Files created**: ~8 new files
- **Files modified**: 0 existing files

### Files to Create
```
~/.config/awareness-agent/config.toml     — Default config
~/.config/systemd/user/awareness-agent.service — systemd service
~/.local/bin/awareness                    — CLI entry point
~/.local/lib/awareness-agent/
  __init__.py
  daemon.py                               — Main daemon loop
  server.py                               — Unix socket server
  store.py                                — SQLite operations
  providers/
    __init__.py
    base.py                               — Provider interface
    git.py                                — Git context provider
  models/
    __init__.py
    ego.py                                — Ego/preferences model
  redaction.py                            — Redaction engine
```

### Dependencies
- Python 3.14 (already installed)
- No new packages required (stdlib: sqlite3, json, socket, pathlib, tomllib)

### Risks
- **Low**: No external dependencies, no network, no privilege escalation
- **Risk**: systemd user session may not be available in all environments
- **Mitigation**: Daemon can also run in foreground for testing

### Acceptance Criteria
1. `awareness start` starts the daemon
2. `awareness status` shows daemon running + current project
3. `awareness remember "test decision"` stores a decision
4. `awareness recall "test"` returns the stored decision
5. `awareness context project` shows git repo info
6. Daemon survives restart (`awareness restart`)
7. All data stored in SQLite, survives reboot

### How to Test
```bash
bash ~/.local/lib/awareness-agent/tests/smoke-test.sh
```

---

## Spike B: ClaudeCode Slash-Command/Plugin Improvement

**Goal**: Prove that the awareness concept works within the existing CC/GSD skill system.

### Scope
- New GSD-style skill: `awareness` (context recall + memory)
- New hook: session-start context injection
- New agent: `awareness-researcher` (searches local context)
- Integration with existing GSD planning system
- Uses existing ChromaDB for semantic search

### Estimated Effort
- **Time**: 3-4 hours
- **Files created**: ~5 new files
- **Files modified**: 0 existing files (new skill/hook/agent)

### Files to Create
```
~/.claude/skills/awareness/
  SKILL.md                               — Skill definition
  scripts/
    context.sh                           — Context query script
    remember.sh                          — Memory store script
~/.claude/hooks/
  awareness-context-inject.js            — Session-start context injection
~/.claude/agents/
  awareness-researcher.md                — Agent definition
~/.local/share/awareness-agent/
  awareness.db                           — SQLite database (shared with Spike A)
```

### Dependencies
- Existing GSD system (already installed)
- Existing ChromaDB (already installed)
- bash + Python (already available)

### Risks
- **Low**: Uses existing extension points, no daemon needed
- **Risk**: Skills are prompt-level only — can't maintain persistent state between sessions without external storage
- **Mitigation**: Skill scripts write to SQLite, which persists across sessions

### Acceptance Criteria
1. `/awareness context` returns current project context
2. `/awareness remember` stores a decision
3. `/awareness recall` searches stored decisions
4. Session-start hook injects project context into CC session
5. `awareness-researcher` agent can search context independently

### How to Test
```bash
# In Claude Code:
/awareness context
/awareness remember "test: spike B decision"
/awareness recall "spike B"
```

---

## Spike C: Explicit-Selection Semantic Action Prototype

**Goal**: Prove that selected text can be processed with local context for semantic actions.

### Scope
- CLI tool that takes selected text as input
- Three semantic actions: `explain`, `find-related`, `summarize`
- Uses local context (project info, past decisions) to enrich the action
- Optional: local model inference via Ollama
- Integration with terminal selection (xclip/xsel) and editor (VS Code CLI)

### Estimated Effort
- **Time**: 6-8 hours
- **Files created**: ~6 new files
- **Files modified**: 0 existing files

### Files to Create
```
~/.local/bin/awareness-action           — Semantic action CLI
~/.local/lib/awareness-agent/
  actions/
    __init__.py
    explain.py                           — Explain selected text
    find_related.py                      — Find related context
    summarize.py                         — Summarize selected text
  context_enrichment.py                 — Enrich selection with local context
~/.config/awareness-agent/
  actions.toml                          — Action configuration
```

### Dependencies
- Python 3.14 (already installed)
- xclip or xsel (for terminal selection — may need install)
- Ollama (already installed, optional for local inference)

### Risks
- **Medium**: Requires clipboard/selection integration (platform-specific)
- **Risk**: xclip/xsel may not be installed
- **Mitigation**: Accept text via stdin as fallback
- **Risk**: Local model inference may be slow
- **Mitigation**: Make inference optional, context-only mode works without it

### Acceptance Criteria
1. `echo "some error" | awareness-action explain` returns explanation with context
2. `awareness-action find-related --text "authentication"` returns related decisions
3. `awareness-action summarize --file docs/architecture.md` returns summary
4. Works with terminal selection (Ctrl+Shift+C → pipe to action)
5. Works without Ollama (context-only mode)

### How to Test
```bash
# Terminal selection
echo "FastAPI CORS middleware configuration" | awareness-action explain

# File input
awareness-action summarize --file README.md

# Find related
awareness-action find-related --text "database migration"
```

---

## Recommendation: Spike A (Minimal Daemon Skeleton)

### Why Spike A

| Criterion | Spike A | Spike B | Spike C |
|-----------|---------|---------|---------|
| **Proves core concept** | ✅ Yes — persistent daemon | Partial — skill-level only | Partial — action-level only |
| **Independence** | ✅ Standalone | Depends on CC/GSD | Depends on daemon or CC |
| **Reversibility** | ✅ Trivial cleanup | Trivial cleanup | Trivial cleanup |
| **Effort** | 4-6 hours | 3-4 hours | 6-8 hours |
| **Risk** | Low | Low | Medium |
| **Foundation for v1** | ✅ Yes — daemon is the foundation | No — skills are additive | Needs daemon or CC |
| **No external deps** | ✅ stdlib only | ✅ Uses existing | ⚠️ May need xclip |
| **Testability** | ✅ Smoke test script | Manual in CC | Manual in terminal |

**Spike A is the best first move** because:
1. It builds the **foundation** that Spikes B and C depend on
2. It proves the core concept: a persistent, local-only daemon with context awareness
3. It's fully reversible (single directory + systemd service)
4. It has no external dependencies
5. It's testable with a simple smoke test
6. The daemon can later be extended with CC skills (Spike B) and semantic actions (Spike C)

### Recommended Sequence
1. **Spike A** now — build the daemon foundation
2. **Spike B** next — add CC skill integration on top of the daemon
3. **Spike C** last — add semantic actions using the daemon's context

### If Spike A Succeeds
The daemon skeleton becomes the core of the awareness agent. Next steps:
- Add more providers (shell, editor, model telemetry)
- Add semantic search (sqlite-vec)
- Add CC skill integration (Spike B)
- Add CLI tray icon
- Add web dashboard (optional)

### If Spike A Fails
The entire system is contained in `~/.local/lib/awareness-agent/` and `~/.config/awareness-agent/`. Removal:
```bash
systemctl --user disable --now awareness-agent
rm -rf ~/.local/lib/awareness-agent
rm -rf ~/.config/awareness-agent
rm -rf ~/.local/share/awareness-agent
rm ~/.local/bin/awareness
```
