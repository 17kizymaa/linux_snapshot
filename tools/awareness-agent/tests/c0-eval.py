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

    # Migrate taxonomy columns + FTS5
    migrate_taxonomy(conn)
    migrate_fts5(conn)

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
         _now(-30), 0),  # expired 30 days ago

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

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
