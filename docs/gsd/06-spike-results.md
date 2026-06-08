# Spike Results

## 2026-06-08 — Spike A0: Stdlib Awareness daemon vertical slice

### Selection

Completed the interrupted A0 implementation instead of advancing to a new spike. A partial local daemon is worse than no daemon: it creates uncertainty in the workflow and blocks clean follow-on Claude Code integration.

### Implemented

- `tools/awareness-agent/bin/awareness`
- `tools/awareness-agent/awareness_agent/__init__.py`
- `tools/awareness-agent/awareness_agent/paths.py`
- `tools/awareness-agent/awareness_agent/redaction.py`
- `tools/awareness-agent/awareness_agent/git_provider.py`
- `tools/awareness-agent/awareness_agent/store.py`
- `tools/awareness-agent/awareness_agent/protocol.py`
- `tools/awareness-agent/awareness_agent/server.py`
- `tools/awareness-agent/awareness_agent/cli.py`
- `tools/awareness-agent/tests/smoke-test.sh`
- `tools/awareness-agent/systemd/awareness-agent.service`
- `tools/awareness-agent/install.sh`
- `tools/awareness-agent/uninstall.sh`

### Behavior

- Local-only daemon.
- Unix socket IPC only: `$XDG_RUNTIME_DIR/awareness-agent.sock`.
- Socket mode `0600`.
- SQLite store under XDG data dir with WAL journal mode.
- SQLite DB/WAL/SHM files hardened to `0600`.
- Config under XDG config dir.
- State/logs under XDG state dir.
- Git context provider stores project metadata only.
- Redaction runs before explicit memory persistence.
- systemd user service with `NoNewPrivileges`, `ProtectSystem=strict`, `RestrictAddressFamilies=AF_UNIX`.

### Smoke result

Passed with `tools/awareness-agent/tests/smoke-test.sh` in isolated temporary XDG dirs.

Validated:

- daemon starts
- status reports daemon online
- explicit memory can be remembered/recalled
- sensitive token-shaped memory is redacted before recall
- git project context is available
- socket exists with mode `0600`
- SQLite DB and live WAL/SHM sidecars are mode `0600`
- daemon stops cleanly

### Privacy/security notes

- No network listener.
- No TCP.
- No reverse shell / command-execution RPC surface.
- No clipboard polling.
- No shell history ingestion.
- No editor surveillance.
- All memory is explicit via `awareness remember`.
- systemd unit is provided but not auto-enabled.

### Known limitations

- Recall is SQLite LIKE, not semantic search.
- No Claude Code skill yet.
- No JSON-RPC shutdown method; stop currently uses PID file + SIGTERM.
- No migrations framework yet.
- No model/runtime telemetry yet.

### Next recommended spike

Spike B0: Claude Code wrapper around the daemon:

- `/awareness context`
- `/awareness remember`
- `/awareness recall`
- optional SessionStart context snippet with hard size cap
