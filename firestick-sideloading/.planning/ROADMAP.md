# Roadmap: FireStick Sideloading Toolkit

## Overview

A Go CLI tool (`firetv`) that automates the complete Fire TV Stick + Arch Linux workflow. Built in vertical MVP slices — each phase delivers a shippable, testable increment. Phase 1 gets you connecting and inspecting devices; Phase 2 adds sideloading; Phase 3 adds mirroring and control; Phase 4 adds safety nets and polish.

## Phases

- [ ] **Phase 1: Core Connect + Device Awareness** — Detect Fire TV devices, connect via network ADB, display device info, Arch setup helpers
- [ ] **Phase 2: Sideloading & App Management** — Install/uninstall APKs, split APK support, package listing
- [ ] **Phase 3: Control & Mirroring** — scrcpy integration, UHID/SDK fallback, ADB keyevent control
- [ ] **Phase 4: Safety, Automation & Polish** — Snapshots/rollback, systemd generation, Viper config, rich logging

## Phase Details

### Phase 1: Core Connect + Device Awareness

**Goal:** `firetv detect`, `firetv connect`, `firetv status`, `firetv devices`, `firetv setup` — reliable device discovery, connection, and system bootstrap
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: ADB-01, ADB-02, ADB-03, DEV-01, DEV-02, DEV-03, CON-01, CON-02, CON-03, CON-04, SET-01, SET-02, ERR-01, ERR-02, ERR-03, CFG-01, CFG-02, CFG-03
**Success Criteria** (what must be TRUE):

  1. User can run `firetv setup` and go from fresh Arch install to ADB-ready (packages, udev rules, group membership)
  2. User can run `firetv detect` and see all connected Fire TV devices with model, OS version, connection type
  3. User can run `firetv connect 192.168.1.50` and establish a verified network ADB connection
  4. User can run `firetv status` and see device info: model, Fire OS version, SDK level, serial
  5. CLI enforces single ADB server on 127.0.0.1:5037 and rejects 0.0.0.0 binding
  6. CLI detects "unauthorized" and "offline" states and prompts user to fix them

**Plans:** 3 plans
Plans:
**Wave 1**

- [ ] 01-01-PLAN.md — Project scaffold, ADB runner, config, errors, stub commands (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — DeviceService: detect, connect, info, health check, disconnect (Wave 2)
- [ ] 01-03-PLAN.md — Arch setup automation (OSUtils), error classification hardening (Wave 2)

### Phase 2: Sideloading & App Management

**Goal:** `firetv install`, `firetv uninstall`, `firetv list`, `firetv push` — full APK management
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: INS-01, INS-02, INS-03, INS-04, INS-05, INS-06, RB-01, RB-02
**Success Criteria** (what must be TRUE):

  1. User can run `firetv install app.apk` and see the app appear on the Fire TV
  2. User can run `firetv install base.apk split_config.apks` for split APKs
  3. CLI captures pre/post-install snapshots and identifies newly installed packages
  4. User can run `firetv uninstall com.example.app` and verify the app is removed
  5. User can run `firetv list --sideloaded` to see user-installed packages
  6. Split APK sessions are cleaned up on failure (no stale sessions)

**Plans**: 2 plans

Plans:

- [ ] 02-01: APK install (single + split), hash verification, session management
- [ ] 02-2: Uninstall, package listing, snapshot capture, diff detection

### Phase 3: Control & Mirroring

**Goal:** `firetv mirror`, `firetv keyevent`, `firetv type` — see and control the Fire TV
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: MIR-01, MIR-02, MIR-03, MIR-04, CTL-01, CTL-02
**Success Criteria** (what must be TRUE):

  1. User can run `firetv mirror` and see the Fire TV screen on their desktop
  2. Keyboard and mouse input work in the mirrored session (UHID or SDK fallback)
  3. If UHID is unavailable, CLI warns user and falls back to SDK input automatically
  4. User can run `firetv keyevent HOME` to send remote control commands
  5. User can run `firetv type "hello world"` to input text

**Plans**: 2 plans

Plans:

- [ ] 03-01: scrcpy integration, UHID probe, fallback chain
- [ ] 03-02: ADB keyevent CLI, text input, long-running process management

### Phase 4: Safety, Automation & Polish

**Goal:** `firetv rollback`, `firetv snapshot`, full Viper config, systemd generation, zerolog, JSON output
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: RB-03, RB-04, SET-03, SET-04, SET-05
**Success Criteria** (what must be TRUE):

  1. User can run `firetv snapshot` to manually capture current device state
  2. User can run `firetv rollback` after an install and return device to pre-install state
  3. Rollback diff computation correctly identifies and removes all packages from a session
  4. `firetv setup --systemd` generates and enables a systemd user service for ADB server
  5. `firetv --json status` outputs machine-readable JSON for agent consumption
  6. Verbose logging via zerolog shows structured output; quiet mode suppresses all but errors

**Plans**: 2 plans

Plans:

- [ ] 04-01: Session-scoped rollback, snapshot diff computation, uninstall cascade
- [ ] 04-02: Viper config, systemd service generation, JSON output mode, zerolog wire-up

## Progress

**Execution Order:**
Phases execute in order: 1 -> 2 -> 3 -> 4 (Phase 3 can start after Phase 1, parallel with Phase 2)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Connect + Device Awareness | 0/3 | Not started | - |
| 2. Sideloading & App Management | 0/2 | Not started | - |
| 3. Control & Mirroring | 0/2 | Not started | - |
| 4. Safety, Automation & Polish | 0/2 | Not started | - |
