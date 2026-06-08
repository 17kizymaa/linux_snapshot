# Phase 1: Core Connect + Device Awareness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 01-Core Connect + Device Awareness
**Areas discussed:** CLI Command Structure, ADB Server Lifecycle, Config + Error Strategy, Device Detection + Arch Setup

---

## CLI Command Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat with light nesting | `firetv connect` — direct, ergonomic, matches adb/fastboot conventions | ✓ |
| Nested subcommands | `firetv device connect` — more organized but more typing | |
| Hybrid | Root-level for common, nested for advanced | |

**User's choice:** Flat with light nesting
**Rationale:** Flat is more ergonomic for a focused tool. Users type `firetv connect 192.168.1.50` far more often than `firetv device connect`. Matches adb, fastboot, scrcpy conventions. Best balance between discoverability (`firetv --help`) and speed.

---

## ADB Server Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| CLI-managed (auto) | CLI starts/stops ADB server, singleton enforcement | ✓ |
| User-managed | User must run `adb start-server` themselves | |
| Opt-in auto | CLI manages only when `--manage-adb` flag is set | |

**User's choice:** CLI-managed with singleton guard
**Rationale:** The tool should "just work." Users shouldn't need to manage `adb start-server`. Singleton on 127.0.0.1:5037 with auto-kill + restart on bad state.

---

## Config + Error Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| YAML at ~/.config/firetv/ | Viper + YAML, auto-create on first run, FIRETV_ env overrides | ✓ |
| JSON at ~/.firetvrc | JSON config file, simpler but less standard for Go CLIs | |
| Env vars only | No config file, all via environment variables | |
| TOML | TOML format (common in Rust, less so in Go ecosystem) | |

**User's choice:** YAML + rich recovery messages
**Config details:** Store default Fire TV IP, preferred scrcpy flags, log level, Arch paths, last connection. Auto-create with sensible defaults on first run.

**Error details:** Every error includes short message, suggested recovery command, link to built-in help. Classified errors with specific exit codes (0/1/2/3). Zerolog with ConsoleWriter.

**Example output:**
```
❌ Failed to connect to 192.168.1.42:5555
   → Device not responding or not on same network.
   Try: firetv connect 192.168.1.42 --force
   Or check firewall: sudo firewall-cmd --add-port=5555/tcp
```

---

## Device Detection

| Option | Description | Selected |
|--------|-------------|----------|
| `adb devices -l` only | Detect already-connected devices, no auto-scanning | ✓ |
| Network scanning | Auto-discover Fire TV via mDNS/port scan | |
| Both | `adb devices` + optional `--scan` flag for network discovery | |

**User's choice:** `adb devices -l` only for Phase 1
**Rationale:** Keep Phase 1 focused. Network scanning/mDNS is a v2 feature (V2-05).

**Scope boundary:** Phase 1 detects what ADB can already see. Auto-discovery is a convenience layer, not table-stakes for core workflow.

---

## Arch Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Verify only | Check what's installed, report what's missing | |
| Auto-install (aggressive) | Install packages, udev rules, group membership, firewall | ✓ |
| Interactive | Ask user before each installation step | |

**User's choice:** Aggressive auto-install
**Rationale:** Core value is "single reliable command." Setup should go from fresh Arch to ADB-ready. Run full verification at end.

---

## Claude's Discretion

- Exact Cobra command initialization and internal package structure — follow standard Go CLI conventions
- Zerolog configuration details (log level mapping, output format)
- Exact error type hierarchy — clean Go error types mapping to classification scheme
- Snapshot store internal format — simple JSON on disk, exact path chosen by planner

## Deferred Ideas

- Network scanning/mDNS for auto-discovery → v2 feature (V2-05)
- Audio forwarding (sndcpy) → v2 feature (V2-04)
- USB hotplug detection → v2 feature (V2-06)
- OTA survival/reconnection → v2 feature (V2-07)
- `firetv rollback` → Phase 4
- systemd user service generation → Phase 4
- JSON output mode → Phase 4
- Multi-device management → v2 feature (V2-03)
