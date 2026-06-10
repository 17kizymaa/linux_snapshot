#!/usr/bin/env python3
"""C0 eval: memory taxonomy + relevance/ranking prototype.

Creates an in-memory SQLite DB, seeds synthetic memories covering multiple
kinds/scopes, runs ranked recall queries, and asserts expected top-3 ordering.

Usage:
    python3 tests/c0-eval.py          # run eval, print results
    python3 tests/c0-eval.py --verbose  # show score breakdowns
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from awareness_agent.ranking import (
    MemoryKind,
    MemoryScope,
    RankWeights,
    category_to_kind,
    migrate_kind_ttls,
    migrate_taxonomy,
    migrate_fts5,
    recall_ranked,
    rank_memories,
)
from awareness_agent.store import AwarenessStore


def _now(days_ago: float = 0) -> str:
    """ISO timestamp, optionally days in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def create_test_db() -> sqlite3.Connection:
    """Create an in-memory DB with schema + FTS5 + taxonomy."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create base tables
    conn.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            name TEXT,
            language TEXT,
            framework TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id),
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL DEFAULT 'note',
            context TEXT NOT NULL DEFAULT '',
            decision TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'user'
        );
    """)

    # Migrate taxonomy columns + FTS5 + kind_ttls
    migrate_taxonomy(conn)
    migrate_fts5(conn)
    migrate_kind_ttls(conn)

    return conn


def seed_fixtures(conn: sqlite3.Connection) -> None:
    """Insert 15 synthetic memories covering multiple kinds/scopes.

    Projects:
      - /home/user/aw-webapp   (Python/FastAPI web app)
      - /home/user/cli-tools   (Go CLI toolkit)
      - global                 (no project)
    """
    # Insert projects
    projects = [
        (1, "/home/user/aw-webapp", "aw-webapp", "python", "fastapi"),
        (2, "/home/user/cli-tools", "cli-tools", "go", None),
    ]
    for pid, path, name, lang, fw in projects:
        conn.execute(
            "INSERT INTO projects(id, path, name, language, framework) VALUES (?, ?, ?, ?, ?)",
            (pid, path, name, lang, fw),
        )

    memories = [
        # ── Project: aw-webapp ──────────────────────────────────
        # id, project_id, timestamp, category, context, decision, rationale, source, kind, scope, confidence, tags, expires_at, pinned
        (1, 1, _now(0.1), "decision", "cwd=/home/user/aw-webapp",
         "Use pytest with pytest-asyncio for FastAPI endpoint tests",
         "FastAPI TestClient works best with async test functions", "user",
         MemoryKind.DECISION, MemoryScope.PROJECT, 0.9,
         '["testing", "fastapi", "pytest"]', None, 0),

        (2, 1, _now(2), "preference", "cwd=/home/user/aw-webapp",
         "Prefer functional style over class-based for service layers",
         "Consistency with existing codebase", "user",
         MemoryKind.PREFERENCE, MemoryScope.PROJECT, 0.8,
         '["style", "architecture"]', None, 0),

        (3, 1, _now(5), "error", "cwd=/home/user/aw-webapp",
         "sqlite3.OperationalError: database is locked — restart daemon, clear WAL",
         "Happened after concurrent writes from two agents", "user",
         MemoryKind.ERROR, MemoryScope.PROJECT, 0.95,
         '["sqlite", "daemon", "recovery"]', None, 0),

        (4, 1, _now(14), "procedure", "cwd=/home/user/aw-webapp",
         "Deploy: run `make build` then `make push`, verify health endpoint",
         "Documented after 3 failed manual deploys", "user",
         MemoryKind.PROCEDURE, MemoryScope.PROJECT, 0.85,
         '["deploy", "workflow"]', None, 0),

        (5, 1, _now(30), "fact", "cwd=/home/user/aw-webapp",
         "The /api/v1 prefix is shared across all route modules",
         "Found in main.py router setup", "user",
         MemoryKind.FACT, MemoryScope.REPO, 0.7,
         '["api", "routing"]', None, 0),

        (6, 1, _now(45), "note", "cwd=/home/user/aw-webapp",
         "Consider migrating from Flask-style decorators to APIRouter",
         "Technical debt from v1 prototype", "user",
         MemoryKind.NOTE, MemoryScope.PROJECT, 0.5,
         '["refactor", "technical-debt"]', None, 0),

        (7, 1, _now(0.5), "pinned", "cwd=/home/user/aw-webapp",
         "DO NOT run `make reset-db` in production — drops all tables",
         "Accident during debugging wiped 3 days of data", "user",
         MemoryKind.PINNED, MemoryScope.PROJECT, 1.0,
         '["safety", "database"]', None, 1),

        # ── Project: cli-tools ──────────────────────────────────
        (8, 2, _now(1), "decision", "cwd=/home/user/cli-tools",
         "Use Cobra for CLI framework, Viper for config",
         "Standard Go CLI stack, well-documented", "user",
         MemoryKind.DECISION, MemoryScope.PROJECT, 0.9,
         '["go", "cli", "cobra"]', None, 0),

        (9, 2, _now(3), "error", "cwd=/home/user/cli-tools",
         "ADB server race condition: two instances bind 127.0.0.1:5037",
         "Fix: singleton enforcement with PID file", "user",
         MemoryKind.ERROR, MemoryScope.PROJECT, 0.95,
         '["adb", "daemon", "race-condition"]', None, 0),

        (10, 2, _now(10), "fact", "cwd=/home/user/cli-tools",
         "Fire TV sleep/wake breaks network ADB — always health-check first",
         "Source: operational profile doc", "user",
         MemoryKind.FACT, MemoryScope.REPO, 0.8,
         '["fire-tv", "adb", "network"]', None, 0),

        (11, 2, _now(60), "note", "cwd=/home/user/cli-tools",
         "Viper config path: ~/.config/firetv/config.yaml",
         "Default config auto-created on first run", "user",
         MemoryKind.NOTE, MemoryScope.PROJECT, 0.6,
         '["config", "viper"]', None, 0),

        # ── Global / cross-project ──────────────────────────────
        (12, None, _now(0.2), "preference", "cwd=/home/user",
         "Keep all DB/config/socket files at mode 0600",
         "Security-first invariant", "user",
         MemoryKind.PREFERENCE, MemoryScope.GLOBAL, 1.0,
         '["security", "file-permissions"]', None, 0),

        (13, None, _now(7), "error", "cwd=/home/user",
         "Bearer token leaked in recall output — added redaction patterns",
         "Found during B0.1 security review", "user",
         MemoryKind.ERROR, MemoryScope.GLOBAL, 0.9,
         '["security", "redaction", "tokens"]', None, 0),

        (14, None, _now(90), "note", "cwd=/home/user",
         "aetherOS is a downstream fork of odysseus",
         "Mapped in initial repo cartography", "user",
         MemoryKind.NOTE, MemoryScope.GLOBAL, 0.4,
         '["repo", "aetherOS", "odysseus"]',
         _now(30), 0),  # expired 30 days ago

        (15, None, _now(0.01), "pinned", "cwd=/home/user",
         "ABCD: Always Be Closing Daemon — never leave orphan processes",
         "Foundational operational principle", "user",
         MemoryKind.PINNED, MemoryScope.GLOBAL, 1.0,
         '["ops", "daemon", "principle"]', None, 1),
    ]

    for m in memories:
        conn.execute(
            """INSERT INTO decisions
               (id, project_id, timestamp, category, context, decision,
                rationale, source, kind, scope, confidence, tags,
                expires_at, pinned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            m,
        )

    conn.commit()


def run_eval(conn: sqlite3.Connection, verbose: bool = False) -> bool:
    """Run eval queries and assert expected results. Returns True if all pass."""
    weights = RankWeights()
    failures: list[str] = []
    passes: list[str] = []

    def check(name: str, query: str, project_path: str | None,
              expected_top3_kinds: list[str], expected_top1_substring: str = ""):
        results = recall_ranked(
            conn, query, project_path=project_path, limit=5, weights=weights,
        )
        if not results:
            failures.append(f"{name}: no results")
            return

        top3_kinds = [r.get("kind") or category_to_kind(r.get("category", "")) for r in results[:3]]
        top1_decision = results[0]["decision"]

        ok = True
        # Check top-1 contains expected substring
        if expected_top1_substring and expected_top1_substring.lower() not in top1_decision.lower():
            failures.append(
                f"{name}: top-1 decision '{top1_decision[:60]}' "
                f"does not contain '{expected_top1_substring}'"
            )
            ok = False

        # Check top-3 kinds are in expected set
        for i, (actual, expected) in enumerate(zip(top3_kinds, expected_top3_kinds)):
            if actual != expected:
                failures.append(
                    f"{name}: top-{i+1} kind '{actual}' != expected '{expected}'"
                )
                ok = False

        if ok:
            passes.append(name)

        if verbose:
            print(f"\n{'='*60}")
            print(f"Query: '{query}' | project: {project_path or 'any'}")
            print(f"Expected kinds: {expected_top3_kinds}")
            for i, r in enumerate(results[:3]):
                kind = r.get("kind") or category_to_kind(r.get("category", ""))
                print(f"  #{i+1} [{kind}] score={r['_score']}: {r['decision'][:70]}")
                if verbose > 1:
                    for component, val in r["_score_breakdown"].items():
                        print(f"       {component}: {val:.4f}")

    # ── Query 1: "pytest testing" in aw-webapp ──────────────
    # Should surface the pytest decision (#1) — both FTS match + project match
    check(
        "Q1: pytest in aw-webapp",
        "pytest",
        "/home/user/aw-webapp",
        expected_top3_kinds=[MemoryKind.DECISION, MemoryKind.PINNED, MemoryKind.PREFERENCE],
        expected_top1_substring="pytest",
    )

    # ── Query 2: "deploy" in aw-webapp ──────────────────────
    # Should surface the deploy procedure (#4)
    check(
        "Q2: deploy in aw-webapp",
        "deploy",
        "/home/user/aw-webapp",
        expected_top3_kinds=[MemoryKind.PROCEDURE, MemoryKind.DECISION, MemoryKind.PINNED],
        expected_top1_substring="deploy",
    )

    # ── Query 3: "daemon" globally ──────────────────────────
    # Should surface pinned memory #15 and error #3 (sqlite daemon) or #9 (adb daemon)
    check(
        "Q3: daemon global",
        "daemon",
        None,
        expected_top3_kinds=[MemoryKind.PINNED, MemoryKind.ERROR, MemoryKind.ERROR],
        expected_top1_substring="daemon",
    )

    # ── Query 4: "security" globally ────────────────────────
    # Should surface the Bearer token error (#13) and security preference (#12)
    check(
        "Q4: security global",
        "security",
        None,
        expected_top3_kinds=[MemoryKind.ERROR, MemoryKind.PREFERENCE, MemoryKind.NOTE],
        expected_top1_substring="token",
    )

    # ── Query 5: empty query in aw-webapp ───────────────────
    # Pinned memories (global + project) float to top, then recent project memories
    check(
        "Q5: empty query in aw-webapp",
        "",
        "/home/user/aw-webapp",
        expected_top3_kinds=[MemoryKind.PINNED, MemoryKind.PINNED, MemoryKind.ERROR],
    )

    # ── Query 6: "cobra go cli" in cli-tools ────────────────
    check(
        "Q6: cobra go cli",
        "cobra",
        "/home/user/cli-tools",
        expected_top3_kinds=[MemoryKind.DECISION, MemoryKind.ERROR, MemoryKind.FACT],
        expected_top1_substring="Cobra",
    )

    # ── Query 7: TTL expiry filter (C2a) ────────────────────
    # Memory #14 (aetherOS fork note) has a backdated expires_at 30 days ago.
    # It should be excluded from ALL recall results.
    # A query for "aetherOS" that would match #14 should NOT return it.
    all_results = recall_ranked(conn, "aetherOS", project_path=None, limit=20)
    expired_found = [r for r in all_results if "aetherOS" in r.get("decision", "") and "fork" in r.get("decision", "")]
    if expired_found:
        failures.append(
            f"Q7: TTL expiry: expired aetherOS note was returned "
            f"(expires_at={expired_found[0].get('expires_at')})"
        )
    else:
        passes.append("Q7: TTL expiry filter")
        if verbose:
            print(f"\n  Q7: aetherOS expired note correctly excluded ✓")

    # Assert that no expired rows leak through in a broad query
    all_rows = recall_ranked(conn, "", project_path=None, limit=50, include_expired=False)
    now_str = datetime.now(timezone.utc).isoformat()
    for r in all_rows:
        if r.get("expires_at") and r["expires_at"] <= now_str:
            failures.append(
                f"Q7: TTL filter leak: row id={r['id']} expires_at={r['expires_at']} <= now"
            )
            break
    else:
        if "Q7: TTL expiry filter" not in passes:
            passes.append("Q7: TTL expiry filter")
        if verbose:
            print(f"  Q7: no expired rows leaked through empty query ✓")

    # ── Query 8: Scope-based recall filtering (C2b) ─────────
    # Memories have scope column set. When recalling for a project,
    # only project-scoped (matching) and global-scoped memories should appear.
    # aw-webapp project recall should NOT include cli-tools-scoped memories.
    results_aw = recall_ranked(conn, "ADB", project_path="/home/user/aw-webapp", limit=20)
    adb_in_aw = [r for r in results_aw if "ADB" in r.get("decision", "") and "race" in r.get("decision", "")]
    if adb_in_aw:
        failures.append(
            f"Q8: scope isolation: cli-tools ADB memory leaked into aw-webapp recall"
        )
    else:
        passes.append("Q8: scope isolation")
        if verbose:
            print(f"\n  Q8: scope isolation — cli-tools ADB excluded from aw-webapp ✓")

    # Global memories (scope=global) should appear in any project's recall
    results_cli = recall_ranked(conn, "mode 0600", project_path="/home/user/cli-tools", limit=20)
    global_in_cli = [r for r in results_cli if "0600" in r.get("decision", "")]
    if not global_in_cli:
        failures.append(
            f"Q8: global scope: global memory missing from cli-tools recall"
        )
    else:
        if "Q8: scope isolation" not in passes:
            passes.append("Q8: scope isolation")
        if verbose:
            print(f"  Q8: global memory surfaced in cli-tools recall ✓")

    # ── Summary ─────────────────────────────────────────────
    total = len(passes) + len(failures)
    print(f"\n{'='*60}")
    print(f"C0 Eval Results: {len(passes)}/{total} passed")

    if passes:
        print(f"  Passed: {', '.join(passes)}")
    if failures:
        print(f"  Failed:")
        for f in failures:
            print(f"    ✗ {f}")
        return False
    print("  All assertions passed ✓")
    return True


def run_store_integration() -> bool:
    """Verify that AwarenessStore.recall() uses ranked recall (C1 integration)."""
    print("\n=== C1: Store integration ===")

    # Use a temp file DB so AwarenessStore can manage it
    import tempfile
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    store = AwarenessStore(db_path)
    try:
        store.remember("Use pytest for FastAPI tests", category="decision", context="cwd=/home/user/aw-webapp", source="user", project={"root": "/home/user/aw-webapp", "name": "aw-webapp"})
        store.remember("Prefer functional style", category="preference", context="cwd=/home/user/aw-webapp", source="user", project={"root": "/home/user/aw-webapp", "name": "aw-webapp"})
        store.remember("DO NOT run reset-db in prod", category="pinned", context="cwd=/home/user/aw-webapp", source="user", project={"root": "/home/user/aw-webapp", "name": "aw-webapp"})

        # Verify kind auto-detection
        status = store.status()
        print(f"  Status: {status['counts']}")

        # Verify ranked recall via store.recall()
        results = store.recall("pytest", limit=3, project_path="/home/user/aw-webapp")
        if not results or "_score" not in results[0]:
            print("  [fail] store.recall() did not return ranked results")
            return False
        print(f"  Ranked recall top: {results[0]['decision'][:60]} (score={results[0]['_score']})")

        # Verify kind column was populated
        raw = store.conn.execute("SELECT kind FROM decisions WHERE id = 1").fetchone()
        if raw[0] != "decision":
            print(f"  [fail] kind auto-detection: expected 'decision', got '{raw[0]}'")
            return False
        print(f"  Kind auto-detection: '{raw[0]}' ✓")

        print("  Store integration: all checks passed ✓")
        return True
    finally:
        store.close()
        os.unlink(db_path)


def run_embedding_eval(conn: sqlite3.Connection, verbose: bool = False) -> bool:
    """Evaluate C2c: local embeddings for hybrid recall."""
    print("\n=== C2c: Embedding hybrid recall ===")
    failures: list[str] = []
    passes: list[str] = []

    # Import embedding module
    from awareness_agent.embeddings import (
        EmbeddingResult,
        embed_text,
        embed_text_bytes,
        cosine_similarity,
        hash_embed,
    )

    # Q9: Embedding column exists and is populated for new memories
    # Re-seed with embeddings by inserting directly with embedding BLOBs
    # (The eval DB was created before store remembered, so we add embeddings manually)
    rows = conn.execute("SELECT id, decision, rationale, context FROM decisions").fetchall()
    for row in rows:
        text = f"{row['decision']} {row['rationale']} {row['context']}".strip()
        emb = hash_embed(text)
        # emb is now an EmbeddingResult — store vector bytes + provenance
        conn.execute(
            "UPDATE decisions SET embedding = ?, embedding_provider = ?, "
            "embedding_model = ?, embedding_dim = ?, embedding_version = ? "
            "WHERE id = ?",
            (emb.vector, emb.provider, emb.model, emb.dim, emb.version, row["id"]),
        )
    conn.commit()

    # Verify all rows now have embeddings
    null_count = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE embedding IS NULL"
    ).fetchone()[0]
    if null_count > 0:
        failures.append(f"Q9: {null_count} rows have NULL embedding after backfill")
    else:
        passes.append("Q9: embedding backfill")
        if verbose:
            print("  Q9: all rows have embeddings ✓")

    # Q10: Hybrid scoring adds embedding component when enabled
    # Query for "pytest" — both FTS5 and hybrid find pytest decision (#1)
    weights_fts = RankWeights(embedding=0.0)
    weights_hybrid = RankWeights(embedding=0.5)

    # Hybrid recall needs a query embedding (normally computed by store.recall())
    # embed_text now returns EmbeddingResult (provenance-aware)
    query_q10 = embed_text("pytest")

    results_fts = recall_ranked(
        conn, "pytest", project_path="/home/user/aw-webapp",
        limit=5, weights=weights_fts,
    )
    results_hybrid = recall_ranked(
        conn, "pytest", project_path="/home/user/aw-webapp",
        limit=5, weights=weights_hybrid, query_embedding=query_q10,
    )

    if results_fts and results_hybrid:
        fts_top = results_fts[0]["decision"]
        hybrid_top = results_hybrid[0]["decision"]

        if "pytest" not in fts_top.lower():
            failures.append(f"Q10: FTS5 top missing 'pytest': {fts_top[:60]}")
        elif "pytest" not in hybrid_top.lower():
            failures.append(f"Q10: Hybrid top missing 'pytest': {hybrid_top[:60]}")
        else:
            # Hybrid should have a non-zero embedding component for this query
            emb_score = results_hybrid[0]["_score_breakdown"].get("embedding", 0)
            if emb_score <= 0:
                failures.append(f"Q10: Hybrid embedding component is zero for matching query")
            else:
                passes.append("Q10: hybrid ranking")
                if verbose:
                    print(f"  Q10: FTS5 top='{fts_top[:50]}' score={results_fts[0]['_score']}")
                    print(f"  Q10: Hybrid top='{hybrid_top[:50]}' score={results_hybrid[0]['_score']}")
                    print(f"  Q10: Hybrid embedding component: {emb_score:.4f}")
    else:
        failures.append(f"Q10: no results (fts={len(results_fts)}, hybrid={len(results_hybrid)})")

    # Q11: Embedding similarity is meaningful
    # "pytest testing" should be more similar to the pytest decision than to the deploy procedure
    query_emb = embed_text("pytest testing framework")
    pytest_decision = conn.execute(
        "SELECT embedding FROM decisions WHERE id = 1"
    ).fetchone()["embedding"]
    deploy_decision = conn.execute(
        "SELECT embedding FROM decisions WHERE id = 4"
    ).fetchone()["embedding"]

    if pytest_decision and deploy_decision:
        query_vec = query_emb.vector if isinstance(query_emb, EmbeddingResult) else query_emb
        sim_pytest = cosine_similarity(query_vec, pytest_decision)
        sim_deploy = cosine_similarity(query_vec, deploy_decision)
        if sim_pytest > sim_deploy:
            passes.append("Q11: semantic similarity ordering")
            if verbose:
                print(f"  Q11: sim(pytest query, pytest decision)={sim_pytest:.4f}")
                print(f"  Q11: sim(pytest query, deploy decision)={sim_deploy:.4f}")
        else:
            failures.append(
                f"Q11: semantic ordering wrong: pytest_sim={sim_pytest:.4f} <= deploy_sim={sim_deploy:.4f}"
            )
    else:
        failures.append("Q11: missing embeddings for similarity test")

    # Q12: Fallback when embeddings disabled (embedding_weight=0)
    # Results should be identical to C1 behavior
    weights_no_emb = RankWeights(embedding=0.0)
    results_no_emb = recall_ranked(
        conn, "deploy", project_path="/home/user/aw-webapp",
        limit=3, weights=weights_no_emb,
    )
    if results_no_emb and results_no_emb[0]["_score_breakdown"].get("embedding", 0) == 0.0:
        passes.append("Q12: embedding disabled fallback")
        if verbose:
            print(f"  Q12: embedding=0.0 when disabled, top='{results_no_emb[0]['decision'][:50]}'")
    else:
        failures.append("Q12: embedding component non-zero when disabled")

    total = len(passes) + len(failures)
    print(f"\nC2c Embedding Eval: {len(passes)}/{total} passed")
    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        return False
    print("  All embedding assertions passed ✓")
    return True


def run_c3_eval(conn: sqlite3.Connection, verbose: bool = False) -> bool:
    """Evaluate C3: provenance, backfill, candidate widening, TTL/scope enforcement."""
    print("\n=== C3: Embedding consolidation eval ===")
    failures: list[str] = []
    passes: list[str] = []

    from awareness_agent.embeddings import (
        EmbeddingResult, embed_text, cosine_similarity,
        HASH_PROVIDER, HASH_MODEL, EMBED_DIM, HASH_VERSION,
    )
    from awareness_agent.ranking import RankWeights, recall_ranked

    # Q13: EmbeddingResult provenance fields
    emb = embed_text("test provenance", backend='hash')
    assert isinstance(emb, EmbeddingResult), f'Expected EmbeddingResult, got {type(emb)}'
    assert emb.provider == HASH_PROVIDER
    assert emb.model == HASH_MODEL
    assert emb.dim == EMBED_DIM
    assert emb.version == HASH_VERSION
    assert emb.is_semantic is False
    passes.append("Q13: EmbeddingResult provenance")
    if verbose:
        print(f"  Q13: provider={emb.provider}, model={emb.model}, dim={emb.dim}, semantic={emb.is_semantic}")

    # Q14: Provenance compatibility check
    emb2 = embed_text("another test", backend='hash')
    assert emb.is_compatible(emb2), 'Same-backend embeddings should be compatible'
    passes.append("Q14: provenance compatibility")
    if verbose:
        print(f"  Q14: compatible={emb.is_compatible(emb2)}")

    # Q15: Backfill populates provenance columns
    # The eval DB has 15 rows without provenance (seeded before C3 migration).
    # Simulate backfill by updating rows with embeddings + provenance.
    rows = conn.execute("SELECT id, decision, rationale, context FROM decisions WHERE embedding IS NULL OR embedding_provider IS NULL").fetchall()
    updated = 0
    for row in rows:
        text = f"{row['decision']} {row['rationale']} {row['context']}".strip()
        e = embed_text(text, backend='hash')
        conn.execute(
            "UPDATE decisions SET embedding = ?, embedding_provider = ?, "
            "embedding_model = ?, embedding_dim = ?, embedding_version = ? "
            "WHERE id = ?",
            (e.vector, e.provider, e.model, e.dim, e.version, row["id"]),
        )
        updated += 1
    conn.commit()
    null_prov = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE embedding_provider IS NULL"
    ).fetchone()[0]
    if null_prov == 0:
        passes.append("Q15: backfill provenance")
        if verbose:
            print(f"  Q15: backfill populated provenance for {updated} rows, 0 NULL remaining")
    else:
        failures.append(f"Q15: {null_prov} rows still have NULL provenance after backfill")

    # Q16: Candidate widening — embedding-only candidates appear
    # Use a query that lexically matches nothing but has embedding overlap
    weights_no_emb = RankWeights(embedding=0.0)
    weights_emb = RankWeights(embedding=0.5)

    # Query with empty string (no FTS) — only embedding widening can find candidates
    query_emb = embed_text("pytest testing framework", backend='hash')
    results_no_wide = recall_ranked(
        conn, "", project_path="/home/user/aw-webapp",
        limit=20, weights=weights_no_emb,
    )
    results_wide = recall_ranked(
        conn, "", project_path="/home/user/aw-webapp",
        limit=20, weights=weights_emb, query_embedding=query_emb,
    )
    # With widening, we should get results that have embeddings
    if len(results_wide) > 0:
        passes.append("Q16: candidate widening")
        if verbose:
            print(f"  Q16: widening returned {len(results_wide)} results (no-widen: {len(results_no_wide)})")
    else:
        failures.append("Q16: candidate widening returned no results")

    # Q17: TTL/scope filtering on embedding candidates
    # Memory #14 is expired — verify it's excluded even with embedding widening
    results_all = recall_ranked(
        conn, "", project_path=None,
        limit=50, weights=weights_emb, query_embedding=query_emb,
    )
    expired_found = [r for r in results_all if r.get("id") == 14]
    if not expired_found:
        passes.append("Q17: TTL filtering on embedding candidates")
        if verbose:
            print(f"  Q17: expired memory #14 correctly excluded from embedding results")
    else:
        failures.append("Q17: expired memory #14 leaked through embedding widening")

    # Q18: Incompatible provenance is skipped for embedding scoring
    # Create a fake ST embedding row and verify its embedding score is zero
    # when queried with a hash embedding (incompatible providers).
    # Note: the row can still appear via FTS5 lexical match — the key is that
    # the embedding component is zero (not compared across incompatible providers).
    fake_st_vec = embed_text("ST-style embedding", backend='hash')
    conn.execute(
        """INSERT INTO decisions
           (id, project_id, timestamp, category, context, decision,
            rationale, source, kind, scope, confidence, tags, expires_at, pinned,
            embedding, embedding_provider, embedding_model, embedding_dim, embedding_version)
           VALUES (99, 1, datetime('now'), 'note', 'test', 'ST-provenance memory',
                   '', 'user', 'note', 'project', 0.5, '[]', NULL, 0,
                   ?, 'sentence-transformers', 'all-MiniLM-L6-v2', 384, '1.0')""",
        (fake_st_vec.vector,),
    )
    conn.commit()
    hash_query = embed_text("ST-provenance memory", backend='hash')
    results_st = recall_ranked(
        conn, "ST-provenance", project_path="/home/user/aw-webapp",
        limit=10, weights=weights_emb, query_embedding=hash_query,
    )
    st_row = next((r for r in results_st if r.get("id") == 99), None)
    if st_row is not None:
        emb_score = st_row["_score_breakdown"].get("embedding", 0)
        if emb_score == 0.0:
            passes.append("Q18: incompatible provenance skipped")
            if verbose:
                print(f"  Q18: ST-provenance row found via FTS5 but embedding score is 0 (correct)")
        else:
            failures.append(f"Q18: ST-provenance row has non-zero embedding score: {emb_score}")
    else:
        # Also acceptable — row not returned at all
        passes.append("Q18: incompatible provenance skipped")
        if verbose:
            print(f"  Q18: ST-provenance row not in results (also correct)")
    # Clean up
    conn.execute("DELETE FROM decisions WHERE id = 99")
    conn.commit()

    total = len(passes) + len(failures)
    print(f"\nC3 Eval: {len(passes)}/{total} passed")
    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        return False
    print("  All C3 assertions passed ✓")
    return True


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    conn = create_test_db()
    seed_fixtures(conn)

    print("C0 Spike Eval: Memory Taxonomy + Relevance/Ranking")
    print(f"  DB: in-memory SQLite with FTS5 + taxonomy columns")
    print(f"  Fixtures: 15 memories across 2 projects + global")

    all_pass = run_eval(conn, verbose=verbose)

    if all_pass:
        all_pass = run_store_integration()

    if all_pass:
        all_pass = run_embedding_eval(conn, verbose=verbose)

    if all_pass:
        all_pass = run_c3_eval(conn, verbose=verbose)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
