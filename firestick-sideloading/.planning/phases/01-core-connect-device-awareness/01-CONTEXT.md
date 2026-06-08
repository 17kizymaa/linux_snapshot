# Phase 1: Core Connect + Device Awareness - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

## Phase Boundary

Phase 1 delivers the foundation: ADB server lifecycle management, Fire TV device detection (USB + network), network ADB connection with auth handling, Arch Linux system setup helpers, structured error handling with recovery suggestions, and CLI configuration via YAML + env vars. Everything else in the project builds on this layer.

## Requirements (from roadmap + REQUIREMENTS.md)

**18 requirements mapped to this phase:**
- ADB-01: CLI starts and verifies single ADB server bound to 127.0.0.1:5037
- ADB-02: CLI detects and rejects conflicting ADB servers (wrong ports, 0.0.0.0)
- ADB-03: CLI verifies ADB server responsiveness before device operations
- DEV-01: CLI detects Fire TV devices via `adb devices -l` (USB + network)
- DEV-02: CLI displays device info: model, Fire OS version, SDK level, serial, connection type
- DEV-03: CLI performs health check (echo ping) before every operation
- CON-01: CLI connects to Fire TV Stick at given IP:port via `adb connect`
- CON-02: CLI handles first-time RSA auth with configurable timeout (default 30s) + user prompt
- CON-03: CLI detects and recovers from "unauthorized" and "offline" device states
- CON-04: CLI disconnects cleanly and verifies disconnection
- SET-01: CLI detects and installs required Arch packages (android-tools, android-udev, scrcpy, ffmpeg, vlc, usbutils)
- SET-02: CLI installs Amazon/Android udev rules for USB ADB
- ERR-01: CLI classifies errors (connection, auth, install, device offline, not found, permission)
- ERR-02: CLI suggests specific recovery actions for each error type
- ERR-03: CLI returns appropriate exit codes (0 success, 1 user error, 2 device error, 3 system error)
- CFG-01: CLI reads config from YAML file (default path, device aliases, timeouts)
- CFG-02: CLI reads config from env vars (FIRESTICK_DEVICE, FIRESTICK_ADB_TIMEOUT)
- CFG-03: CLI accepts global flags: --device, --verbose, --json

## Implementation Decisions

### CLI Command Structure
- **D-01:** Flat command structure with light nesting where it adds clarity. Root-level commands for the common operations, no heavy subcommand grouping.
- **D-02:** Final command layout:
  ```
  firetv devices                  # list all detected/connected
  firetv detect                   # quick scan + info
  firetv connect [IP|serial]      # connect (network or USB)
  firetv status                   # current connection health
  firetv setup                    # Arch Linux one-time setup helper
  firetv install <apk>...         # sideload (single or split)  [Phase 2]
  firetv uninstall <package>      # [Phase 2]
  firetv list-apps                # installed packages [Phase 2]
  firetv scrcpy                   # launch scrcpy with best settings [Phase 3]
  firetv keyevent <key>           # send input [Phase 3]
  firetv push <local> <remote>    # [Phase 3]
  firetv info                     # detailed device properties
  firetv snapshot                 # manual state capture [Phase 4]
  ```
- **Rationale:** Flat is more ergonomic for a focused tool. Users type `firetv connect 192.168.1.50` far more often than `firetv device connect`. Matches conventions of similar tools (adb, fastboot, scrcpy).

### ADB Server Lifecycle
- **D-03:** CLI manages the ADB server automatically — starts, stops, singleton enforcement.
- **D-04:** Singleton guard on 127.0.0.1:5037. Kill + restart on bad state, with user confirmation for destructive actions.
- **Rationale:** Users shouldn't need to manually manage `adb start-server`. The tool should "just work" while enforcing safety constraints.

### Config + Error Strategy
- **D-05:** Viper + YAML at `~/.config/firetv/config.yaml`. Auto-create on first run with sensible defaults.
- **D-06:** Config stores: default Fire TV IP, preferred scrcpy flags, log level, Arch-specific paths, last successful connection.
- **D-07:** `FIRETV_` environment variable overrides for all config values.
- **D-08:** Error output style:
  ```
  ❌ Failed to connect to 192.168.1.42:5555
     → Device not responding or not on same network.
     Try: firetv connect 192.168.1.42 --force
     Or check firewall: sudo firewall-cmd --add-port=5555/tcp
  ```
- **D-09:** Classified errors (connection, adb-server, permission, apk, device-offline, not-found) with specific exit codes (0/1/2/3) and recovery suggestions.
- **D-10:** Zerolog with ConsoleWriter for human-readable dev output; structured JSON for `--json` mode (Phase 4).

### Device Detection
- **D-11:** Phase 1 uses `adb devices -l` for device detection (USB + already-connected network). No network scanning/mDNS yet — that's a v2 feature (V2-05).
- **Rationale:** Keep Phase 1 focused. Network scanning adds complexity without being table-stakes for the core workflow.

### Arch Setup
- **D-12:** `firetv setup` is aggressive — auto-detects and installs missing Arch packages, configures udev rules, adds user to `adbusers` group, verifies firewall.
- **D-13:** Full setup runs verification at end and reports status (what was installed, what needs reboot, etc.).
- **Rationale:** The project's core value is "single reliable command." Setup should go from fresh Arch to ADB-ready, not just verify.

### Claude's Discretion
- Exact Cobra command initialization pattern and internal package structure — follow standard Go CLI conventions (cmd/, internal/, pkg/).
- Zerolog configuration details (log level mapping, output format selection).
- Exact error type hierarchy — use clean Go error types that map to the classification scheme.
- Snapshot store internal format — use simple JSON on disk, path TBD by planner.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Docs
- `CLAUDE.md` — Project constraints, safety rules, technology stack, architecture guidance
- `.planning/PROJECT.md` — Core value, requirements, key decisions, constraints
- `.planning/REQUIREMENTS.md` — All v1/v2 requirements with phase mapping
- `.planning/ROADMAP.md` — Phase details, success criteria, execution order

### Research
- `.planning/research/ARCHITECTURE.md` — Four-layer architecture (CLI → Services → Runtime → External binaries)
- `.planning/research/STACK.md` — Recommended library versions and rationale
- `.planning/research/PITFALLS.md` — Critical pitfalls (server race conditions, auth timeout, sleep/wake, split APK sessions)
- `.planning/research/SUMMARY.md` — Executive summary with phase ordering rationale

### Technology References (from CLAUDE.md)
- Cobra v1.9.1 — CLI framework
- Viper v1.20.1 — Configuration management
- zerolog — Structured logging
- go-systemdconf v3 — systemd unit generation (Phase 4)

## Existing Code Insights

### Reusable Assets
- None — this is a greenfield project. Phase 1 establishes the foundation.

### Established Patterns
- None yet — patterns will emerge from Phase 1 implementation.

### Integration Points
- Phase 1 sets up the Cobra root command, Viper config bootstrapping, and ADB runtime runner that all subsequent phases depend on.
- ADB runner (`internal/runtime/adb.go` or similar) will be the single point of ADB interaction for all phases.

## Specific Ideas

- ADB server must bind to 127.0.0.1 — NEVER 0.0.0.0 (safety constraint)
- No rooting, bootloader unlocks, or irreversible ADB commands (safety constraint)
- All mutating operations should eventually snapshot device state (Phase 4 rollback depends on this)
- Network ADB is primary path; USB is secondary (convenience for headless Fire TV Sticks)
- RSA auth first-time flow needs 30s timeout and clear user prompt
- Fire TV sleep/wake breaks network ADB — every operation starts with health check

## Deferred Ideas

- Network scanning/mDNS for auto-discovery (V2-05, v2 feature)
- Audio forwarding via sndcpy (V2-04, v2 feature)
- USB hotplug detection (V2-06, v2 feature)
- OTA survival / reconnection after Fire TV updates (V2-07, v2 feature)
- `firetv rollback` command (Phase 4)
- systemd user service generation (Phase 4)
- JSON output mode for all commands (Phase 4, V2-01)
- Multi-device management (V2-03, v2 feature)

---

*Phase: 01-Core Connect + Device Awareness*
*Context gathered: 2026-06-08*
