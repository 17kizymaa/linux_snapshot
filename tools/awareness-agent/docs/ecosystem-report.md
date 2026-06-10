# Ecosystem Report: awareness-agent

**Positioning:** A local-first, privacy-preserving, project-aware memory daemon for coding agents.

**Version:** 0.1.0-a0 | **Date:** 2026-06-10 | **Spike:** C3 (consolidated)

---

## 1. Executive Summary

The awareness-agent is a Unix-socketed, SQLite-backed memory daemon that gives AI coding assistants (Claude Code, Codex, etc.) persistent, structured, project-scoped memory. It is not an agent framework - it is the memory layer that agent frameworks lack.

As of mid-2026, the AI agent ecosystem is experiencing a memory reckoning. OpenClaw's dual-memory architecture (QMD + Core) has made "memory plugin" a first-class concept. Hermes Agent ships with built-in persistent memory as a core differentiator. A wave of new projects (Mnemo, Mnemosyne, verifiable-memory-mcp) are attacking the same problem from different angles. Meanwhile, the community sentiment on r/AI_Agents is crystallizing around a key insight: **retrieval architecture matters more than storage format**, and **autonomous agents are hype - semi-autonomous agents with alarms are what people actually use**.

The awareness-agent sits at a unique intersection: more structured than OpenClaw's markdown files, more private than Mem0's cloud extraction, more project-aware than Mnemosyne's global scope, and more principled than Hermes's built-in memory (which lacks provenance, TTL, and scope control). Its combination of 8-kind taxonomy, per-kind TTL, 5-level scope, FTS5+trigram lexical search, dual-backend embeddings with provenance enforcement, and fail-closed SessionStart injection has no direct equivalent in the current ecosystem.

**Key finding:** The stack is architecturally ahead of most alternatives on paper, but the ecosystem is moving fast. The window to establish relevance is the next 2-3 months as the "memory for agents" category crystallizes.

---

## 2. Architecture Breakdown

### 2.1 Core Design Principles

| Principle | Implementation |
|-----------|---------------|
| Local-first | Unix socket IPC, SQLite WAL, no network calls ever |
| Privacy-preserving | Regex redaction pipeline, 0600 file permissions, no telemetry, no cloud |
| Project-aware | Git metadata collection, path-scoped memories, project-matched ranking |
| Fail-closed | SIGALRM timeouts, silent degradation, opt-in everything |
| Explicit invocation | No hidden surveillance, no conversation harvesting |

### 2.2 Storage Layer

- **SQLite with WAL mode** - busy_timeout=5000, foreign_keys=ON, 0600 permissions
- **4 tables:** projects, sessions, memories (with kind/scope/embedding columns), FTS5 virtual table
- **Schema carries:** kind, scope, confidence, tags, expires_at, pinned, embedding BLOB, embedding_provider, embedding_model, embedding_dim, embedding_version

### 2.3 Memory Taxonomy

8 kinds x 5 scopes with per-kind TTL:

| Kind | TTL | Purpose |
|------|-----|---------|
| decision | None | Choices made ("use pytest") |
| preference | None | User preferences ("prefer functional style") |
| fact | None | Stable facts ("project uses FastAPI") |
| procedure | None | Repeatable workflows ("deploy: build then push") |
| error | 90 days | Failure + recovery patterns |
| note | 30 days | General observations |
| task | 30 days | Pending/completed tasks |
| pinned | None | User-pinned, always surface |

### 2.4 Retrieval Pipeline (Hybrid Recall)

1. **FTS5 lexical candidates** - BM25-ranked full-text search with trigram tokenizer for partial matching
2. **Embedding candidate widening** - Cosine similarity over compatible-provenance vectors (brute-force numpy)
3. **UNION** of both candidate sets
4. **Ranking** via weighted scoring: BM25 + recency + project_match + pinned_boost + error_boost + source_boost
5. **Deduplication** via character-bigram Jaccard similarity (threshold 0.75)

### 2.5 Embedding System (Dual-Backend with Provenance)

| Backend | Provider | Model | Dim | Semantic? | Network |
|---------|----------|-------|-----|-----------|---------|
| Hash (default) | hash | char-trigram-sha256-v1 | 384 | No | Never |
| ST (optional) | sentence-transformers | local-only | Model-dependent | Yes | Never |

**Provenance enforcement:** Vectors only compared when provider+model+dim+version match. This prevents the silent-semantic-drift problem that plagues systems mixing embedding sources.

### 2.6 SessionStart Integration

- Opt-in via `acknowledged-risks.json` (explicit consent)
- Bounded to 10K characters (configurable)
- Redacted output (secrets stripped)
- 2-second SIGALRM timeout (no GNU timeout dependency)
- Fail-closed: unreachable daemon = no injection, no error
- XML-like block with `<!-- untrusted -->` comment to mitigate prompt injection

### 2.7 Security & Hardening

- Unix socket with 0600 permissions
- Systemd: ProtectSystem=strict, ProtectHome=read-only, RestrictAddressFamilies=AF_UNIX, PrivateTmp=yes, NoNewPrivileges
- Regex redaction for: URL credentials, Bearer tokens, GitHub PATs, OpenAI/Anthropic-style keys
- XDG directory compliance

---

## 3. Ecosystem Mapping

### 3.1 Direct Competitors (Memory Systems for Agents)

| Project | Language | Storage | Retrieval | Local? | Project-Aware? | Taxonomy | License |
|---------|----------|---------|-----------|--------|----------------|----------|---------|
| **awareness-agent** | Python 3.14 | SQLite WAL + FTS5 | Hybrid (FTS5 + embedding) | Yes | Yes (5 scopes) | 8 kinds + TTL | - |
| OpenClaw QMD | TypeScript | Markdown files | Semantic + keyword | Yes | Partial (workspace) | None (flat files) | OSS |
| OpenClaw Core | TypeScript | Markdown + SQLite | Vector + keyword | Yes | Partial | None | OSS |
| Hermes Agent memory | Python | SQLite | Semantic | Yes | Unknown | Unknown | OSS |
| Mnemo | Rust + Python | SQLite + petgraph | Graph-expanded + scored | Yes | Session-based | Entity graph | OSS |
| Mnemosyne | Python | SQLite + sqlite-vec | Hybrid (50% vector + 30% FTS + 20% importance) | Yes | No (global only) | 3 layers (working/episodic/scratch) | OSS |
| Mem0 | Python | Cloud DB | Semantic | No (cloud) | Yes | Auto-extracted | Commercial |
| LanceDB plugin | Rust | Vector DB | Vector only | Yes | No | None | OSS |
| Graphiti | Python | Graph DB | Graph traversal | Varies | Yes | Temporal graph | OSS |
| verifiable-memory-mCP | Python | SQLite | MCP tool | Yes | Unknown | Content-hash chain | OSS |

### 3.2 Key Differentiators vs. Each Competitor

**vs. OpenClaw QMD/Core:**
- OpenClaw uses flat markdown files with no structured taxonomy. awareness-agent has 8 memory kinds with per-kind TTL.
- OpenClaw's QMD is a search engine over markdown; awareness-agent's FTS5+trigram+hybrid recall is purpose-built for structured memory.
- OpenClaw has no embedding provenance system. awareness-agent enforces provider+model+dim+version matching.
- OpenClaw's scope is workspace-level. awareness-agent has 5 scope levels (global → session).
- Both are local-first and private.

**vs. Hermes Agent:**
- Hermes memory is built-in and not separable. awareness-agent is a standalone daemon any agent can use.
- Hermes lacks documented TTL, scope control, or provenance enforcement.
- Hermes is a full agent framework; awareness-agent is a memory layer that enhances any agent.
- Hermes had 1M+ YouTube views (NetworkChuck) in May 2026 - awareness-agent has no marketing.

**vs. Mnemo:**
- Mnemo uses a knowledge graph (petgraph) for entity relationships. awareness-agent uses scope-based project awareness.
- Mnemo is Rust-based with a Python SDK. awareness-agent is pure Python.
- Mnemo's graph traversal is its key differentiator; awareness-agent's taxonomy+TTL+provenance is its key differentiator.
- Both are fully local, both use SQLite.

**vs. Mnemosyne:**
- Mnemosyne has 3 memory layers (working/episodic/scratch). awareness-agent has 8 kinds x 5 scopes.
- Mnemosyne is global-only. awareness-agent is project-aware.
- Mnemosyne uses sqlite-vec for vector search. awareness-agent uses brute-force numpy (no extra dependency).
- Both are pip-installable, both are sub-millisecond for lexical search.

**vs. Mem0:**
- Mem0 is cloud-based (data leaves the machine). awareness-agent never touches the network.
- Mem0 auto-extracts via LLM. awareness-agent uses explicit user invocation.
- Mem0 costs up to $0.07/message. awareness-agent costs nothing.
- Mem0 has project awareness; awareness-agent has finer-grained scope control.

### 3.3 Ecosystem Trends (Last 30 Days)

Based on last30days research (HN, Reddit, YouTube - 77 items across 3 queries):

1. **"Local-first" is now a baseline expectation**, not a differentiator. Every new memory project in the last 30 days advertises local-first.
2. **The 70+ open-source memory systems landscape** (r/mcp, June 8) shows the category is fragmenting. The comment "storage format matters less than retrieval architecture" validates awareness-agent's hybrid recall design.
3. **Verifiable/cryptographic memory** is emerging (verifiable-memory-mcp on YouTube). awareness-agent doesn't have this yet - it's a gap.
4. **Community fatigue with autonomous agents** is real (r/AI_Agents: "autonomous is absolutely hype, all you want is semi-autonomous with an alarm clock"). awareness-agent's explicit-invocation model aligns perfectly with this sentiment.
5. **Hermes Agent is the fastest-growing GitHub project** (surpassed OpenClaw on GitHub stars in May 2026). Its built-in memory is a key selling point, but it's not separable or auditable.
6. **OpenClaw's QMD is considered the best memory plugin** by independent testing (theclawguy.substack: "S Tier"). But QMD indexes markdown files - it doesn't provide structured memory with taxonomy.

---

## 4. Dogfeeding Paths

Dogfeeding = using awareness-agent to improve the workflow of building awareness-agent itself.

### Path 1: Project Memory for Development Sessions

**What:** Use `awareness remember` to capture decisions, errors, and procedures during development. Use SessionStart injection to restore context at the start of each coding session.

**How:**
```bash
# During development:
awareness remember "decision: use FTS5 trigram tokenizer for partial matching"
awareness remember "error: SQLite WAL mode requires busy_timeout for concurrent access"
awareness remember "procedure: run tests/b0-smoke-test.sh before committing"

# At session start, context is auto-injected into Claude Code
```

**Value:** Eliminates re-explaining architectural decisions across sessions. The 8-kind taxonomy means decisions persist forever while errors auto-expire (90-day TTL).

### Path 2: Cross-Project Pattern Recognition

**What:** Use global scope to capture patterns that apply across all projects. Use project scope for project-specific knowledge.

**How:**
```bash
# Global pattern:
awareness remember "prefer: always use WAL mode for SQLite in long-running processes" --scope global

# Project-specific:
awareness remember "fact: awareness-agent uses Python 3.14" --scope project
```

**Value:** When working on a new project, global patterns surface automatically. Project-specific facts don't leak across contexts.

### Path 3: Error Recovery Compounding

**What:** Every time a bug is fixed, the error+recovery is stored with 90-day TTL. When a similar error occurs, past solutions surface via hybrid recall.

**How:**
```bash
# After fixing a bug:
awareness remember "error: daemon fails to start when socket file exists but process is dead - check PID file staleness"

# Weeks later, when a similar issue occurs:
awareness recall "daemon start failure"
```

**Value:** The error_boost weight (0.2) ensures failure memories surface preferentially. Over time, the agent builds a personal debugging manual.

### Path 4: Spike/Phase Tracking

**What:** Use the task kind (30-day TTL) to track active development tasks. Use pinned kind for long-running goals.

**How:**
```bash
awareness remember "task: implement config file support" --scope project
awareness remember "pinned: C4 goals - config, backfill CLI, embedding cache, vector indexing" --scope project
```

**Value:** Pinned memories always surface. Task memories auto-expire when completed (or after 30 days if forgotten).

### Path 5: Ranking Weight Tuning via Recall Quality

**What:** Use `awareness recall` with different queries to test ranking quality. Tune RankWeights based on what surfaces vs. what should surface.

**How:**
```bash
# Test recall:
awareness recall "embedding provenance"

# If results are wrong, adjust weights:
# Edit ranking.py: RankWeights(fts_bm25=1.0, recency=0.3, ...)
# Re-test until ranking matches intuition
```

**Value:** The ranking system is explicitly designed to be tunable. Dogfeeding the tuning loop with real queries produces a ranking model calibrated to actual usage patterns.

### Path 6: Embedding Backend Evaluation

**What:** Use the dual-backend system to compare hash vs. sentence-transformers recall quality on real queries.

**How:**
```bash
# With hash backend (default):
awareness recall "project scope detection"

# Switch to ST backend:
awareness config embedding-backend sentence-transformers
awareness recall "project scope detection"

# Compare results, decide which backend serves real queries better
```

**Value:** The provenance system means vectors from different backends are never mixed. This enables clean A/B comparison of embedding quality.

---

## 5. Confidence & Gaps

### 5.1 High Confidence

- **Architecture is sound:** The layered design (CLI → protocol → store → ranking → embeddings) is clean and testable.
- **Privacy model is strongest-in-class:** No network calls, no telemetry, explicit invocation only. This is a genuine differentiator vs. Mem0 and any cloud-dependent system.
- **Taxonomy is well-designed:** 8 kinds x 5 scopes with per-kind TTL covers the memory design space better than any competitor.
- **Hybrid recall is the right approach:** FTS5 for exact/partial matching + embeddings for semantic widening is the consensus best practice.
- **Test coverage is strong:** 31 smoke test sections + 18 eval assertions provide confidence in correctness.

### 5.2 Gaps

- **No vector indexing:** Brute-force numpy cosine similarity works for thousands of memories but won't scale to hundreds of thousands. sqlite-vec or hnswlib integration is needed for C4.
- **No config file support:** All configuration is currently in code. A TOML/YAML config file is needed for user customization (C4 goal).
- **No CLI backfill command:** `backfill_embeddings()` exists in Python but has no CLI subcommand (C4 goal).
- **No cryptographic verification:** Emerging projects (verifiable-memory-mcp) offer content-hash chains. awareness-agent has no tamper detection.
- **No MCP server:** The ecosystem is standardizing on MCP. An MCP server interface would make awareness-agent usable by any MCP-compatible agent, not just Claude Code.
- **No memory export/import:** No way to share memories across machines or back them up (C4 goal).
- **No confidence scoring:** Memories are stored with a confidence field but it's not populated or used in ranking.
- **No multi-agent awareness:** The daemon is single-user, single-agent. No concept of multiple agents sharing a memory store with access control.

### 5.3 Ecosystem Risks

- **Hermes Agent's momentum:** With 1M+ YouTube views and fastest-growing GitHub project status, Hermes's built-in memory sets user expectations. awareness-agent needs to be positionable as "the memory layer Hermes should have used."
- **OpenClaw's QMD dominance:** QMD is considered S-tier by independent testing. awareness-agent's FTS5 approach is technically superior for structured memory, but QMD's markdown-file approach is more familiar to users.
- **Category fragmentation:** 70+ open-source memory systems means users are overwhelmed. awareness-agent needs a clear, simple positioning to cut through the noise.

---

## 6. GPT 5.5 Pro Evaluation Prompt

The following prompt is designed to be sent to GPT 5.5 Pro (or any frontier model) to produce an independent, structured evaluation of the awareness-agent stack against the competitive landscape.

---

```
You are an expert systems architect evaluating memory subsystems for AI coding agents. Evaluate the following project:

**Project:** awareness-agent
**Repository:** https://github.com/17kizymaa/linux_snapshot/tree/main/tools/awareness-agent
**Positioning:** A local-first, privacy-preserving, project-aware memory daemon for coding agents.

**Architecture Summary:**
- Python 3.14 daemon with Unix socket JSON-RPC (AF_UNIX, 0600 permissions)
- SQLite WAL mode storage with FTS5 + trigram tokenizer for full-text search
- 8 memory kinds (decision, preference, fact, procedure, error, note, task, pinned) with per-kind TTL
- 5 scope levels (global, project, repo, path, session) for project-aware retrieval
- Hybrid recall: FTS5 lexical candidates UNION embedding candidates → weighted ranking → Jaccard dedup
- Dual-backend embeddings: hash-based (char-trigram-SHA256, 384-dim, always offline) + optional sentence-transformers (local-only)
- Embedding provenance enforcement: vectors only compared when provider+model+dim+version match
- Opt-in SessionStart hook for Claude Code with 10K char bound, redaction, 2s SIGALRM timeout
- Systemd hardening: ProtectSystem=strict, ProtectHome=read-only, RestrictAddressFamilies=AF_UNIX
- No network calls ever. No telemetry. No conversation harvesting. Explicit invocation only.

**Your task:**

1. **Competitive Analysis:** Compare awareness-agent against these alternatives across the dimensions listed:
   - OpenClaw (QMD + Core memory plugins)
   - Hermes Agent (built-in persistent memory)
   - Mnemo (Rust, SQLite, petgraph knowledge graph)
   - Mnemosyne (SQLite + sqlite-vec, BEAM architecture)
   - Mem0 (cloud-based auto-extraction)
   
   Dimensions: privacy model, retrieval quality, project awareness, taxonomy/structure, scalability, agent portability, operational complexity.

2. **Architecture Review:** Identify the 3 strongest architectural decisions and the 3 weakest. For each weakness, propose a specific improvement with tradeoff analysis.

3. **Gap Analysis:** What critical capabilities are missing that would prevent this from being the default memory layer for AI coding agents in 2026? Prioritize by impact.

4. **Positioning Assessment:** The project positions itself as "a local-first, privacy-preserving, project-aware memory daemon for coding agents." Is this the right positioning? What would make it more compelling or differentiated?

5. **Risk Assessment:** What are the top 3 risks (technical, ecosystem, or adoption) that could prevent this project from succeeding?

6. **Recommendation:** Should the maintainer continue investing in this as a standalone project, pivot to a plugin for an existing framework (OpenClaw, Hermes), or merge the best ideas into an existing project? Justify your answer.

Format your response as a structured report with clear section headers. Be specific and technical. Do not hedge - take a position on each question.
```

---

## 7. Recommended Next Steps

1. **Register last30days-skill as a git submodule** in `.gitmodules` (original preflight was interrupted)
2. **Implement C4 goals** in priority order: config file support → CLI backfill command → embedding cache/warmup → vector indexing
3. **Add MCP server interface** to make awareness-agent usable by any MCP-compatible agent
4. **Write a README.md** for the awareness-agent directory (currently undocumented at the repo level)
5. **Publish a comparison post** on HN/Reddit: "I built a local-first memory daemon for coding agents - here's why existing solutions weren't enough"

---

*Report synthesized from: last30days engine (3 queries, 77 evidence items), WebFetch (6 competitor pages), WebSearch (OpenClaw memory docs), and direct codebase analysis (17 source files).*
