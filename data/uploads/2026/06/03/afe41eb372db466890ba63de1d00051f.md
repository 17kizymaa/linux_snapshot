aetherOS 48-Hour VM Demo Operational Standard
Status: normative for the VM-demo sprint
Primary goal: produce a reproducible Arch/mkarchiso-based VM demo with lightweight UX, stable boot, clear validation, and agent-compatible repo hygiene.

Non-goals for this sprint:

No custom kernel.
No custom package manager.
No installer unless already trivial.
No autonomous self-modification.
No cloud dependency required for boot or core UX.
No speculative architecture beyond preparing clean seams for future agents/RAG.
1. Recommended Repo Structure
CopyaetherOS/
├── README.md
├── AGENTS.md
├── VERSION
├── CHANGELOG.md
├── LICENSE
├── .gitignore
│
├── profiles/
│   └── aetheros/
│       ├── profiledef.sh
│       ├── packages.x86_64
│       ├── pacman.conf
│       ├── airootfs/
│       │   ├── etc/
│       │   ├── usr/
│       │   └── home/
│       └── README.md
│
├── scripts/
│   ├── build-iso.sh
│   ├── validate.sh
│   ├── validate-profile.sh
│   ├── smoke-qemu.sh
│   ├── collect-artifacts.sh
│   └── print-build-env.sh
│
├── docs/
│   ├── SPRINT_OPERATIONS.md
│   ├── BUILD_PIPELINE.md
│   ├── VALIDATION_GATES.md
│   ├── VM_DEMO_ACCEPTANCE.md
│   ├── PACKAGE_POLICY.md
│   ├── LOGGING.md
│   ├── TROUBLESHOOTING.md
│   ├── RELEASES.md
│   └── decisions/
│       ├── ADR-0001-use-archiso.md
│       ├── ADR-0002-no-custom-kernel.md
│       └── ADR-0003-local-first-ai-boundaries.md
│
├── context/
│   ├── README.md
│   ├── PROJECT_BRIEF.md
│   ├── CONSTRAINTS.md
│   ├── CURRENT_STATE.md
│   ├── AGENT_RULES.md
│   ├── TASKS.md
│   ├── KNOWN_ISSUES.md
│   ├── ENVIRONMENT.md
│   ├── prompts/
│   │   ├── sprint-planning.md
│   │   ├── code-review.md
│   │   └── build-debugging.md
│   └── rag/
│       ├── README.md
│       └── sources.md
│
├── tests/
│   ├── qemu/
│   └── fixtures/
│
├── artifacts/
│   └── releases/
│       └── README.md
│
└── .github/
    ├── pull_request_template.md
    └── workflows/
        └── validate.yml
Copy
Recommended .gitignore additions:

Copywork/
out/
logs/
*.iso
*.img
*.qcow2
*.log
.env
.env.*
!.env.example
Rules:

profiles/aetheros/ is the source of truth for the bootable ISO.
out/, work/, ISO files, VM images, and raw logs are generated artifacts and should not be committed.
Release evidence may be committed under artifacts/releases/<version>/ as manifests, checksums, and summarized logs only.
The root README.md should contain only the shortest reliable path: install deps, validate, build, boot in VM.
2. Docs Folder Structure
Copydocs/
├── SPRINT_OPERATIONS.md
├── BUILD_PIPELINE.md
├── VALIDATION_GATES.md
├── VM_DEMO_ACCEPTANCE.md
├── PACKAGE_POLICY.md
├── LOGGING.md
├── TROUBLESHOOTING.md
├── RELEASES.md
└── decisions/
    ├── ADR-0001-use-archiso.md
    ├── ADR-0002-no-custom-kernel.md
    └── ADR-0003-local-first-ai-boundaries.md
Document purposes:

File	Purpose
SPRINT_OPERATIONS.md	Main operational standard for the 48-hour sprint.
BUILD_PIPELINE.md	Exact build stages, inputs, outputs, and artifact naming.
VALIDATION_GATES.md	Required checks before merge or release.
VM_DEMO_ACCEPTANCE.md	What must work in the demo VM.
PACKAGE_POLICY.md	Package inclusion rules and rejection criteria.
LOGGING.md	Build, validation, and demo logging standards.
TROUBLESHOOTING.md	Debug workflow and common failure modes.
RELEASES.md	Versioning, tagging, artifact, and checksum process.
decisions/	Lightweight ADRs for sprint-relevant architecture decisions.
Docs rule:

If behavior changes, update the relevant doc in the same PR or commit.

3. Context Folder Structure
The context/ folder exists for AI-assisted development and future RAG compatibility. It should be short, current, and easy for coding agents to ingest.

Copycontext/
├── README.md
├── PROJECT_BRIEF.md
├── CONSTRAINTS.md
├── CURRENT_STATE.md
├── AGENT_RULES.md
├── TASKS.md
├── KNOWN_ISSUES.md
├── ENVIRONMENT.md
├── prompts/
│   ├── sprint-planning.md
│   ├── code-review.md
│   └── build-debugging.md
└── rag/
    ├── README.md
    └── sources.md
Rules:

docs/ is authoritative.
context/ summarizes current operational state for agents.
context/ must not contradict docs/.
Future RAG indexes are generated locally and must not be committed.
Secrets, API keys, local model paths, and private logs must never be stored in context/.
Recommended context/PROJECT_BRIEF.md:

Copy# aetherOS Project Brief

aetherOS is a lightweight local-first operating environment for reviving constrained hardware for artists, independents, and small businesses.

Sprint goal: produce a stable Arch/mkarchiso VM demo with reproducible build steps, lightweight UX, and clear operational standards.

Hard constraints:
- Arch-based workflow preferred.
- mkarchiso preferred.
- No custom kernel.
- No custom package manager.
- No autonomous self-modification.
- Local-first by default.
- AI/NIM/RAG integrations must be optional and non-blocking.
4. Operational Rules for Coding Agents
Copy this section into root-level AGENTS.md.

Copy# aetherOS Agent Operating Rules

These rules apply to ClaudeCode, local coding agents, assistant-generated patches, and future RAG-assisted workflows.

## Prime Directive

Keep aetherOS simple, bootable, local-first, and reproducible. Do not introduce speculative architecture during the VM-demo sprint.

## Hard Constraints

Agents must not:

1. Add a custom kernel.
2. Add a custom package manager.
3. Add autonomous self-modifying behavior.
4. Add cloud dependencies required for boot or desktop UX.
5. Commit secrets, API keys, model weights, private logs, or `.env` files.
6. Add AUR helpers or source-built packages unless explicitly approved.
7. Replace mkarchiso as the demo ISO build path.
8. Add background services that are not required for the VM demo.
9. Modify generated ISO artifacts directly instead of changing the source profile.
10. Make broad repo rewrites without a task-specific reason.

## Required Agent Workflow

Before editing:

1. Read `README.md`.
2. Read `docs/SPRINT_OPERATIONS.md`.
3. Read `context/PROJECT_BRIEF.md`.
4. Read `context/CONSTRAINTS.md`.
5. Check `context/CURRENT_STATE.md` and `context/KNOWN_ISSUES.md`.

For every change:

1. State the goal.
2. Identify files changed.
3. Keep the diff small.
4. Preserve bootability.
5. Update docs if behavior changes.
6. Run the relevant validation gate.
7. Record unresolved risks in `context/KNOWN_ISSUES.md`.

## AI/NIM/Local Inference Rules

- NVIDIA NIM API access must be optional.
- Use `.env.example` for variable names only.
- Required variable example: `NVIDIA_API_KEY=`.
- Missing API keys must degrade gracefully.
- Local inference support must not require bundled model weights.
- Future RAG support must use local generated indexes ignored by git.

## Done Criteria for Agent Tasks

An agent task is done only when:

- The change is committed or ready as a clean diff.
- Validation steps are documented.
- No new boot blockers are introduced.
- No sprint constraints are violated.
- Any follow-up is recorded in `context/TASKS.md` or `context/KNOWN_ISSUES.md`.
Copy
5. Validation Gates
Validation gates are ordered. Do not skip earlier gates.

Gate	Name	Required For	Pass Criteria
G0	Repo hygiene	Every commit/PR	Clean status, no generated artifacts, no secrets.
G1	Profile integrity	Package/profile changes	mkarchiso profile files exist and are sane.
G2	Package policy	Package changes	Official repos preferred, no duplicates, no unnecessary daemons.
G3	Script validation	Script changes	Shell scripts linted and executable where required.
G4	ISO build	Demo candidate	mkarchiso completes successfully.
G5	Artifact manifest	Demo candidate	ISO checksum, build ID, package manifest captured.
G6	VM boot smoke	Demo candidate	ISO boots in QEMU to login or desktop.
G7	UX smoke	Demo candidate	Terminal, file manager, editor, network status, shutdown tested.
G8	Release readiness	Tagged demo	Docs, known issues, version, and checksum complete.
Minimum command set:

Copy./scripts/validate.sh
./scripts/build-iso.sh
./scripts/smoke-qemu.sh out/*.iso
./scripts/collect-artifacts.sh
Host prep target:

Copysudo pacman -Syu --needed archiso qemu-desktop edk2-ovmf shellcheck git
If qemu-desktop is unavailable on the host, use the appropriate Arch QEMU package available for that system.

6. Build Pipeline Stages
Primary supported build host: Arch Linux x86_64 or a clean Arch VM.

Stage	Input	Action	Output
0. Environment capture	Host system	Record OS, kernel, archiso version, git SHA.	Build environment log.
1. Repo validation	Git checkout	Check required files, ignored artifacts, docs presence.	Validation result.
2. Profile validation	profiles/aetheros/	Check profiledef.sh, packages.x86_64, pacman.conf, permissions.	Profile validation log.
3. Package review	packages.x86_64	Check duplicate/heavy/unapproved packages.	Package review result.
4. ISO build	mkarchiso profile	Run mkarchiso with repo-local work/out dirs.	ISO in out/.
5. Artifact capture	ISO + logs	Generate checksum, manifest, package list, build metadata.	Release artifact folder.
6. VM smoke boot	ISO	Boot with QEMU/KVM or software fallback.	QEMU log and pass/fail note.
7. UX smoke	Running VM	Confirm desktop/session and core apps.	Demo acceptance note.
8. Tag/release	Passing artifact	Create release manifest and git tag.	Demo tag and checksum.
Recommended artifact naming:

Copyaetheros-v0.1.0-demo.1-YYYYMMDDTHHMMSSZ-g<shortsha>.iso
Recommended release manifest:

Copyartifacts/releases/v0.1.0-demo.1/
├── MANIFEST.md
├── SHA256SUMS
├── build-env.txt
├── package-list.txt
├── validation-summary.md
└── known-issues.md
7. VM-Demo Success Criteria
Primary VM target:

CopyPlatform: QEMU/KVM x86_64
CPU: 2 vCPU
RAM: 2 GB
Disk: optional, live ISO boot is sufficient
Firmware: BIOS or UEFI; supporting both is preferred
Network: optional for core UX
GPU: standard virtual display, no passthrough
The demo passes if:

ISO boots from a clean VM.
System reaches graphical session or clearly documented login flow.
UX is lightweight and responsive at 2 GB RAM.
User can open:
terminal,
file manager,
text editor,
system/about/help document.
Shutdown/reboot works from UI or documented command.
No cloud service is required for boot, login, desktop, or core tools.
NVIDIA NIM/API functionality is optional and gracefully disabled when no key is present.
Build provenance and checksum are available.
Known issues are documented.
Stretch goals:

Boot at 1 GB RAM.
Both BIOS and UEFI boot verified.
Local inference launcher stub or documentation present.
Future RAG source manifest present under context/rag/sources.md.
8. Logging Standards
Logs must make failures reproducible without exposing secrets.

Required log metadata:

UTC timestamp.
Git SHA.
Branch name.
Build ID.
Host OS.
Kernel version.
archiso version.
mkarchiso profile path.
ISO output path.
Package count.
Mirror or archive source used.
Validation gate status.
Log level convention:

CopyINFO   normal progress
WARN   non-blocking issue
ERROR  blocking failure
GATE   validation gate result
DEBUG  optional verbose detail
Recommended log paths:

Copylogs/
├── YYYYMMDDTHHMMSSZ-validate.log
├── YYYYMMDDTHHMMSSZ-build.log
├── YYYYMMDDTHHMMSSZ-qemu.log
└── YYYYMMDDTHHMMSSZ-artifacts.log
Commit policy:

Raw logs are not committed by default.
Release summaries may be committed under artifacts/releases/<version>/.
Logs must not contain:
API keys,
tokens,
private paths if avoidable,
local model paths,
user data,
SSH keys.
Secrets rule:

CopyIf a value authenticates access, it never belongs in git, docs, logs, screenshots, or context files.
9. Branching and Versioning Recommendations
Use low-complexity branching.

Recommended branches:

Copymain                  stable, demo-ready or near-demo-ready
demo/v0.1-vm           active sprint integration branch
feature/<short-name>   short-lived task branches
fix/<short-name>       short-lived bugfix branches
If solo or moving fast, use trunk-based development:

Copymain
feature/<short-name>
Rules:

main must always have passing G0-G3.
Demo tags require G0-G8.
Avoid long-lived branches during the 48-hour sprint.
Prefer squash merges for noisy AI-assisted commits.
Do not force-push shared demo branches unless coordinated.
Version format:

CopyvMAJOR.MINOR.PATCH-demo.N
First demo target:

Copyv0.1.0-demo.1
Required files:

CopyVERSION
CHANGELOG.md
docs/RELEASES.md
artifacts/releases/<version>/MANIFEST.md
Recommended commit style:

Copyfeat: add lightweight desktop profile
fix: repair mkarchiso package list
docs: add VM demo acceptance criteria
build: add ISO artifact manifest step
test: add QEMU smoke boot script
chore: update context current state
10. Package Selection Philosophy
Package priority:

Boot reliability.
Low memory usage.
Official Arch repositories.
Simple maintenance.
Clear UX value.
Local-first behavior.
Future extensibility only where it does not add runtime complexity.
Preferred:

Official Arch repo packages.
One lightweight desktop/window manager path.
One terminal.
One file manager.
One text editor.
Minimal fonts/theme packages.
Network tooling only if needed.
Official linux or linux-lts, but not both unless justified.
System services disabled by default unless required.
Avoid:

AUR packages for the first demo.
Electron-heavy apps unless essential.
Duplicate apps in the same category.
Large background services.
Packages requiring account login for core usage.
Bundled model weights.
GPU-specific stacks required for boot.
Custom kernels or patched system packages.
Experimental filesystems, init systems, or package managers.
AI-related package rule:

AI support should be integration-ready, not ISO-bloating. Local inference, NIM API, and future RAG must be optional layers that do not block boot or desktop use.

Recommended package review checklist:

Copy- [ ] Is this package required for boot, UX, build, or demo narrative?
- [ ] Is it available in official Arch repos?
- [ ] Does it add a background service?
- [ ] Does it increase RAM usage significantly?
- [ ] Is there already another package serving the same purpose?
- [ ] Does it require cloud login?
- [ ] Does it violate local-first principles?
- [ ] Is it documented in `docs/PACKAGE_POLICY.md`?
11. Troubleshooting Workflow
Use this order. Do not debug randomly.

Step 1: Identify the failing stage
Classify failure as:

Copyrepo hygiene
profile validation
package resolution
mkarchiso build
ISO artifact generation
VM boot
desktop/session
application UX
AI/NIM optional integration
Step 2: Capture state
Record:

Copygit status --short
git rev-parse --short HEAD
uname -a
pacman -Q archiso
ls -lh out/ || true
Step 3: Reproduce with clean generated dirs
Only remove repo-local generated build dirs after confirming paths.

Copy./scripts/validate.sh
./scripts/build-iso.sh
Step 4: Minimize the change
If a recent package or config change broke the build:

Revert only that change.
Rebuild.
Reintroduce smaller changes.
Record the result in context/KNOWN_ISSUES.md.
Step 5: Check common failures
Symptom	Likely Cause	Action
mkarchiso missing	Host deps missing	Install archiso.
Pacman signature failure	Keyring/mirror issue	Update host keyring, retry with known mirror.
Package not found	Wrong repo, typo, removed package	Check official repo availability.
ISO builds but does not boot	Bootloader/profile issue	Compare against Arch releng profile.
Boots to console only	Display manager/session missing	Check enabled services and installed session packages.
Desktop slow or unusable	Too many services/heavy packages	Remove non-essential packages.
NIM/API feature fails	Missing key/network	Confirm graceful fallback.
QEMU fails with KVM	Host virtualization unavailable	Use software fallback and document slower boot.
Step 6: Never patch the running ISO as the fix
All fixes must go back into:

Copyprofiles/aetheros/
scripts/
docs/
context/
The live VM can be used to inspect problems, but the source profile must contain the actual fix.

12. Definition of Done for First Demo
The first VM demo is done when all required items below are true.

Build
 Clean clone can validate with ./scripts/validate.sh.
 Clean Arch host or Arch VM can build with ./scripts/build-iso.sh.
 Build uses mkarchiso.
 No custom kernel.
 No custom package manager.
 ISO is generated under out/.
 SHA256 checksum is generated.
 Build metadata is captured.
Boot
 ISO boots in QEMU.
 VM reaches desktop or documented login flow.
 Works with 2 vCPU and 2 GB RAM.
 Shutdown or reboot works.
 No cloud dependency is required.
UX
 Terminal opens.
 File manager opens.
 Text editor opens.
 Basic system/about/help document is present.
 Visual identity is minimal and coherent.
 No obvious broken launchers.
Operations
 docs/SPRINT_OPERATIONS.md exists.
 AGENTS.md exists.
 context/PROJECT_BRIEF.md exists.
 context/CONSTRAINTS.md exists.
 context/CURRENT_STATE.md reflects actual status.
 context/KNOWN_ISSUES.md lists remaining issues.
 Package choices follow docs/PACKAGE_POLICY.md.
 Logs and artifacts follow docs/LOGGING.md.
AI/local-first boundaries
 NVIDIA NIM API key is not committed.
 .env.example exists if API variables are referenced.
 Missing NIM/API credentials do not break boot or UX.
 Local inference support does not require bundled model weights.
 Future RAG docs/sources are prepared but no heavy RAG service is required.
Release
 Version is set in VERSION.
 Changelog has demo entry.
 Release manifest exists.
 ISO checksum exists.
 Git tag created, recommended: v0.1.0-demo.1.
 Demo limitations are documented clearly.
Final demo statement:

CopyaetherOS v0.1.0-demo.1 is a reproducible Arch/mkarchiso VM demo that boots successfully, presents a lightweight local-first desktop environment, documents its build provenance, and preserves clear operational boundaries for future AI/RAG integration.
