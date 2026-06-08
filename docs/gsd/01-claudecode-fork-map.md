# ClaudeCode / FreeClaudeCode Fork Map

> Phase 1 Cartography — How CC/FCC are installed, what's forked, and where to integrate

## Installation Topology

```
/usr/bin/claude → /usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe
  ├── Package: @anthropic-ai/claude-code@2.1.116 (npm global)
  ├── License: LICENSE.md (proprietary)
  └── NOT a fork — official Anthropic binary

/home/anphuni/.local/bin/fcc-server → uv tool (free-claude-code)
  ├── Package: free_claude_code-1.2.39 (uv tool install)
  ├── Source: /home/anphuni/.local/share/uv/tools/free-claude-code/lib/python3.14/site-packages/
  ├── License: Unknown (check package metadata)
  └── NOT a local fork — installed via uv from PyPI or similar

/home/anphuni/.local/bin/fcc-claude → launches Claude Code through FCC proxy
```

## Two-Layer Architecture

### Layer 1: FreeClaudeCode (Proxy)
- **Role**: Multi-provider API proxy + Claude Code launcher
- **Tech**: FastAPI (Python 3.14), uvicorn, httpx, pydantic
- **Source modules**:
  - `api/` — FastAPI app, routes, admin, model router, web tools
  - `cli/` — Entry points (serve, launch_claude), session manager, process registry
  - `config/` — Settings, provider catalog, paths, constants
  - `core/` — Anthropic SSE handling, rate limiting, trace, tool streaming
  - `providers/` — 15+ provider backends (NVIDIA NIM, OpenRouter, Mistral, DeepSeek, Ollama, LM Studio, llama.cpp, Gemini, Groq, Cerebras, Fireworks, Kimi, Wafer, OpenCode, Z-AI)
  - `messaging/` — Telegram/Discord bridge
- **Config**: `.fcc/.env` (API keys, model routing, runtime settings)
- **Logs**: `.fcc/logs/` (~1.9GB, rotating ~50MB files)
- **Admin UI**: Available at local `/admin` endpoint

### Layer 2: Claude Code (Agent)
- **Role**: Official Anthropic coding agent CLI
- **Tech**: Node.js binary (compiled/bundled)
- **Config**: `.claude.json` (global), `.claude/` (project)
- **Launched by**: `fcc-claude` (which sets up proxy routing)

## Extension Points

### Claude Code Extension Points

| Extension Point | Location | Current State |
|----------------|----------|---------------|
| **Skills** | `.claude/skills/` | 70+ GSD skills installed |
| **Hooks** | `.claude/hooks/` | 13 GSD hooks (SessionStart, PostToolUse, PreToolUse) |
| **Agents** | `.claude/agents/` | 35+ GSD agent definitions |
| **Settings** | `.claude/settings.json` | Hooks, statusline, model |
| **Local Settings** | `.claude/settings.local.json` | Permission allowlist |
| **Plugins** | `.claude/plugins/` | Marketplace configured |
| **Credentials** | `.claude/.credentials.json` | OAuth token |

### FreeClaudeCode Extension Points

| Extension Point | Location | Description |
|----------------|----------|-------------|
| **Provider Backends** | `providers/*/client.py` | Add new LLM provider |
| **Provider Config** | `config/provider_catalog.py` | Register provider in catalog |
| **Model Routing** | `api/model_router.py` | Route models to providers |
| **Messaging Bridges** | `messaging/` | Telegram/Discord integrations |
| **Web Tools** | `api/web_tools/` | Web fetch, parse, stream |
| **Admin Routes** | `api/admin_routes.py` | Admin UI API |
| **Env Config** | `.fcc/.env` | Runtime configuration |

### GSD (Get Shit Done) Extension Points

| Extension Point | Location | Description |
|----------------|----------|-------------|
| **Skills** | `.claude/skills/gsd-*` | 70+ workflow skills |
| **Hooks** | `.claude/hooks/gsd-*` | Session monitoring, context tracking, phase boundaries |
| **Agents** | `.claude/agents/gsd-*` | Specialized sub-agents |
| **Workflows** | `.claude/get-shit-done/workflows/` | Workflow definitions |
| **Profile** | `.claude/.gsd-profile` | Feature toggle (`full`) |

## Where a Local Agent System Could Integrate Cleanly

### Option A: FCC Provider Backend (Recommended)
- Add a new provider in `providers/` that routes to local inference
- FCC already supports Ollama and llama.cpp — a local-awareness provider is natural
- No changes to Claude Code needed
- **Risk**: FCC is a uv-installed package, not a local fork — would need to fork FCC or use its plugin mechanism

### Option B: Claude Code Skill + Hook
- Create a new GSD-style skill that invokes local agent logic
- Use hooks to inject context awareness into sessions
- No changes to FCC or CC binary
- **Risk**: Skills are limited to prompt-level interaction; can't run persistent daemons

### Option C: Standalone Daemon + FCC Integration
- Build a separate daemon (systemd --user service)
- Expose via Unix socket or local HTTP
- FCC routes certain requests to it via new provider backend
- **Risk**: Requires modifying FCC or running a separate proxy

### Option D: Claude Code Plugin
- CC has a plugin/marketplace system
- Could package awareness features as a plugin
- **Risk**: Plugin API may be limited; marketplace may not support private plugins

## What Should NOT Be Patched Directly

1. **Claude Code binary** (`/usr/lib/node_modules/@anthropic-ai/claude-code/`) — proprietary, will be overwritten on update
2. **FCC package** (`site-packages/free_claude_code/`) — uv-managed, will be overwritten on update
3. **GSD hooks/skills** — managed by GSD update system; edit only via GSD config
4. **`.claude.json`** — managed by CC; use settings.json for overrides

## Recommended Integration Strategy

1. **Do not fork FCC or CC** — both update automatically and patches would be lost
2. **Build a standalone daemon** that runs independently
3. **Integrate via**:
   - Claude Code skills (for explicit user-invoked actions)
   - FCC `.env` config (if local provider support is added to FCC)
   - Unix socket / DBus (for inter-process communication)
4. **Use GSD hooks** for session-aware context injection (already running)
5. **Store all state in `~/.local/share/awareness-agent/`** (XDG compliant)

## FCC Provider Architecture (Key for Local Inference)

FCC's provider system is the cleanest integration point for local models:

```
providers/
  ollama/client.py      → Ollama API (already local)
  llamacpp/client.py    → llama.cpp server (already local)
  lmstudio/client.py    → LM Studio (local)
  open_router/client.py → OpenRouter (remote)
  ...12 more remote providers
```

The Ollama and llama.cpp providers already support local inference. A new "awareness" provider could:
- Wrap a local model runtime
- Add context-awareness preprocessing
- Return enhanced responses with local context metadata
