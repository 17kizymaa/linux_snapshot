# Repo Map — Linux $HOME Snapshot

> Phase 1 Cartography — Read-only inspection of `/home/anphuni`

## Top-Level Structure

| Path | Type | Purpose |
|------|------|---------|
| `aetherOS/` | Git submodule | Local-first OS / AI chat platform (FastAPI, Arch-based) |
| `odysseus/` | Git submodule | Upstream AI chat application (FastAPI, Python) — aetherOS is derived from this |
| `Desktop/` | Git repo | Creative workspace with audio transcripts, handoff docs |
| `archive/` | Git repo | Recovery data, odysseus windows mount |
| `server_ops/` | Directory | Contains `pocket-id` (root-owned, identity service) |
| `antigravity-test/` | Directory | Test artifacts |
| `.claude/` | Directory | Claude Code config, skills, hooks, sessions, history |
| `.fcc/` | Directory | FreeClaudeCode server config and logs |
| `.ollama/` | Directory | Ollama model runtime (custom 4.6GB GGUF model) |
| `.planning/` | Directory | GSD planning state (phases, roadmap) |
| `.local/` | Directory | Standard Linux local data (uv tools, flatpak, etc.) |
| `.config/` | Directory | XDG app configs (GTK, Thunar, etc.) |
| `.cache/` | Directory | Standard cache |
| `.npm/` | Directory | npm cache |
| `.gemini/` | Directory | Gemini CLI config |
| `.chroma_db/` | Directory | Chroma vector DB (single SQLite + UUID dir) |
| `.benchmarks/` | Directory | Benchmark data |
| `.trial_logs/` | Directory | Trial logs (antigravity-cli, config) |
| `.ssh/` | Directory | SSH keys (gitignored) |
| `.gnupg/` | Directory | GPG keys (gitignored) |

## Git Remotes

| Repo | Remote URL |
|------|-----------|
| `$HOME` (snapshot) | `git@github.com:17kizymaa/linux_snapshot.git` |
| `aetherOS/` | `https://github.com/17kizymaa/aetherOS` |
| `odysseus/` | `https://github.com/pewdiepie-archdaemon/odysseus.git` |

## Working Tree State (Dirty)

- `.config/Thunar/accels.scm` — modified (user keybinding changes)
- `.config/gtk-3.0/bookmarks` — modified (bookmark changes)
- `aetherOS/` — submodule commit drift
- `odysseus/` — untracked (not staged)

## Package Managers / Build Systems

| Tool | Usage |
|------|-------|
| `uv` | Python package manager — hosts `free-claude-code` tool |
| `npm` (global) | Node.js — hosts `@anthropic-ai/claude-code@2.1.116` |
| `pip` | Python (not directly used; uv manages Python) |
| `systemd` | User services (gpg-agent, etc.) |
| `mkarchiso` | aetherOS ISO build pipeline |
| `Docker` | aetherOS/odysseus containerization (docker-compose) |

## Key Software Installed

| Software | Version | Install Method | Purpose |
|----------|---------|---------------|---------|
| Claude Code | 2.1.116 | npm global | Official Anthropic CLI coding agent |
| FreeClaudeCode (FCC) | 1.2.39 | uv tool | Multi-provider proxy + Claude Code launcher |
| Ollama | — | Binary | Local model runtime |
| Python | 3.14 | uv | Runtime for FCC |
| Node.js | — | System | Runtime for Claude Code |

## Claude Code Configuration

- **Model**: `opus` (Opus 4.7)
- **OAuth**: Configured (Anthropic account)
- **GSD Profile**: `full` (all GSD features enabled)
- **Skills**: 70+ installed (all GSD skills)
- **Hooks**: 13 hooks (all GSD — session state, context monitor, read injection scanner, phase boundary, workflow guard, statusline, etc.)
- **Agents**: 35+ custom agents (all GSD)
- **Plugins**: marketplace configured
- **Permissions**: `gsd-plan-phase` allowed

## FreeClaudeCode Architecture

FCC is a FastAPI-based multi-provider proxy that:
- Intercepts Claude Code API calls
- Routes to 15+ provider backends (NVIDIA NIM, OpenRouter, Mistral, DeepSeek, Ollama, LM Studio, llama.cpp, Gemini, Groq, Cerebras, Fireworks, Kimi, Wafer, OpenCode, Z-AI)
- Supports Telegram and Discord messaging bridges
- Has admin UI at `/admin`
- Runs as `fcc-server` process (PID 4000-range, on pts/0)
- Launches Claude Code via `fcc-claude`
- Currently running with model `owl-alpha`

## aetherOS Architecture

- **Type**: FastAPI web application (Python)
- **Entry**: `app.py` (1057 lines, slim orchestrator)
- **Core modules**: `core/` (auth, database, session_manager, middleware, models, constants, atomic_io, platform_compat, exceptions)
- **Routes**: 40+ route files (chat, memory, research, documents, tasks, calendar, email, search, shell, TTS, etc.)
- **Services**: `services/` (MCP servers: email, image_gen, memory, rag)
- **LLM**: `llm/` (Modelfile for Ollama, custom model)
- **Build**: `scripts/` (ISO build pipeline for Arch/mkarchiso)
- **Context**: `context/` (agent rules, constraints, mission, project brief)
- **Purpose**: Local-first AI chat platform targeting constrained hardware (VM demo with 2GB RAM)

## odysseus Architecture

- **Type**: FastAPI web application (Python) — upstream of aetherOS
- **Entry**: `app.py` (1057 lines)
- **Core**: Same structure as aetherOS (shared ancestry)
- **Routes**: Similar route set with more features (email, calendar, YouTube, etc.)
- **Tests**: 80+ test files
- **MCP Servers**: `mcp_servers/`
- **Services**: `services/` (cache, docs, faces, hwfit, memory, research, search, shell, stt, tts, youtube)
- **Upstream**: `https://github.com/pewdiepie-archdaemon/odysseus.git`

## Relationship: aetherOS vs odysseus

- odysseus is the **upstream** project (pewdiepie-archdaemon/odysseus)
- aetherOS is a **fork/derivative** (17kizymaa/aetherOS) — stripped down for constrained hardware
- Both share the same `app.py` structure and many source files
- aetherOS has additional Arch/mkarchiso build tooling
- odysseus has more features (email, calendar, YouTube, more tests)
- The `$HOME` repo tracks both as submodules

## Obvious Stale/Broken/Generated Areas

1. `.ollama/id_ed25519` — SSH key inside `.ollama/` (wrong place, gitignored but suspicious)
2. `.ollama/EOF` — empty file (artifact of interrupted download?)
3. `.xsession-errors.old` — 163MB stale error log
4. `.claude/history.jsonl` — 87KB conversation history
5. `.claude/file-history/` — 23 directories of file snapshots
6. `.claude/session-env/` — 40 directories of session environments
7. `.claude/sessions/` — active session data
8. `.fcc/logs/` — ~1.9GB of server logs (hundreds of 50MB log files)
9. `Downloads/` — large audio files (m4a), chat transcripts
10. `Desktop/` — large audio files (37MB m4a), transcripts
11. `archive/recovery/` — gitignored recovery data
12. `.chroma_db/` — Chroma vector DB (gitignored)
13. `.benchmarks/` — benchmark data (gitignored)
14. `server_ops/pocket-id/` — root-owned directory (potential permission issue)

## Files Important for Claude Code / FreeClaudeCode Behavior

| File | Purpose |
|------|---------|
| `.claude.json` | CC global config (model, features, OAuth, tips) |
| `.claude/settings.json` | CC project settings (hooks, statusline, model) |
| `.claude/settings.local.json` | CC local permissions |
| `.claude/.credentials.json` | CC OAuth credentials |
| `.claude/.gsd-profile` | GSD profile (`full`) |
| `.claude/skills/` | 70+ GSD skills |
| `.claude/hooks/` | 13 GSD hooks |
| `.claude/agents/` | 35+ GSD agent definitions |
| `.fcc/.env` | FCC provider keys, model routing, runtime config |
| `aetherOS/context/` | Agent rules, constraints, mission for aetherOS |
| `aetherOS/.env.example` | aetherOS environment template |

## Risks and Unknowns

1. **Secrets in `.fcc/.env`**: 15+ API keys for various providers
2. **SSH keys in `.ollama/`**: Unexpected location, unclear purpose
3. **Root-owned `server_ops/`**: Permission anomaly
4. **1.9GB FCC logs**: Disk space, potential sensitive data in logs
5. **Submodule drift**: aetherOS and odysseus have diverged from their remotes
6. **GSD hooks run on every tool use**: Non-trivial background processing
7. **Custom Ollama model**: `anti_clown.merged.Q4_K_M.gguf` (4.6GB) — origin unclear
8. **Desktop git repo**: Contains voice recordings and transcripts (privacy)
