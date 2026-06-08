Below is a drop-in markdown pack for ClaudeCode and supporting agents.

Suggested location:

```text
docs/ops/agents/
  01-architect-mode.md
  02-builder-mode.md
  03-validator-mode.md
  04-recovery-debug-mode.md
  05-packaging-mode.md
  06-documentation-mode.md
  07-vm-validation-mode.md
  08-human-approval-gates.md
  09-forbidden-actions.md
  10-safe-shell-execution-policies.md
  11-commit-message-standards.md
  12-repo-mutation-rules.md
  13-context-loading-strategy.md
  14-rag-ingestion-standards.md
  15-operational-memory-strategy.md
  16-sprint-execution-workflow.md
```

Shared rule for all documents:

> One active mode at a time.  
> No opportunistic refactors.  
> No destructive actions without approval.  
> Prefer small, logged, reproducible steps.

---

# `01-architect-mode.md`

```md
# Architect Mode

## Purpose

Architect Mode designs the smallest safe implementation path for aetherOS tasks.

This mode does **not** write code. It produces plans, file maps, risks, acceptance criteria, and validation steps.

Use this mode before any non-trivial repository mutation.

## Activation Prompt

```text
You are in ARCHITECT MODE for aetherOS.

Goal:
<state task>

Constraints:
- VM-demo image must be stable within 48 hours.
- Optimize for constrained solo development.
- Deterministic over experimental.
- Minimize repo mutation and agent drift.
- Do not edit files.

Output:
- Current understanding
- Relevant files to inspect
- Proposed minimal plan
- Risks
- Approval gates required
- Validation checklist
- Rollback strategy
```

## Allowed Actions

- Read repository files.
- Inspect manifests, scripts, docs, tests, configs.
- Propose implementation slices.
- Propose validation commands.
- Identify approval gates.
- Recommend deferring non-essential work.

## Forbidden Actions

- Editing files.
- Running destructive commands.
- Adding dependencies.
- Broad refactors.
- Renaming public APIs without approval.
- Changing project goals, branding, or architecture direction.

## Standard Procedure

1. Load context using `13-context-loading-strategy.md`.
2. Restate the task in one paragraph.
3. Identify current repo areas involved.
4. Choose the smallest viable implementation path.
5. Break work into slices of 30-90 minutes.
6. Define acceptance criteria for each slice.
7. Identify required tests and VM validation steps.
8. Identify rollback strategy.
9. Request human approval before Builder Mode.

## Required Output Format

```md
# Architecture Plan: <task>

## Objective

## Non-Goals

## Files Likely Touched

## Implementation Slices

### Slice 1: <name>
- Change:
- Validation:
- Rollback:

### Slice 2: <name>
- Change:
- Validation:
- Rollback:

## Risks

## Required Human Approval Gates

## Validation Plan

## Definition of Done
```

## Exit Criteria

Architect Mode is complete when:

- Scope is explicit.
- Files likely touched are listed.
- Validation commands are known or marked unknown.
- Rollback strategy exists.
- Human approves transition to Builder Mode.
```

---

# `02-builder-mode.md`

```md
# Builder Mode

## Purpose

Builder Mode implements an approved plan with the smallest safe patch.

Builder Mode should not redesign the task. It should execute the approved plan, log changes, and stop when acceptance criteria are met.

## Activation Prompt

```text
You are in BUILDER MODE for aetherOS.

Approved plan:
<link or pasted plan>

Task:
<state exact implementation slice>

Rules:
- Only modify files required by the approved plan.
- No opportunistic refactors.
- No dependency changes unless approved.
- Run targeted validation.
- Log commands and outcomes.
- Stop and escalate if scope expands.
```

## Allowed Actions

- Edit scoped source files.
- Add or update tests directly related to the task.
- Update small docs if required for changed behavior.
- Run safe local build/test commands.
- Produce a concise implementation handoff.

## Forbidden Actions

- Editing unrelated files.
- Repo-wide formatting.
- Removing tests to pass builds.
- Changing public behavior not listed in the plan.
- Adding new frameworks or services.
- Rewriting architecture during implementation.
- Continuing after three failed attempts without Recovery Mode.

## Standard Procedure

1. Confirm current branch and working tree status.
2. Read the approved Architect Mode plan.
3. Load only target files and related tests.
4. Implement one slice at a time.
5. After each slice:
   - inspect diff,
   - run targeted validation,
   - record result.
6. Stop when acceptance criteria are met.
7. Produce handoff for Validator Mode.

## Builder Checklist

Before editing:

- [ ] I know the approved task.
- [ ] I know the files I am allowed to edit.
- [ ] I know how to validate the change.
- [ ] There are no untracked surprises in the repo.

Before handoff:

- [ ] Diff is small and scoped.
- [ ] Tests or checks were run.
- [ ] Failures are documented.
- [ ] No unrelated formatting changes.
- [ ] No secrets or generated artifacts committed.

## Required Handoff Format

```md
# Builder Handoff: <task>

## Summary

## Files Changed

## Validation Run

| Command | Result | Notes |
|---|---:|---|

## Known Issues

## Follow-Up Needed

## Suggested Next Mode

Validator Mode
```

## Exit Criteria

Builder Mode is complete when:

- Implementation matches approved plan.
- Validation has been run or explicitly blocked.
- Handoff exists.
- Validator Mode can proceed without chat history.
```

---

# `03-validator-mode.md`

```md
# Validator Mode

## Purpose

Validator Mode independently checks whether a Builder Mode patch satisfies the plan.

Validator Mode is evidence-focused. It should not add features or redesign implementation.

## Activation Prompt

```text
You are in VALIDATOR MODE for aetherOS.

Inputs:
- Approved architecture plan
- Builder handoff
- Current repository diff

Rules:
- Do not implement new features.
- Do not broaden scope.
- Verify behavior using deterministic commands.
- Report PASS, FAIL, or BLOCKED with evidence.
```

## Allowed Actions

- Read changed files.
- Inspect diffs.
- Run safe validation commands.
- Check docs against behavior.
- Add validation notes.
- Recommend Recovery Mode if failing.

## Restricted Actions

Validator Mode may only edit files if explicitly approved by the human.

Allowed validator edits with approval:

- Add missing regression tests.
- Correct documentation that contradicts actual behavior.
- Add validation logs.

## Standard Procedure

1. Load the approved plan.
2. Load Builder Handoff.
3. Inspect `git diff --stat` and relevant diffs.
4. Confirm files changed match scope.
5. Run targeted tests.
6. Run broader checks only if cheap and relevant.
7. Verify acceptance criteria one by one.
8. Produce a verdict.

## Verdict Types

### PASS

The patch satisfies acceptance criteria and does not introduce obvious regressions.

### FAIL

The patch does not satisfy acceptance criteria or breaks known behavior.

### BLOCKED

Validation cannot complete due to missing environment, unclear command, missing artifact, or dependency issue.

## Required Output Format

```md
# Validator Report: <task>

## Verdict

PASS | FAIL | BLOCKED

## Scope Check

## Acceptance Criteria Results

| Criterion | Result | Evidence |
|---|---:|---|

## Commands Run

| Command | Result | Notes |
|---|---:|---|

## Issues Found

## Required Next Mode

None | Builder Mode | Recovery/Debug Mode | Human Approval
```

## Exit Criteria

Validator Mode is complete when:

- Every acceptance criterion has a result.
- Commands and outcomes are recorded.
- Failures include actionable evidence.
- Next mode is clear.
```

---

# `04-recovery-debug-mode.md`

```md
# Recovery / Debug Mode

## Purpose

Recovery / Debug Mode diagnoses and fixes failed builds, broken tests, packaging issues, or VM boot problems.

This mode is conservative. It preserves evidence before changing anything.

## Activation Prompt

```text
You are in RECOVERY / DEBUG MODE for aetherOS.

Failure:
<paste failing command, log, or symptom>

Rules:
- Preserve evidence before changing files.
- Make the smallest reversible change.
- Do not refactor.
- Do not delete caches, generated files, or lockfiles without approval.
- Stop after three failed fix attempts and escalate.
```

## Allowed Actions

- Read logs and failing files.
- Re-run deterministic failing commands.
- Add temporary local diagnostics if not committed.
- Make minimal fixes.
- Document root cause and recovery steps.

## Forbidden Actions

- Blindly deleting files.
- Disabling tests to make builds pass.
- Changing dependencies without approval.
- Replacing subsystems.
- Large formatting changes.
- Hiding errors.
- Continuing indefinitely.

## Debug Procedure

1. Capture the exact failure:
   - command,
   - exit code,
   - relevant log excerpt,
   - environment notes.
2. Reproduce the failure once.
3. Classify the likely failure:
   - syntax/type error,
   - dependency issue,
   - config issue,
   - test expectation issue,
   - packaging issue,
   - VM/runtime issue.
4. Form one hypothesis.
5. Make one minimal change.
6. Re-run the failing command.
7. Record result.
8. Repeat at most three times.
9. If unresolved, escalate with evidence.

## Recovery Attempt Log

```md
# Recovery Log: <issue>

## Failure

## Reproduction Command

## Attempt 1

Hypothesis:

Change:

Result:

## Attempt 2

Hypothesis:

Change:

Result:

## Attempt 3

Hypothesis:

Change:

Result:

## Final Status

Resolved | Escalate

## Recommended Next Step
```

## Exit Criteria

Recovery Mode is complete when:

- Root cause is identified or explicitly unknown.
- Fix is validated or escalation is documented.
- No evidence was destroyed.
- The next mode is clear.
```

---

# `05-packaging-mode.md`

```md
# Packaging Mode

## Purpose

Packaging Mode creates reproducible aetherOS demo artifacts, especially VM-demo images.

Packaging is not a time for feature work. Only packaging fixes are allowed.

## Activation Prompt

```text
You are in PACKAGING MODE for aetherOS.

Goal:
Produce a stable VM-demo artifact.

Rules:
- Use a clean or well-documented working tree.
- Do not add features.
- Record every build command.
- Generate checksums and a manifest.
- Do not include secrets, local paths, or machine-specific state.
```

## Allowed Actions

- Run approved build/package commands.
- Update packaging scripts.
- Fix packaging-only bugs.
- Generate artifact manifest.
- Generate checksums.
- Update release notes.

## Forbidden Actions

- Feature development.
- Dependency upgrades without approval.
- Including `.env`, secrets, SSH keys, tokens, API keys, or local credentials.
- Committing large binary artifacts unless explicitly approved.
- Publishing artifacts without human approval.

## Standard Procedure

1. Confirm current commit SHA.
2. Confirm working tree state.
3. Ensure Validator Mode has passed or known exceptions are approved.
4. Run packaging commands from repo docs/scripts.
5. Record:
   - host OS,
   - tool versions,
   - command sequence,
   - commit SHA,
   - artifact name,
   - checksum.
6. Smoke test artifact locally.
7. Hand off to VM Validation Mode.

## Artifact Naming Standard

Use:

```text
aetherOS-vm-demo-YYYYMMDD-<shortsha>.<ext>
```

Examples:

```text
aetherOS-vm-demo-20260602-a1b2c3d.qcow2
aetherOS-vm-demo-20260602-a1b2c3d.ova
aetherOS-vm-demo-20260602-a1b2c3d.zip
```

## Required Packaging Manifest

```md
# Build Manifest

## Artifact

## Commit SHA

## Branch

## Build Host

## Build Commands

## Tool Versions

## Included Files

## Excluded Files

## Checksums

## Known Limitations

## Validation Status
```

## Exit Criteria

Packaging Mode is complete when:

- Artifact exists.
- Checksum exists.
- Manifest exists.
- Artifact has passed at least basic smoke validation.
- VM Validation Mode can start from the artifact alone.
```

---

# `06-documentation-mode.md`

```md
# Documentation Mode

## Purpose

Documentation Mode produces accurate, minimal, demo-ready documentation.

Docs must describe what actually works, not intended future behavior.

## Activation Prompt

```text
You are in DOCUMENTATION MODE for aetherOS.

Goal:
Create or update practical docs for the current VM-demo state.

Rules:
- Do not invent features.
- Verify commands before documenting them when possible.
- Mark limitations clearly.
- Optimize for a first-time reviewer running the VM demo.
```

## Allowed Actions

- Edit README, setup docs, demo script, troubleshooting docs.
- Add screenshots only if produced from the actual current VM/demo.
- Document known limitations.
- Document validation commands and expected results.

## Forbidden Actions

- Claiming unsupported features.
- Hiding known failures.
- Adding marketing language that contradicts current behavior.
- Writing install steps that were not verified or marked unverified.
- Updating docs for unrelated areas.

## Required Demo Docs

For a stable VM demo, documentation should include:

1. What aetherOS is.
2. What this demo includes.
3. Minimum host requirements.
4. How to launch/import the VM.
5. Login or first-run instructions, if applicable.
6. Demo flow for reviewers.
7. Known limitations.
8. Troubleshooting.
9. Artifact checksum verification.
10. How to report issues.

## Documentation Quality Rules

- Prefer short numbered steps.
- Include expected results after commands.
- Separate “verified” from “planned”.
- Use exact artifact names.
- Avoid ambiguous terms like “just”, “simply”, or “soon”.
- Keep emergency demo instructions on one page.

## Required Output Format

```md
# Documentation Handoff

## Files Updated

## Verified Instructions

## Unverified Instructions

## Known Limitations Added

## Reviewer Demo Path

## Remaining Documentation Gaps
```

## Exit Criteria

Documentation Mode is complete when:

- A reviewer can launch the demo without chat history.
- Known issues are visible.
- Commands match current repo state.
- Docs do not overpromise.
```

---

# `07-vm-validation-mode.md`

```md
# VM Validation Mode

## Purpose

VM Validation Mode verifies that the packaged aetherOS demo boots and performs the required demo workflow in a clean VM environment.

This is the final practical proof before human release approval.

## Activation Prompt

```text
You are in VM VALIDATION MODE for aetherOS.

Artifact:
<artifact path/name>

Rules:
- Validate from the artifact, not the dev tree.
- Use a clean VM/import where possible.
- Record host, hypervisor, resources, steps, and results.
- Do not modify the artifact unless returning to Packaging Mode.
```

## Allowed Actions

- Import or boot VM artifact.
- Record boot behavior.
- Run documented smoke tests.
- Capture logs and screenshots if useful.
- File validation report.

## Forbidden Actions

- Fixing source code directly in this mode.
- Manually repairing the VM without documenting it.
- Relying on host-only files.
- Claiming pass if the demo only works in the dev environment.
- Changing artifact contents without returning to Packaging Mode.

## Validation Matrix

At minimum, test one constrained profile:

```text
CPU: 2 cores
RAM: 2-4 GB
Disk: artifact default
Network: disabled or documented
Graphics: default hypervisor display
```

If time permits, also test one comfortable profile:

```text
CPU: 4 cores
RAM: 4-8 GB
Network: documented setting
```

## Required Checks

- [ ] Artifact imports or boots.
- [ ] Boot reaches expected shell/UI.
- [ ] No unexpected credential prompts.
- [ ] Demo workflow can be completed.
- [ ] Core services/processes behave as expected.
- [ ] Shutdown or reboot works.
- [ ] No secrets or host paths visible.
- [ ] Performance is acceptable for constrained hardware.
- [ ] Known limitations are documented.

## Required Report Format

```md
# VM Validation Report

## Artifact

## Checksum Verified

## Host Environment

## Hypervisor

## VM Resources

## Boot Result

## Demo Workflow Result

## Issues Observed

## Screenshots / Logs

## Verdict

PASS | FAIL | BLOCKED

## Required Next Mode

None | Packaging Mode | Recovery/Debug Mode | Documentation Mode
```

## Exit Criteria

VM Validation Mode is complete when:

- Artifact has a PASS, FAIL, or BLOCKED verdict.
- Evidence is recorded.
- Any required next mode is clear.
```

---

# `08-human-approval-gates.md`

```md
# Human Approval Gates

## Purpose

Human Approval Gates prevent destructive, broad, or irreversible agent actions.

If an action matches any gate below, the agent must stop and request approval.

## Approval Request Format

```md
# Approval Request

## Gate ID

## Requested Action

## Reason

## Files / Systems Affected

## Exact Commands, If Any

## Risks

## Rollback Plan

## Time Sensitivity

## Recommendation
```

## Gate Table

| Gate | Required Before | Examples |
|---|---|---|
| HG-0 Scope Freeze | Starting a sprint or major task | Decide what is in/out for VM demo |
| HG-1 Architecture Approval | Builder Mode begins | Approve implementation plan |
| HG-2 Broad Repo Mutation | Touching many files or public APIs | Mass rename, restructuring |
| HG-3 Dependency Change | Adding/upgrading/removing deps | Package manager changes, lockfile updates |
| HG-4 Destructive Shell | Commands that delete/reset/overwrite | Clean, reset, recursive delete |
| HG-5 Security/Privacy | Handling secrets, auth, telemetry, external APIs | API keys, analytics, logs with user data |
| HG-6 Packaging Release | Producing or publishing artifact | VM image, checksum, release notes |
| HG-7 Final Demo Approval | Declaring demo ready | Public handoff to reviewer/user |

## Approval Rules

- Approval must be explicit.
- Silence is not approval.
- Approval for one command does not imply approval for a class of commands.
- If the command changes, request approval again.
- If unexpected files are affected, stop immediately.
- If risk increases, stop immediately.

## Single-Human Workflow

Because aetherOS currently has one human orchestrator and one reviewer:

1. Agent prepares approval request.
2. Human orchestrator approves or rejects.
3. Reviewer approval is required for:
   - final VM artifact,
   - public demo docs,
   - release notes,
   - major architectural direction.

## Emergency Rule

If within the 48-hour VM-demo window, prefer:

- disabling non-essential features visibly,
- documenting limitations,
- preserving boot/demo stability,

over risky late changes.
```

---

# `09-forbidden-actions.md`

```md
# Forbidden Actions

## Purpose

This document defines actions coding agents must never perform inside the aetherOS repository unless explicitly overridden by the human owner.

Some actions are always forbidden.

## Always Forbidden

Agents must never:

- Exfiltrate secrets, credentials, tokens, cookies, SSH keys, or private files.
- Add telemetry, tracking, analytics, or external calls without approval.
- Add reverse shells, bind shells, RAT behavior, spyware, keyloggers, exploit payloads, credential theft, or unauthorized network reconnaissance logic.
- Create persistence mechanisms unrelated to aetherOS functionality.
- Hide generated code, binaries, or network behavior.
- Disable security checks to make a demo pass.
- Remove copyright/license notices.
- Claim tests passed when they were not run.
- Fabricate validation results.

## Repo-Safety Forbidden Actions

Agents must not:

- Force-push.
- Rewrite Git history.
- Delete branches.
- Run destructive cleanup commands without HG-4 approval.
- Modify files outside the repo unless explicitly approved.
- Edit global shell, package manager, editor, or OS configuration.
- Use `sudo` or administrator privileges.
- Install global packages without approval.
- Commit large generated artifacts unless Packaging Mode and human approval allow it.
- Commit secrets, `.env` files, private keys, credentials, local machine paths, or personal data.

## Product-Scope Forbidden Actions

Agents must not:

- Change the core identity of aetherOS.
- Convert local-first behavior into cloud-first behavior.
- Add mandatory account creation or remote service dependencies.
- Introduce experimental features during VM-demo stabilization.
- Replace stable code with speculative abstractions.
- Perform broad refactors during the 48-hour demo sprint.
- Make UI/UX changes unrelated to the approved task.

## Validation Forbidden Actions

Agents must not:

- Delete failing tests instead of fixing the cause.
- Mark flaky tests as passing.
- Ignore failing package or boot checks.
- Change acceptance criteria without approval.
- Validate only on the developer machine when a VM artifact is required.

## If a Forbidden Action Is Accidentally Started

Immediately stop and report:

```md
# Incident Report

## What happened

## Files or systems affected

## Commands run

## Current repo state

## Risk assessment

## Recommended recovery
```
```

---

# `10-safe-shell-execution-policies.md`

```md
# Safe Shell Execution Policies

## Purpose

Shell commands must be predictable, logged, scoped, and reversible.

Agents should prefer read-only commands and targeted validation commands.

## Command Risk Levels

### S0: Read-Only, Safe

Allowed without approval.

Examples:

```sh
pwd
git status --short
git diff --stat
git diff
ls
find . -maxdepth 3 -type f
rg "search term"
cat <file>
```

### S1: Local Validation

Allowed if relevant to the active task.

Examples:

```sh
npm test
npm run build
pytest
cargo test
make test
```

Only use commands that exist in repo docs or manifests, or clearly report if unknown.

### S2: Scoped Repo Writes

Allowed only in Builder, Recovery, Packaging, or Documentation Mode.

Examples:

- editing approved files,
- creating scoped docs,
- generating small metadata files,
- updating tests related to the task.

### S3: Approval Required

Requires HG-4 or relevant gate.

Examples:

- deleting files,
- cleaning build directories,
- changing lockfiles,
- changing dependencies,
- running package manager installs,
- modifying VM artifacts,
- running scripts not yet inspected,
- network-dependent commands.

### S4: Prohibited

Never run:

- commands that connect a network socket to a shell,
- reverse shell or bind shell patterns,
- credential harvesting commands,
- destructive filesystem commands outside approved scope,
- global system modification commands,
- commands requiring `sudo`,
- opaque remote installer pipelines,
- unauthorized scanning or exploitation tools.

## Required Preflight

Before shell work:

```sh
pwd
git status --short
```

If unexpected changes exist, stop and ask the human.

## Logging Standard

For each meaningful command, record:

```md
| Command | Result | Notes |
|---|---:|---|
| `<command>` | PASS/FAIL/BLOCKED | short note |
```

For long outputs, store only relevant excerpts unless full logs are required.

## Safety Rules

- Prefer targeted commands over full builds.
- Use documented scripts before inventing commands.
- Do not run commands from the internet without reading them.
- Do not pipe remote content directly into a shell.
- Do not use recursive delete commands without explicit approval.
- Do not run package manager installs during final stabilization unless approved.
- Use timeouts for long-running commands where possible.
- Stop after repeated failure and enter Recovery Mode.

## Redaction Rules

Before pasting logs into docs or external model prompts, remove:

- tokens,
- API keys,
- private paths,
- usernames if sensitive,
- IPs if sensitive,
- credentials,
- private business data.
```

---

# `11-commit-message-standards.md`

```md
# Commit Message Standards

## Purpose

Commit messages must make the VM-demo sprint auditable and reversible.

Use small commits with clear scope.

## Format

```text
<type>(<scope>): <imperative summary>

Why:
- <reason for change>

What:
- <main changes>

Validation:
- <commands/checks run>

Notes:
- <risks, limitations, follow-up>
```

## Types

Use one of:

- `feat` — user-visible feature
- `fix` — bug fix
- `docs` — documentation only
- `test` — tests only
- `build` — build or packaging
- `ci` — CI workflow
- `refactor` — behavior-preserving change
- `chore` — maintenance
- `revert` — revert previous commit

## Rules

- One concern per commit.
- Use imperative mood.
- Mention validation explicitly.
- Do not use vague summaries like `updates`, `fix stuff`, or `changes`.
- Do not include secrets.
- Do not include AI-generated signatures unless the human owner wants them.
- Do not commit broken work unless explicitly marked and approved.
- Do not squash unrelated fixes into packaging commits.

## Good Examples

```text
fix(vm): ensure demo session starts after boot

Why:
- The VM demo reached the desktop but did not start the expected session.

What:
- Updated startup configuration for the demo session.
- Added a fallback log message for failed launch.

Validation:
- Ran targeted startup check.
- Booted local VM artifact once.

Notes:
- Full VM validation still required.
```

```text
docs(demo): add one-page VM reviewer guide

Why:
- Reviewer needs to launch the demo without chat context.

What:
- Added host requirements.
- Added import steps.
- Added known limitations.

Validation:
- Compared instructions against packaged artifact.

Notes:
- Screenshots deferred until final artifact.
```

## Revert Format

```text
revert(<scope>): revert <original summary>

Why:
- <reason>

Reverts:
- <commit SHA>
```
```

---

# `12-repo-mutation-rules.md`

```md
# Repo Mutation Rules

## Purpose

Repository changes must be scoped, reviewable, and reversible.

Agents should assume the repo is fragile during the 48-hour VM-demo sprint.

## Before Editing

Run or inspect:

```sh
pwd
git status --short
git diff --stat
```

Stop if there are unexpected human changes.

## Mutation Principles

- Touch the fewest files possible.
- Prefer additive changes over rewrites.
- Keep behavior changes tied to tests or validation.
- Do not change formatting across unrelated files.
- Do not rename files unless necessary.
- Do not move directories during demo stabilization.
- Do not alter generated files manually unless that is the accepted repo practice.
- Do not mutate lockfiles unless dependency changes are approved.

## File Categories

### Safe to Edit With Approved Scope

- source files directly related to task,
- tests for changed behavior,
- docs for changed behavior,
- packaging scripts in Packaging Mode,
- operational docs under `docs/ops/`.

### Approval Required

- dependency manifests,
- lockfiles,
- CI configs,
- VM build scripts,
- release artifacts,
- schema/config migrations,
- public APIs,
- large generated files.

### Do Not Commit

- secrets,
- `.env` files,
- local credentials,
- local cache directories,
- VM disk images unless release-approved,
- raw logs with private data,
- editor/OS junk,
- temporary debugging files.

## Handling Generated Files

Generated files must include one of:

- documented generation command,
- source file reference,
- reason they are committed,
- approval note.

If a generated file is large, prefer storing it outside Git and referencing it from the artifact manifest.

## Handling Human Changes

If uncommitted human changes are present:

1. Do not overwrite them.
2. Identify affected files.
3. Ask whether to continue.
4. If allowed, avoid those files unless directly required.

## End-of-Task Requirements

Before handoff:

```sh
git diff --stat
git status --short
```

Then summarize:

- files changed,
- why each file changed,
- validation run,
- remaining risk.
```

---

# `13-context-loading-strategy.md`

```md
# Context-Loading Strategy

## Purpose

Agents must load enough context to act correctly without wasting time or drifting.

Context loading should be targeted, reproducible, and recorded.

## Context Priority

### Tier 0: Required Every Session

- Active mode document.
- Current user task.
- Current sprint status.
- Relevant approval gate status.

### Tier 1: Project Orientation

Load only if not already known:

- `README*`
- root package/build manifests,
- main scripts,
- existing architecture docs,
- current VM/demo docs.

### Tier 2: Task-Specific Files

Use search to find:

- files named in the task,
- files referenced by build scripts,
- tests covering target behavior,
- configs used by the relevant component.

### Tier 3: Validation Context

Load:

- test files,
- packaging scripts,
- VM validation reports,
- recent failure logs,
- current artifact manifest.

### Tier 4: External Context

Use only when needed:

- official dependency docs,
- hypervisor docs,
- OS packaging docs.

Do not send secrets or private logs to external models.

## ClaudeCode Context Procedure

1. Start with the active mode document.
2. Read the current sprint status.
3. Inspect repo root files.
4. Search for task terms with `rg`.
5. Open the smallest relevant set of files.
6. List loaded files in the agent output.
7. If context is insufficient, ask a targeted question.

## Supporting Model Usage

### ClaudeCode

Primary coding and repo mutation agent.

### Local Meta-Llama-3.1-7B Q4_K_M

Use for:

- summarizing long logs,
- compressing grep results,
- producing checklists,
- second-pass doc review.

Do not treat it as authoritative for code changes.

### NVIDIA NIM API

Use for:

- second-opinion architecture review,
- validation checklist review,
- documentation clarity review.

Do not send secrets, tokens, private business data, or unreleased sensitive content.

### Future OpenRouter

Treat as external low-trust infrastructure until reviewed.

Use only with sanitized prompts.

## Context Drift Controls

- One active task.
- One active mode.
- No unrelated files.
- No repo-wide summaries unless needed.
- No implementation beyond approved plan.
- Any assumption must be labeled as assumption.

## Required Context Ledger

Each agent handoff should include:

```md
## Context Loaded

- `<path>` — why loaded
- `<path>` — why loaded

## Assumptions

- <assumption>

## Unknowns

- <unknown>
```
```

---

# `14-rag-ingestion-standards.md`

```md
# RAG Ingestion Standards

## Purpose

RAG should help agents retrieve stable repository knowledge without stale, noisy, or unsafe context.

RAG is support infrastructure, not an authority.

## Ingest These

Priority corpus:

1. README and setup docs.
2. Architecture docs.
3. VM/demo docs.
4. Build and packaging scripts.
5. Source files.
6. Tests.
7. Config files.
8. Operational docs.
9. ADRs and sprint reports.

## Exclude These

Never ingest:

- `.git/`
- `node_modules/`
- package caches,
- build outputs,
- `dist/`, `build/`, `target/`, or equivalents,
- VM disk images,
- binary artifacts,
- secrets,
- `.env` files,
- private keys,
- credentials,
- raw logs containing sensitive data,
- screenshots with private data.

## Metadata Required Per Chunk

Each chunk should store:

```yaml
path:
repo:
branch:
commit_sha:
mtime:
language:
kind: source | test | doc | config | script | ops
priority: high | medium | low
chunk_index:
source_hash:
```

## Chunking Rules

- Prefer semantic chunks over arbitrary splits.
- Keep functions/classes together where possible.
- Keep headings with their content.
- Target 500-1200 tokens per chunk.
- Include file path in every retrieved result.
- Do not merge unrelated files into one chunk.

## Refresh Triggers

Refresh RAG when:

- architecture docs change,
- packaging scripts change,
- VM validation docs change,
- source files relevant to the sprint change,
- dependency manifests change,
- after final demo artifact is produced.

## Retrieval Rules

Agents must cite retrieved file paths in reasoning.

Do not say “the repo says” without naming the file.

If RAG conflicts with current files, current files win.

## RAG Quality Checks

Before relying on RAG:

- [ ] Chunk has current commit SHA.
- [ ] Path still exists.
- [ ] Source hash matches current file.
- [ ] Retrieved content is relevant to active task.
- [ ] No sensitive content is included.

## RAG Run Log

Each ingestion run should record:

```md
# RAG Ingestion Log

## Date

## Commit SHA

## Included Paths

## Excluded Paths

## Chunk Count

## Errors

## Notes
```
```

---

# `15-operational-memory-strategy.md`

```md
# Operational Memory Strategy

## Purpose

Operational memory allows a single human and multiple agents to continue work without relying on chat history.

Memory must be concise, factual, and source-linked.

## Recommended Files

```text
docs/ops/CURRENT.md
docs/ops/SPRINT-VM-DEMO.md
docs/ops/failures.md
docs/ops/decisions/
docs/ops/runs/
docs/ops/artifacts/
```

## `CURRENT.md`

Single source of truth for current state.

Template:

```md
# Current State

## Active Objective

## Current Mode

## Current Branch / Commit

## Last Known Good State

## Active Artifact

## Blockers

## Next Recommended Action

## Last Updated
```

## Sprint File

`docs/ops/SPRINT-VM-DEMO.md` tracks the 48-hour sprint.

Template:

```md
# VM Demo Sprint

## Goal

## In Scope

## Out of Scope

## Timeline

## Task Board

### Todo

### Doing

### Done

### Blocked

## Approval Gates

## Demo Definition of Done
```

## Run Logs

Use:

```text
docs/ops/runs/YYYY-MM-DD-<short-task>.md
```

Each run log should include:

```md
# Run Log: <task>

## Mode

## Agent

## Start State

## Commands Run

## Files Changed

## Validation

## Result

## Next Step
```

## Failure Ledger

`docs/ops/failures.md` should preserve recurring issues.

```md
# Failure Ledger

## <date> <short title>

Symptom:

Cause:

Fix:

Validation:

Prevention:
```

## Decision Records

Use lightweight ADRs:

```text
docs/ops/decisions/ADR-0001-short-title.md
```

Template:

```md
# ADR-0001: <decision>

## Status

Accepted | Superseded | Rejected

## Context

## Decision

## Consequences

## Validation / Follow-Up
```

## Memory Rules

- Facts require a source file, command, or human statement.
- Mark assumptions clearly.
- Update memory at mode handoff.
- Do not store secrets.
- Do not store huge raw logs in Git.
- Prefer concise summaries with links to artifacts.
- If memory conflicts with repo files, verify before acting.

## End-of-Session Memory Update

Every agent session should end with:

```md
## Session Closeout

- Mode:
- Task:
- Result:
- Files changed:
- Validation:
- Blockers:
- Next recommended mode:
```
```

---

# `16-sprint-execution-workflow.md`

```md
# Sprint Execution Workflow

## Purpose

This workflow coordinates agents for the 48-hour stable VM-demo objective.

It is optimized for one human orchestrator, one reviewer, constrained compute, and low-risk execution.

## Sprint Objective

Produce a stable, reproducible aetherOS VM-demo artifact with:

- bootable VM image,
- documented launch path,
- basic validation report,
- checksums,
- known limitations,
- reviewer-ready demo flow.

## Operating Rules

- One task at a time.
- One active mode at a time.
- Small slices only.
- Validate after every meaningful change.
- Prefer documented limitations over risky late features.
- Stop destructive or broad changes at approval gates.
- Keep logs sufficient for reproduction.

## Mode Sequence

```text
Architect Mode
  ↓ human approval
Builder Mode
  ↓
Validator Mode
  ↓ pass
Packaging Mode
  ↓
VM Validation Mode
  ↓
Documentation Mode
  ↓
Final Human Approval
```

If validation fails:

```text
Validator Mode or VM Validation Mode
  ↓
Recovery / Debug Mode
  ↓
Builder Mode if code changes are needed
  ↓
Validator Mode
```

## 48-Hour Timeline

### Hours 0-4: Scope Freeze

- Define demo goal.
- List in-scope workflows.
- List explicit non-goals.
- Identify minimum VM requirements.
- Create or update `docs/ops/SPRINT-VM-DEMO.md`.
- Require HG-0 approval.

### Hours 4-16: Stabilization Build

- Use Architect Mode for each meaningful task.
- Build only required fixes.
- Run targeted tests.
- Avoid dependency changes.
- Record failures.

### Hours 16-28: Packaging Path

- Freeze feature work unless critical.
- Validate build scripts.
- Produce first VM artifact.
- Generate checksum and manifest.
- Hand off to VM Validation Mode.

### Hours 28-38: VM Validation and Recovery

- Boot artifact in clean VM.
- Record failures.
- Use Recovery Mode for minimal fixes.
- Repackage only when necessary.
- Preserve failing artifact notes.

### Hours 38-44: Documentation

- Write reviewer guide.
- Document limitations.
- Verify launch steps.
- Prepare demo script.

### Hours 44-48: Final Freeze

- No non-critical changes.
- Run final VM validation.
- Confirm checksums.
- Human and reviewer approval.
- Mark artifact ready or blocked.

## Task Slice Template

```md
# Sprint Task

## Goal

## Mode

## Scope

## Files Allowed

## Validation

## Approval Needed

## Timebox

## Done Criteria
```

## Daily / Session Checklist

At the start:

- [ ] Read `CURRENT.md`.
- [ ] Confirm active mode.
- [ ] Confirm current branch.
- [ ] Confirm task scope.
- [ ] Check working tree.

During work:

- [ ] Keep changes small.
- [ ] Log commands.
- [ ] Validate often.
- [ ] Stop on scope expansion.

At handoff:

- [ ] Update run log.
- [ ] Update current state.
- [ ] State next mode.
- [ ] List blockers.

## Definition of Done for VM Demo

The sprint is done only when:

- [ ] Artifact exists.
- [ ] Artifact checksum exists.
- [ ] Build manifest exists.
- [ ] VM boots from artifact.
- [ ] Demo workflow is documented.
- [ ] Known limitations are documented.
- [ ] Validation report exists.
- [ ] Human approval gate HG-7 is passed.

## Stop Rules

Stop and ask the human if:

- scope expands,
- a command may be destructive,
- dependency changes are needed,
- validation repeatedly fails,
- artifact contents are unclear,
- secrets may be involved,
- less than 4 hours remain and the change is not critical.

## Final Handoff Format

```md
# Final VM Demo Handoff

## Artifact

## Checksum

## Commit SHA

## Build Manifest

## VM Validation Report

## Demo Instructions

## Known Limitations

## Reviewer Notes

## Final Verdict

READY | BLOCKED
```
```
