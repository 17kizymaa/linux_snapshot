# Repo Hygiene Triage

> Phase 2 — Cleanup opportunities, risks, and remediation plan

## Top 10 Cleanup Opportunities

| # | Issue | Location | Effort | Impact |
|---|-------|----------|--------|--------|
| 1 | **Massive FCC log accumulation** | `.fcc/logs/` (~1.9GB, 80+ files) | Low | High — disk space, potential sensitive data |
| 2 | **Oversized xsession-errors** | `.xsession-errors.old` (163MB) | Low | Medium — pure waste |
| 3 | **SSH keys in wrong directory** | `.ollama/id_ed25519` | Low | High — security risk |
| 4 | **Empty EOF file** | `.ollama/EOF` | Low | Low — artifact cleanup |
| 5 | **Large audio files in repo** | `Desktop/*.m4a` (37MB), `Downloads/*.m4a` (6MB) | Low | Medium — already gitignored butDesktop repo tracks them |
| 6 | **Stale file history** | `.claude/file-history/` (23 dirs) | Low | Medium — grows unbounded |
| 7 | **Session env accumulation** | `.claude/session-env/` (40 dirs) | Low | Medium — grows unbounded |
| 8 | **GSD manifest bloat** | `.claude/gsd-file-manifest.json` (49KB) | Low | Low — regeneratable |
| 9 | **Chromadb should stay gitignored** | `.chroma_db/` | None | OK — already gitignored |
| 10 | **`server_ops/` root-owned** | `server_ops/pocket-id/` | Medium | Medium — permission anomaly |

## Top 10 Risk Areas

| # | Risk | Severity | Details |
|---|------|----------|---------|
| 1 | **API keys in `.fcc/.env`** | Critical | 15+ provider API keys. Not currently tracked by git (good) but stored in plaintext |
| 2 | **SSH keys in `.ollama/`** | High | Private key material outside `.ssh/`. Not gitignored by the main `.gitignore` — only `.ssh/` is gitignored |
| 3 | **Claude Code credentials** | High | `.claude/.credentials.json` contains OAuth token. Listed in gitignore as `.claude.json` but NOT `.credentials.json` |
| 4 | **FCC logs may contain sensitive data** | Medium | 1.9GB of server logs — may contain API keys in headers, conversation content, tokens |
| 5 | **Desktop repo contains voice recordings** | Medium | `.m4a` audio files and transcripts of conversations  |
| 6 | **Custom Ollama model origin unclear** | Medium | `anti_clown.merged.Q4_K_M.gguf` (4.6GB) — unknown provenance, could contain anything |
| 7 | **GSD hooks run on every tool use** | Low | 13 hooks executing on every Bash/Edit/Write/Read — attack surface if hooks are compromised |
| 8 | **Root-owned directory in user home** | Medium | `server_ops/` is root-owned — potential privilege escalation vector |
| 9 | **Submodule version tracking** | Low | aetherOS and odysseus pinned to specific commits — may drift from security updates |
| 10 | **`.claude.json` gitignore pattern mismatch** | Low | Gitignore says `.claude.json` but the file IS tracked in git — dirty working tree shows it as modified |

## Files/Directories That Should Probably Be Gitignored

Currently already gitignored (correctly):
- `.ssh/`, `.gnupg/`, `.claude.json`, `.claude/` (mostly), `.fcc/` (not listed but should be), `.ollama/`

Should be added to `.gitignore`:
```
# FCC config (contains API keys)
.fcc/.env

# Claude Code credentials
.claude/.credentials.json

# Ollama data (keys + models)
.ollama/

# Server ops (root-owned, not user data)
server_ops/

# Desktop is its own repo (already tracked separately)
# But large audio files inside should be in Desktop/.gitignore
```

**Note**: `.fcc/` is NOT in the main `.gitignore` — only `.fcc/logs/` would be naturally excluded since `.fcc/.env` contains secrets.

## Likely Secrets/Private-Data Exposure Patterns

| Pattern | Location | Type | Remediation |
|---------|----------|------|-------------|
| API keys in env file | `.fcc/.env` | 15+ provider keys | Ensure gitignored; rotate if ever committed |
| OAuth token | `.claude/.credentials.json` | Anthropic OAuth | Add to gitignore; rotate if ever committed |
| SSH private key | `.ollama/id_ed25519` | Ed25519 key | Move to `.ssh/` or delete; add `.ollama/` to gitignore |
| GPG keys | `.gnupg/` | Keyring | Already gitignored — OK |
| Conversation history | `.claude/history.jsonl` | Chat logs | Already in `.claude/` — OK |
| FCC server logs | `.fcc/logs/` | API traffic, tokens | Add to gitignore; implement log rotation |
| Voice recordings | `Desktop/*.m4a` | Personal audio | Add to `Desktop/.gitignore` |

## Suggested Minimal Cleanup PR/Commit Plan

### Commit 1: `.gitignore` hardening
```
Add to .gitignore:
  .fcc/
  .ollama/
  .claude/.credentials.json
  server_ops/
  Desktop/*.m4a
  Desktop/*.txt
```

### Commit 2: Remove tracked secrets (if any)
```
Check: git log --all --diff-filter=A -- .fcc/.env .claude/.credentials.json .ollama/id_ed25519
If ever committed: git filter-branch or BFG Repo Cleaner
```

### Commit 3: Clean up artifacts
```
rm .ollama/EOF
rm .xsession-errors.old
rm -rf .fcc/logs/*.log  (keep latest)
```

### Commit 4: Fix permissions
```
chown -R anphuni:anphuni server_ops/  (if appropriate)
Or: move server_ops/ out of $HOME
```

## Do Now / Later / Never Touch

| Action | Timing | Reason |
|--------|--------|--------|
| Add `.fcc/`, `.ollama/`, `server_ops/` to `.gitignore` | **Do now** | Prevents accidental secret commits |
| Verify `.credentials.json` never in git history | **Do now** | Critical security check |
| Clean `.fcc/logs/` (keep last 3 days) | **Do now** | Reclaim ~1.8GB |
| Remove `.ollama/EOF` | **Do now** | Trivial cleanup |
| Remove `.xsession-errors.old` | **Do now** | Trivial cleanup |
| Move `.ollama/id_ed25519` to `.ssh/` | **Later** | Need to verify what uses it |
| Audit custom Ollama model provenance | **Later** | Requires model analysis |
| Implement FCC log rotation | **Later** | Requires config change |
| Audit GSD hooks for security | **Later** | Requires code review |
| Clean `.claude/file-history/` | **Later** | GSD manages this |
| Refactor aetherOS/odysseus fork relationship | **Never touch** | Separate concern |
| Modify FCC source | **Never touch** | uv-managed package |
| Modify Claude Code binary | **Never touch** | Proprietary, auto-updated |
