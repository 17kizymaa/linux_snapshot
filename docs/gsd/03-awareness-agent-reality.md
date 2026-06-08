# Awareness Agent — Product Reality Check

> Phase 3 — Crisp product definition, feasibility assessment, and risk analysis

## Crisp Product Definition

A **local-first Linux daemon** that provides persistent, user-controlled context awareness for AI coding agents and terminal workflows. It runs as a `systemd --user` service, stores data locally (SQLite + optional vector index), and exposes capabilities via Unix socket / DBus. Users interact through explicit invocations — CLI commands, editor integrations, or agent tool calls — never through hidden surveillance.

**Core value proposition**: Your AI agent remembers your project context, preferences, and history across sessions, without sending data to the cloud.

## What "Awareness" Means Technically

Awareness = the ability to answer questions about the user's current working context:

1. **Project awareness**: What repo am I in? What's the structure? What language/framework?
2. **Session awareness**: What was I working on? What commands did I run? What files did I touch?
3. **Preference awareness**: What style do I prefer? What tools do I use? What conventions do I follow?
4. **History awareness**: What decisions were made? What bugs were fixed? What patterns emerged?
5. **Model/runtime awareness**: What models are available? What's the cost/latency tradeoff?

This is implemented as:
- A **memory store** (SQLite for structured data, optional vector index for semantic search)
- **Context providers** (plugins that gather context from git, filesystem, shell history, editor state)
- **A query interface** (CLI, Unix socket, DBus, or HTTP for local requests)

## What "Ego" Means Technically

Ego = the agent's persistent model of the user and their working context. Not consciousness — a data structure:

```json
{
  "preferences": {
    "language": "python",
    "style": "functional",
    "test_framework": "pytest",
    "commit_convention": "conventional"
  },
  "goals": ["ship v1.0", "reduce tech debt", "improve test coverage"],
  "constraints": ["no network calls", "no package installs", "read-only first"],
  "budget": {
    "max_tokens_per_session": 100000,
    "preferred_model": "local",
    "cost_limit_usd": 5.00
  },
  "history": {
    "recent_projects": ["aetherOS", "odysseus"],
    "common_patterns": ["FastAPI", "SQLite", "systemd"]
  }
}
```

Stored in `~/.config/awareness-agent/ego.json` or similar. User-editable. Transported with the project or kept per-machine.

## What Runtime Awareness Means

Runtime awareness = the daemon's knowledge of the current execution environment:

- **System state**: OS, kernel, available memory, CPU load
- **GPU state**: Available GPU, VRAM, driver version (relevant for local inference)
- **Model runtime state**: Which local runtimes are available (Ollama, llama.cpp, LM Studio), which models are loaded
- **Network state**: Online/offline, proxy configuration
- **Process state**: What agents/IDEs/terminals are running (user-configurable, opt-in)

Implementation: Periodic polling + event-driven updates via inotify/dbus. Stored in memory, not persisted (ephemeral).

## What Explicit-Selection Semantic Actions Mean

When the user explicitly selects text (in terminal, editor, or file manager) and invokes an action:

1. **User selects** a file path, error message, code snippet, or command
2. **User invokes** a semantic action (e.g., "explain this", "find related", "summarize")
3. **System processes** the selection with local context + optional model inference
4. **Result is presented** inline, in a popup, or in a new buffer

This is **NOT**:
- Recording all keystrokes
- Monitoring clipboard continuously
- Logging screen contents
- Building a profile without explicit action

This **IS**:
- User-initiated, on-demand processing of explicitly selected content
- Transparent about what data is used
- Local-first, with clear opt-in for any network use

## Model/Runtime Strategy for Ultra-Low-Bit Local Inference

### The 1.56-bit Claim

1.56-bit quantization (e.g., BitNet b1.58 / BitNet-like approaches) is a real research direction:

- **BitNet b1.58** (Microsoft, 2024): 1.58-bit weights (-1, 0, +1) with learned scaling. Demonstrated reasonable quality at 7B scale.
- **BitNet a4.8**: 4-bit activations + 8-bit weights variant.
- **Current state (2026)**: BitNet-style models are real but:
  - Require custom CUDA kernels for efficient inference
  - Quality gap vs 4-bit still noticeable at smaller scales
  - Limited model selection (mostly Llama-derived architectures)
  - No mainstream runtime support (llama.cpp has experimental BitNet support)

### Nearest Practical Targets

| Target | Quality | Runtime Support | Model Selection | Feasibility |
|--------|---------|----------------|-----------------|-------------|
| **1.58-bit (BitNet)** | Moderate | Experimental (llama.cpp) | Limited | Low — bleeding edge |
| **2-bit (Q2_K)** | Moderate | Good (llama.cpp, Ollama) | Good | Medium — usable but lossy |
| **4-bit (Q4_K_M)** | Good | Excellent | Excellent | **High — recommended default** |
| **6-bit (Q6_K)** | Very Good | Excellent | Excellent | High — quality/size sweet spot |
| **8-bit (Q8_0)** | Near-full | Excellent | Excellent | High — if VRAM allows |

### Recommendation

**Start with 4-bit (Q4_K_M) as the practical default.** The user already runs a 4.6GB Q4_K_M model. This is the sweet spot of quality vs size.

**Support 2-bit as an experimental target** for users with severe memory constraints.

**Document 1.58-bit as a future target** — track BitNet ecosystem maturity, integrate when llama.cpp support stabilizes.

**For the POC**: Use whatever Ollama/llama.cpp already supports. Don't build custom quantization tooling.

## What Is Realistic for a POC

### Realistic (can build in 1-2 days)
1. **SQLite memory store** with project context, preferences, and session history
2. **CLI tool** to query/add context (`awareness remember`, `awareness recall`, `awareness status`)
3. **systemd --user service** that maintains the store and responds to queries
4. **Unix socket IPC** for low-latency queries from scripts/agents
5. **Git context provider** (auto-detect project, branch, recent commits)
6. **Basic Claude Code skill** that queries the daemon for context injection

### Stretch (1 week)
7. **Semantic search** via ChromaDB or sqlite-vec
8. **Shell history integration** (opt-in, parse .bash_history for patterns)
9. **Model telemetry** (track which models are available, latency, cost)
10. **Simple tray icon** (show status, quick actions)

### Not realistic for POC
- Full semantic understanding of arbitrary editor state
- Real-time keystroke analysis
- Automatic preference learning (start with explicit config)
- 1.58-bit model support
- Multi-machine sync

## What Is Hype / Unclear / Needs Measurement

| Claim | Reality | What to Measure |
|-------|---------|-----------------|
| "1.56-bit is production-ready" | Not yet — limited models, experimental runtime | Quality benchmarks vs 4-bit on real tasks |
| "Local models match cloud" | Only at 70B+ scale, not on consumer hardware | Task completion rate, user satisfaction |
| "Awareness improves agent quality" | Plausible but unmeasured | Compare agent output with/without context |
| "Semantic command palette" | Vague — needs concrete UX definition | User task completion time |
| "Self-review / critic loop" | Real technique, but adds latency | Quality improvement vs latency cost |

## Privacy / Security / Legal / Licensing Risks

### Privacy Risks
1. **Memory store contains sensitive context** — project names, file paths, code snippets, commands
   - Mitigation: Local-only storage, user-controlled retention, encryption at rest option
2. **Shell history may contain secrets** — passwords in commands, tokens in env vars
   - Mitigation: Opt-in only, redaction patterns, never send to remote models
3. **Session tracking reveals work patterns** — when you work, what you work on
   - Mitigation: No telemetry, no network calls, user controls retention

### Security Risks
1. **Unix socket is local-only but still an attack surface**
   - Mitigation: Socket permissions (user-only), input validation, no privileged operations
2. **SQLite injection if queries are not parameterized**
   - Mitigation: Use parameterized queries exclusively
3. **Model inference could be poisoned** (if using untrusted local models)
   - Mitigation: Model provenance tracking, user approves models

### Legal Risks
1. **GDPR/privacy law compliance** — even local-only tools may process personal data
   - Mitigation: Data stays on user's machine, no third-party processing, clear privacy policy
2. **License compliance** — if distributing, must comply with dependencies (MIT, Apache, GPL)
   - Mitigation: Prefer MIT/Apache dependencies, audit before distribution

### Licensing Risks
1. **FCC is not open-source** (appears to be proprietary) — cannot fork/redistribute
2. **Claude Code is proprietary** — cannot fork/redistribute
3. **odysseus license** — check before deriving products
4. **aetherOS license** — check before deriving products

## Upstream / Fork Maintenance Risks

1. **FCC updates overwrite customizations** — uv-managed package
2. **Claude Code updates overwrite customizations** — npm-managed package
3. **GSD updates may conflict with custom skills** — managed by GSD system
4. **odysseus upstream moves fast** — aetherOS fork may diverge further

**Mitigation**: Build standalone components that don't modify upstream code. Use extension points (skills, hooks, providers) rather than patches.

## Suggested Product Name Alternatives

| Name | Rationale |
|------|-----------|
| **awareness-agent** | Descriptive, clear |
| **local-ctx** | Short, technical |
| **ego** | Memorable, matches the "persistent self-model" concept |
| **habitat** | Evokes "local environment awareness" |
| **sentinel** | Guardian of local context |
| **grounding** | AI term for connecting to real-world context |
| **proprioception** | Body-awareness metaphor (maybe too long) |

**Recommendation**: `awareness-agent` for the daemon, `awareness` for the CLI command. Clear, searchable, unambiguous.
