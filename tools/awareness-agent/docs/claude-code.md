# Claude Code / FCC Integration — Spike B0

## Overview

Spike B0 adds a Claude Code / FCC integration layer on top of the A0 daemon.
It provides:

- **Slash command template** (`.claude/commands/awareness.md`) for `/awareness`
- **SessionStart hook** (opt-in) that injects compact project context at session start
- **CLI subcommand** (`awareness claude`) for install/uninstall/doctor/session-start

All A0 security/privacy invariants are preserved. No network calls. No telemetry.
No conversation harvesting. Fail-closed design throughout.

## Quick Start

```bash
# From your project root:
awareness start
awareness claude install --session-start
```

Then open Claude Code in that project. The `/awareness` command is available,
and a compact context block is injected at each session start.

## Commands

### `awareness claude install [--project PATH] [--session-start]`

Installs integration files into a project's `.claude/` directory:

| File | Purpose |
|------|---------|
| `.claude/commands/awareness.md` | Slash command template for `/awareness` |
| `.claude/hooks/awareness-session-start.sh` | SessionStart hook (opt-in) |
| `.claude/plugins/acknowledged-risks.json` | Opt-in record |

- Without `--session-start`: hook is installed but **disabled** (silent no-op).
- With `--session-start`: hook is **enabled** and injects context at session start.
- **Idempotent**: safe to run multiple times.

### `awareness claude uninstall [--project PATH]`

Removes all integration files. Cleans empty directories. Idempotent.

### `awareness claude doctor [--project PATH]`

Diagnoses integration state: daemon status, file presence, opt-in state,
and a live SessionStart context preview.

### `awareness claude session-start [--project PATH] [--max-chars N]`

Prints the SessionStart context snippet that would be injected. Useful for
testing and debugging.

## SessionStart Context Injection

When enabled, the hook generates a compact XML-like block at session startup:

```
<awareness-context>
Project: my-project
Root: /home/user/projects/my-project
Branch: main
Language: python
Framework: fastapi

Relevant preferences:
  - prefer functional style

Recent decisions:
  - use pytest for tests

Notes:
  - architecture uses Hexagonal pattern
</awareness-context>
```

### Behavior

- **Off by default** — requires explicit `--session-start` flag.
- **Bounded** — default max 10,000 characters (configurable via `--max-chars`).
- **Redacted** — all output passes through the A0 redaction engine.
- **Timeout** — hard 2-second timeout; hook fails silently if exceeded.
- **Fail-closed** — if daemon is unreachable, no context is injected (no error).
- **Uninstallable** — `awareness claude uninstall` removes all traces.

### Opt-in mechanism

The hook checks `.claude/plugins/acknowledged-risks.json` for:

```json
{
  "plugins": {
    "awareness-agent": {
      "session_start": true
    }
  }
}
```

Without this file or with `session_start: false`, the hook is a silent no-op.

## Privacy / Security

- **No cloud sync** — all data stays in local SQLite.
- **No telemetry** — no network calls from the hook or CLI.
- **No conversation harvesting** — only explicit `awareness remember` stores data.
- **Redaction** — secrets/tokens/passwords are redacted before display.
- **No shell injection** — all subprocess calls use argv-style invocation.
- **File permissions** — config files are 0600; DB/socket/WAL/SHM are 0600.
- **Fail-closed** — missing daemon = silent no-op, not a stack trace.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No context injected | Run `awareness start` first |
| Hook errors | Run `awareness claude doctor` |
| SessionStart slow | Check daemon: `awareness status` |
| Want to disable | `awareness claude uninstall --session-start` |
| Re-enable | `awareness claude install --session-start` |

## Files

```
tools/awareness-agent/
├── awareness_agent/
│   ├── integrations.py       # CLI subcommand: claude install/uninstall/doctor/session-start
│   └── session_start.py      # Context snippet generation (bounded, redacted)
├── tests/
│   ├── smoke-test.sh         # A0 tests (unchanged)
│   └── b0-smoke-test.sh      # B0 tests (install, uninstall, idempotency, etc.)
└── docs/
    └── claude-code.md        # This file
```
