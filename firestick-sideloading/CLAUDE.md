<!-- GSD:project-start source:PROJECT.md -->

## Project

**FireStick Sideloading Toolkit**

A Go CLI tool that automates the full Fire TV Stick + Arch Linux workflow: device detection, ADB connection (USB and network), APK sideloading, scrcpy mirroring/control, and rollback. Designed for personal use on Arch Linux with comprehensive documentation for both human operators and Claude Code agent skills.

**Core Value:** A single, reliable CLI command should take you from "Fire TV Stick on my network" to "app installed and screen mirrored" — with full rollback capability and zero ambiguity about device state.

### Constraints

- **Platform**: Arch Linux only (pacman, systemd, udev)
- **Language**: Go (compiled, static binary, easy distribution)
- **Safety**: No rooting, no bootloader unlocks, no irreversible ADB commands
- **Network ADB**: Trusted LAN only — ADB server must bind to 127.0.0.1, not 0.0.0.0
- **Dependencies**: android-tools, android-udev, scrcpy, ffmpeg, vlc, usbutils (all in Arch repos)
- **Device**: All Fire TV models/Fire OS versions via standard ADB protocol

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Go | 1.25.x (stable) | Language / runtime | Static binary, fast compilation, excellent `os/exec` for wrapping system binaries. Target 1.25.x. |
| Cobra (spf13/cobra) | v1.9.1 | CLI framework | De facto standard for Go CLIs. Subcommand-based, POSIX flags, shell completion. Rock-solid API. |
| Viper (spf13/viper) | v1.20.1 | Configuration | Natural companion to Cobra. Reads YAML/JSON config, env vars, pflags. Supports config search paths and defaults. |
| zerolog (rs/zerolog) | latest | Structured logging | Zero-allocation JSON logging with ConsoleWriter for human-readable dev output. Simpler than zap, faster than slog. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| samber/lo | v1.51.0 | Utility functions (generics) | Lodash-style helpers for slices, maps, strings. Reduces boilerplate vs stdlib. |
| go-systemdconf (sergeymakinen) | v3 | systemd unit file generation | Generate systemd service files from Go structs. Clean INI encoder/decoder for systemd syntax. |
| testify (stretchr/testify) | latest | Testing toolkit | Assertions, mocking, test suites. Standard for Go testing beyond stdlib. |

### ADB Interaction Pattern

### Project Layout

## Build and Distribution

| Aspect | Recommendation | Rationale |
|--------|---------------|-----------|
| Static binary | `CGO_ENABLED=0 go build` | All deps are pure Go. Simple distribution. |
| Install (dev) | `go install ./cmd/firestick` | Standard Go install from source. |
| Install (users) | AUR PKGBUILD | Arch Linux standard. Binary package. |
| GoReleaser | Defer to M2 | Overkill for single-platform Arch-only v1. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Native ADB library in Go | No maintained Go library exists. Protocol is complex. | Shell out to `adb` binary. |
| logrus | In maintenance mode. | zerolog or stdlib slog. |
| GUI libraries (Fyne, Wails) | Terminal-first, agent-orchestrated. | CLI only. |
| go-udev for v1 | Requires CGO. USB secondary to network ADB. | `adb devices` polling. |

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| CLI framework | Cobra | urfave/cli v3 | Simpler, less opinionated API. Kong for struct-tag driven. |
| Logger | zerolog | stdlib slog | If minimizing deps is paramount. |
| Systemd units | go-systemdconf | text/template | If only 1-2 static service files. |

## Sources

- Context7 /spf13/cobra v1.9.1 — Subcommand structure, flags, RunE pattern
- Context7 /spf13/viper v1.20.1 — Config file reading, env var binding
- Context7 /rs/zerolog — Structured logging, ConsoleWriter
- Context7 /sergeymakinen/go-systemdconf/v3 — systemd unit generation
- Context7 /stretchr/testify, Context7 /samber/lo v1.51.0
- Project constraints — Arch Linux only, safety-first, 127.0.0.1 ADB binding

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Fire TV + Arch Linux ADB Expertise

This project embodies deep expertise in Fire TV Stick + Arch Linux workflows. When working on this codebase, operate as an expert in:

- **ADB protocol and tooling**: `adb connect`, `adb install`, `adb shell getprop`, keyevent injection, split APK sessions
- **Fire TV device behavior**: Model/OS detection via `getprop`, sleep/wake breaking network ADB, RSA auth flow
- **scrcpy integration**: UHID vs SDK input modes, `--tcpip` auto-configuration, fallback chains
- **Arch Linux system integration**: pacman, udev rules, systemd user services, firewall (ufw)
- **Safety-first design**: Pre-install snapshots, session-scoped rollback, singleton ADB server enforcement
- **Canonical guide reference**: See project operational profile in commit history for the full tested workflow

### Critical Safety Rules

1. ADB server must bind to 127.0.0.1 — NEVER 0.0.0.0
2. No rooting, bootloader unlocks, or irreversible device modifications
3. Always snapshot device state before mutating operations
4. Verify device responsiveness (health check) before every operation
5. Clean up split APK sessions on failure (abort stale sessions)
6. Network ADB only on trusted LAN; disable ADB debugging after work

### Arch Host Detection Commands
```bash
uname -a
cat /etc/os-release
pacman -Q android-tools android-udev scrcpy ffmpeg vlc usbutils 2>/dev/null || true
adb version
scrcpy --version
adb devices -l
```

### Fire TV Device Detection (after ADB connected)
```bash
adb shell getprop ro.product.model
adb shell getprop ro.build.version.sdk
adb shell getprop ro.build.version.fireos
adb shell getprop ro.product.manufacturer
adb shell getprop ro.build.display.id
```
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
