# Spike C0: Relevance/Ranking + Memory Taxonomy

## Goal

Define and spike a practical memory taxonomy + relevance/ranking approach for the awareness-agent daemon. Replace SQLite LIKE with deterministic local ranking (FTS5 + heuristics). Produce a working prototype with fixtures and eval.

## Context

- Spike A0: Daemon skeleton (SQLite, CLI, server, redaction)
- Spike B0: Claude Code integration (SessionStart hook, install/uninstall)
- Spike B0.1: Hardening (portability, quoting, untrusted framing, sanitization)
- Current recall: SQLite `LIKE '%query%'` — no ranking, no relevance, no taxonomy
- C0 plan documented in `tools/awareness-agent/docs/claude-code.md`

## Questions

1. What memory artifacts exist and what's persisted vs transient?
2. What practical taxonomy fits the existing schema + usage patterns?
3. What ranking approach is simple, deterministic, explainable, no LLM required?
4. Can we build a working prototype with fixtures + eval in a spike-sized change?

## Acceptance Criteria

- [ ] Memory type taxonomy documented with examples, retention, ranking signals
- [ ] FTS5 search replacing LIKE in recall
- [ ] Ranking function: recency decay + project boost + pinned boost + FTS5 BM25
- [ ] Schema migration: add kind, scope, source, confidence, tags, expires_at
- [ ] 8-15 synthetic memory fixtures covering multiple types
- [ ] 3-6 example queries with expected top-3 assertions
- [ ] Score breakdown/explainability in recall output
- [ ] Existing A0/B0 tests still pass
- [ ] No new dependencies (FTS5 is built into Python sqlite3)

## Out of Scope (C1+)

- Embeddings / vector search (keep optional/future)
- LLM-based ranking
- Automatic memory extraction from conversations
- Cross-session auto-capture
- Semantic action triggers

## Results

_(filled during spike)_

## Verdict

_(filled during spike)_
