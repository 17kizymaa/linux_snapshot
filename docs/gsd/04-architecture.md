# Awareness Agent — Architecture

> Phase 4 — Local-first Linux daemon design

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐             │
│  │ CLI      │  │ CC Skill │  │ Tray Icon │             │
│  │ awareness│  │ /aware   │  │ (optional)│             │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘             │
│       │              │              │                    │
├───────┼──────────────┼──────────────┼────────────────────┤
│       │        IPC Layer           │                    │
│  ┌────┴──────────────┴──────────────┴────┐              │
│  │  Unix Socket (/run/user/UID/aware.sock)│              │
│  │  or DBus (org.local.AwarenessAgent)    │              │
│  └────────────────┬───────────────────────┘              │
│                   │                                      │
├───────────────────┼──────────────────────────────────────┤
│           Daemon Core (systemd --user)                   │
│  ┌────────────────┴───────────────────────┐              │
│  │  awareness-daemon                      │              │
│  │  ┌─────────────┐  ┌──────────────────┐ │              │
│  │  │ Context     │  │ Memory Store     │ │              │
│  │  │ Providers   │  │ (SQLite)         │ │              │
│  │  │             │  │                  │ │              │
│  │  │ • git       │  │ • projects       │ │              │
│  │  │ • filesystem│  │ • sessions       │ │              │
│  │  │ • shell     │  │ • preferences    │ │              │
│  │  │ • editor    │  │ • history        │ │              │
│  │  │ • clipboard │  │ • decisions      │ │              │
│  │  │ • config    │  │                  │ │              │
│  │  └─────────────┘  └──────────────────┘ │              │
│  │  ┌─────────────┐  ┌──────────────────┐ │              │
│  │  │ Model       │  │ Redaction        │ │              │
│  │  │ Adapter     │  │ Engine           │ │              │
│  │  │             │  │                  │ │              │
│  │  │ • Ollama    │  │ • patterns       │ │              │
│  │  │ • llama.cpp │  │ • retention      │ │              │
│  │  │ • LM Studio │  │ • encryption     │ │              │
│  │  │ • custom    │  │                  │ │              │
│  │  └─────────────┘  └──────────────────┘ │              │
│  └────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────┘
```

## systemd --user Service

```ini
# ~/.config/systemd/user/awareness-agent.service
[Unit]
Description=Awareness Agent — Local Context Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/awareness-daemon
Restart=on-failure
RestartSec=5
Environment=XDG_CONFIG_HOME=%h/.config
Environment=XDG_DATA_HOME=%h/.local/share
Environment=XDG_RUNTIME_DIR=/run/user/%U

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.local/share/awareness-agent %h/.config/awareness-agent /run/user/%U
PrivateTmp=yes

[Install]
WantedBy=default.target
```

**Key design decisions**:
- `--user` service (no root required)
- `ProtectSystem=strict` + explicit `ReadWritePaths` (minimal filesystem access)
- `NoNewPrivileges=yes` (cannot escalate)
- `PrivateTmp=yes` (isolated /tmp)
- Restarts on failure, 5-second backoff

## Local IPC — Unix Socket (Primary)

```python
# Socket path: $XDG_RUNTIME_DIR/awareness-agent.sock
# Permissions: 0600 (user-only)

# Protocol: JSON-RPC 2.0 over newline-delimited JSON
# Each message is a single JSON object followed by \n

# Request:
{"jsonrpc": "2.0", "method": "context.get", "params": {"key": "project.name"}, "id": 1}

# Response:
{"jsonrpc": "2.0", "result": "aetherOS", "id": 1}

# Error:
{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Unknown key"}, "id": 1}
```

**Why Unix socket over DBus**:
- Simpler to implement (no dbus dependency)
- Lower latency for local-only communication
- Easier to secure (filesystem permissions)
- DBus can be added later as an alternative transport

**Why JSON-RPC 2.0**:
- Standard, well-documented
- Request/response pairing via `id`
- Error handling built-in
- Easy to implement in any language

## Plugin / Provider Model

```python
# Provider interface
class ContextProvider(ABC):
    @property
    def name(self) -> str: ...

    @property
    def requires_opt_in(self) -> bool: bool = False

    async def collect(self, scope: ContextScope) -> dict[str, Any]: ...

    async def subscribe(self, callback: Callable) -> None: ...  # optional

# Example providers
class GitProvider(ContextProvider):
    name = "git"
    # Collects: repo root, branch, recent commits, remotes, status

class FilesystemProvider(ContextProvider):
    name = "filesystem"
    # Collects: project structure, key files, .editorconfig, etc.

class ShellProvider(ContextProvider):
    name = "shell"
    requires_opt_in = True  # Shell history may contain secrets
    # Collects: recent commands (filtered), working directory, env vars (whitelisted)

class EditorProvider(ContextProvider):
    name = "editor"
    requires_opt_in = True
    # Collects: current file, cursor position, open buffers (opt-in per editor)

class ClipboardProvider(ContextProvider):
    name = "clipboard"
    requires_opt_in = True
    # Only reads clipboard when explicitly invoked (not polling)

class ConfigProvider(ContextProvider):
    name = "config"
    # Collects: user preferences, ego model, project config

class ModelTelemetryProvider(ContextProvider):
    name = "model_telemetry"
    # Collects: available runtimes, loaded models, VRAM usage, latency stats
```

**Provider registration**:
```python
# providers.toml (user-configurable)
[provider.git]
enabled = true

[provider.shell]
enabled = true
history_lines = 100
redact_patterns = ["*password*", "*token*", "*key*", "*secret*"]

[provider.editor]
enabled = false  # opt-in

[provider.clipboard]
enabled = false  # explicit invoke only
```

## Context Providers — Detailed Design

### Current Project/Repo Provider
- Trigger: On daemon start + git directory change
- Data: repo root, remote URL, branch, last 10 commits, status summary
- Storage: `projects` table in SQLite
- Privacy: Only stores metadata, never file contents

### Shell/Session Metadata Provider
- Trigger: Opt-in, configured per-shell
- Data: Last N commands (filtered), CWD, session duration
- Redaction: Pattern-based redaction of sensitive commands
- Storage: `sessions` table, auto-expires after retention period
- Privacy: User must explicitly enable; redaction patterns configurable

### Editor Integration Provider
- Trigger: Opt-in, per-editor plugin
- Data: Current file, project-relative path, language, cursor context
- Storage: Ephemeral (not persisted, only used for current query)
- Privacy: Only active file, never file contents

### Clipboard/Selection Provider
- Trigger: Explicit invocation only (never polling)
- Data: Selected text at moment of invocation
- Storage: Never stored (processed in-memory, discarded after use)
- Privacy: Zero retention

### Local Config/Preferences Provider
- Trigger: On daemon start + file change
- Data: User preferences, ego model, project constraints
- Storage: `preferences` table + JSON files in config dir
- Privacy: User-controlled, transparent

### Model/Runtime Telemetry Provider
- Trigger: Periodic polling (configurable interval, default 60s)
- Data: Available runtimes (Ollama, llama.cpp, LM Studio), loaded models, VRAM
- Storage: Ephemeral (last known state only)
- Privacy: No network calls, local queries only

## Memory Store Design

### SQLite Schema

```sql
-- Projects the user works on
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT,
    description TEXT,
    language TEXT,
    framework TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON DEFAULT '{}'
);

-- Working sessions
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    summary TEXT,
    commands_run INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0
);

-- Decisions and learnings
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category TEXT,  -- 'architectural', 'style', 'tooling', 'bug_fix'
    context TEXT,   -- what was the situation
    decision TEXT,  -- what was decided
    rationale TEXT,  -- why
    source TEXT     -- 'user', 'agent', 'inferred'
);

-- User preferences (ego)
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    scope TEXT DEFAULT 'global',  -- 'global', 'project', 'language'
    source TEXT DEFAULT 'user',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model telemetry (ephemeral)
CREATE TABLE model_states (
    id INTEGER PRIMARY KEY,
    runtime TEXT NOT NULL,  -- 'ollama', 'llamacpp', 'lmstudio'
    model_name TEXT,
    context_size INTEGER,
    vram_mb INTEGER,
    latency_ms INTEGER,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_projects_path ON projects(path);
CREATE INDEX idx_sessions_project ON sessions(project_id);
CREATE INDEX idx_decisions_project ON decisions(project_id);
CREATE INDEX idx_decisions_category ON decisions(category);
CREATE INDEX idx_preferences_key ON preferences(key);
```

### Optional Vector Index

For semantic search over decisions and context:

```python
# Using sqlite-vec (lightweight, no separate service)
# or ChromaDB (already installed, but heavier)

# For POC: skip vector index, use SQLite FTS5 for text search
# For v1: add sqlite-vec for semantic similarity

CREATE VIRTUAL TABLE decisions_fts USING fts5(
    context, decision, rationale,
    content='decisions',
    content_rowid='id'
);
```

### Storage Locations (XDG Compliant)

```
~/.config/awareness-agent/     — Config files
  config.toml                  — Main config
  providers.toml               — Provider config
  redaction.toml               — Redaction patterns
  ego.json                     — User preferences/goals/constraints

~/.local/share/awareness-agent/ — Data
  awareness.db                 — SQLite database
  vector/                      — Vector index (if enabled)

~/.local/state/awareness-agent/ — State
  daemon.pid                   — PID file
  daemon.log                   — Daemon logs

/run/user/UID/                 — Runtime
  awareness-agent.sock         — Unix socket
```

## Redaction and Retention Policy

### Redaction Rules

```toml
# redaction.toml
[[pattern]]
match = "*password*"
action = "redact_word"  # replace the value with ***

[[pattern]]
match = "*token*"
action = "redact_word"

[[pattern]]
match = "*secret*"
action = "redact_word"

[[pattern]]
match = "*api_key*"
action = "redact_word"

[[pattern]]
match = "sk-*"
action = "redact_full"  # looks like an API key

[[pattern]]
match = "ghp_*"
action = "redact_full"  # GitHub PAT

# Regex patterns
[[regex]]
pattern = "Bearer\\s+[A-Za-z0-9._-]+"
action = "redact_match"

[[regex]]
pattern = "[a-zA-Z0-9+/]{40,}"
action = "flag_for_review"  # might be a key/hash
```

### Retention Policy

| Data Type | Default Retention | Configurable |
|-----------|------------------|--------------|
| Project metadata | Forever (until deleted) | Yes |
| Session data | 30 days | Yes |
| Decisions | Forever | Yes |
| Preferences | Forever | Yes |
| Shell commands | 7 days | Yes |
| Model telemetry | 24 hours | Yes |
| Clipboard content | Never stored | N/A |

## Model Adapter Abstraction

```python
class ModelAdapter(ABC):
    """Abstract interface for local model runtimes."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def infer(self, prompt: str, context: list[str],
                    model: str | None = None) -> str: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

class OllamaAdapter(ModelAdapter):
    """Adapter for Ollama (already installed)."""
    base_url: str = "http://localhost:11434"

class LlamaCppAdapter(ModelAdapter):
    """Adapter for llama.cpp server."""
    base_url: str = "http://localhost:8080"

class LMStudioAdapter(ModelAdapter):
    """Adapter for LM Studio."""
    base_url: str = "http://localhost:1234"

# Model selection strategy
class ModelSelector:
    """Selects the best model for a given task based on:
    - Task complexity (simple query vs complex reasoning)
    - Available VRAM
    - Latency requirements
    - User preferences
    """
    def select(self, task: Task, budget: Budget) -> ModelInfo: ...
```

## Command Palette / CLI / Tray Integration

### CLI Interface

```bash
# Query context
awareness status                    # Show daemon status
awareness context                   # Show current context summary
awareness context project           # Show project context
awareness context model             # Show available models

# Memory management
awareness remember "decision: use FastAPI for new services"
awareness recall "what decisions about auth?"
awareness forget --before 2025-01-01

# Ego management
awareness prefer language python
awareness goal "ship v1.0 by Friday"
awareness constraint "no network calls"

# Semantic actions (explicit selection)
awareness explain --file src/app.py --lines 10-20
awareness find-related --text "authentication middleware"
awareness summarize --file docs/architecture.md

# Daemon management
awareness start
awareness stop
awareness restart
awareness logs
```

### Claude Code Skill Integration

```markdown
# skill: awareness

## Commands
- /awareness context — inject current context into session
- /awareness remember — store a decision or learning
- /awareness recall — search past decisions
- /awareness status — show daemon status
```

### Tray Integration (Future)

```python
# Using AppIndicator / StatusIcon (GTK) or QSystemTrayIcon (Qt)
# Shows:
#   - Daemon status (running/stopped)
#   - Current project
#   - Quick actions: "Remember this", "Recall context", "Status"
#   - Model availability indicator
```

## Test Strategy

### Unit Tests
- SQLite schema migrations
- Redaction engine
- Provider data collection (mocked)
- Model adapter interfaces (mocked)

### Integration Tests
- Daemon start/stop via systemd
- Unix socket communication
- End-to-end: store and query context
- Provider opt-in/opt-out

### Smoke Tests
```bash
#!/bin/bash
# smoke-test.sh
set -e

# Start daemon
systemctl --user start awareness-agent
sleep 2

# Test socket communication
echo '{"jsonrpc":"2.0","method":"health","id":1}' | \
  socat - UNIX-CONNECT:$XDG_RUNTIME_DIR/awareness-agent.sock

# Test context storage
awareness remember "test: smoke test decision"
awareness recall "smoke test"

# Test provider
awareness context project

# Stop daemon
systemctl --user stop awareness-agent

echo "All smoke tests passed"
```

## Failure Modes

| Failure | Behavior | Recovery |
|---------|----------|----------|
| Daemon crashes | systemd auto-restarts | Automatic (5s backoff) |
| Socket unavailable | CLI reports "daemon not running" | User runs `awareness start` |
| SQLite locked | Retry with backoff, then fail gracefully | Automatic |
| Provider fails | Log error, skip provider, continue | Automatic |
| Model runtime unavailable | Report unavailable, skip inference | Automatic |
| Disk full | Stop writing, alert user | Manual (free space) |
| Corrupted database | Attempt recovery, else reindex | Semi-automatic |
| Config invalid | Log error, use defaults | Manual (fix config) |

## Security Hardening Checklist

- [ ] Unix socket: 0600 permissions (user-only)
- [ ] No network listeners (Unix socket only, no TCP)
- [ ] Input validation on all socket messages
- [ ] Parameterized SQL queries only
- [ ] systemd hardening (NoNewPrivileges, ProtectSystem, PrivateTmp)
- [ ] Redaction of sensitive patterns before storage
- [ ] No shell execution from daemon
- [ ] Config files: 0600 permissions
- [ ] Database file: 0600 permissions
- [ ] No setuid/setgid bits on any files
