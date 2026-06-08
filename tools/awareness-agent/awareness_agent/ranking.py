from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Memory taxonomy
# ---------------------------------------------------------------------------

class MemoryKind:
    """Memory kind — what *type* of knowledge this memory represents."""
    DECISION = "decision"       # A choice made (e.g. "use pytest")
    PREFERENCE = "preference"   # User preference (e.g. "prefer functional style")
    FACT = "fact"               # Stable fact learned (e.g. "project uses FastAPI")
    PROCEDURE = "procedure"     # Repeatable workflow (e.g. "deploy: build then push")
    ERROR = "error"             # Failure + recovery (e.g. "adb offline → restart server")
    NOTE = "note"               # General observation
    TASK = "task"               # Pending/completed task
    PINNED = "pinned"           # User-pinned, always surface


class MemoryScope:
    """Memory scope — *where* this memory is relevant."""
    GLOBAL = "global"           # Any session, any project
    PROJECT = "project"         # Specific project (matched by path)
    REPO = "repo"               # Specific git repo
    PATH = "path"               # Specific file/directory
    SESSION = "session"         # Single session only (ephemeral)


# Mapping from existing category strings to MemoryKind
CATEGORY_TO_KIND: dict[str, str] = {
    "decision": MemoryKind.DECISION,
    "preference": MemoryKind.PREFERENCE,
    "fact": MemoryKind.FACT,
    "procedure": MemoryKind.PROCEDURE,
    "error": MemoryKind.ERROR,
    "note": MemoryKind.NOTE,
    "task": MemoryKind.TASK,
    "pinned": MemoryKind.PINNED,
}


def category_to_kind(category: str) -> str:
    """Map a free-text category to a MemoryKind."""
    normalized = category.strip().lower().replace(" ", "_")
    return CATEGORY_TO_KIND.get(normalized, MemoryKind.NOTE)


# ---------------------------------------------------------------------------
# Ranking config
# ---------------------------------------------------------------------------

@dataclass
class RankWeights:
    """Tunable weights for the ranking function."""
    fts_bm25: float = 1.0        # FTS5 BM25 score (lower = better, so we negate)
    recency: float = 0.3          # Recency boost (0-1, newer = higher)
    project_match: float = 0.4    # Boost for current project match
    pinned_boost: float = 0.5     # Boost for pinned memories
    error_boost: float = 0.2      # Small boost for error/failure memories
    source_boost: float = 0.1     # Boost for user-sourced vs auto-sourced

    # Decay: half-life in days. 0 = no decay.
    recency_half_life_days: float = 30.0


# ---------------------------------------------------------------------------
# Ranking function
# ---------------------------------------------------------------------------

def _parse_timestamp(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp from SQLite."""
    if not ts:
        return None
    try:
        # Handle both "YYYY-MM-DD HH:MM:SS" and ISO formats
        return datetime.fromisoformat(ts.replace(" ", "T"))
    except (ValueError, AttributeError):
        return None


def _recency_score(timestamp_str: str, half_life_days: float) -> float:
    """Exponential decay recency score in [0, 1]. Newer = higher."""
    if half_life_days <= 0:
        return 0.5  # neutral
    ts = _parse_timestamp(timestamp_str)
    if ts is None:
        return 0.3  # unknown age = below average
    now = datetime.now(timezone.utc)
    # Handle naive timestamps
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = (now - ts).total_seconds() / 86400.0
    # exponential decay: score = 2^(-age/half_life)
    return math.pow(2.0, -age_days / half_life_days)


def rank_memories(
    rows: list[dict[str, Any]],
    *,
    current_project_path: str | None = None,
    weights: RankWeights | None = None,
) -> list[dict[str, Any]]:
    """Rank a list of memory rows with score breakdown.

    Each row gets a '_score' and '_score_breakdown' added.
    Rows are sorted by _score descending.
    """
    if weights is None:
        weights = RankWeights()

    scored = []
    for row in rows:
        breakdown: dict[str, float] = {}

        # 1) FTS5 BM25: rank column is negative BM25 (sqlite returns it that way)
        #    We negate so higher = better, then normalize to ~[0, 1]
        fts_rank = row.get("_fts_rank")
        if fts_rank is not None:
            # FTS5 rank is -BM25, so -rank = BM25 (positive, lower is better)
            # Convert to a 0-1 score: 1 / (1 + BM25)
            bm25 = max(0.0, -float(fts_rank))
            breakdown["fts"] = weights.fts_bm25 * (1.0 / (1.0 + bm25))
        else:
            breakdown["fts"] = 0.0

        # 2) Recency
        ts = row.get("timestamp", "")
        r_score = _recency_score(ts, weights.recency_half_life_days)
        breakdown["recency"] = weights.recency * r_score

        # 3) Project match
        row_project = row.get("project_path") or ""
        if current_project_path and row_project:
            if row_project == current_project_path:
                breakdown["project"] = weights.project_match
            else:
                breakdown["project"] = 0.0
        else:
            breakdown["project"] = weights.project_match * 0.5  # partial

        # 4) Pinned boost
        kind = row.get("kind") or category_to_kind(row.get("category", "note"))
        if kind == MemoryKind.PINNED:
            breakdown["pinned"] = weights.pinned_boost
        else:
            breakdown["pinned"] = 0.0

        # 5) Error boost (failure memories are often highly relevant)
        if kind == MemoryKind.ERROR:
            breakdown["error"] = weights.error_boost
        else:
            breakdown["error"] = 0.0

        # 6) Source boost
        source = (row.get("source") or "user").lower()
        if source == "user":
            breakdown["source"] = weights.source_boost
        else:
            breakdown["source"] = 0.0

        total = sum(breakdown.values())
        scored.append({**row, "_score": round(total, 4), "_score_breakdown": breakdown})

    scored.sort(key=lambda r: r["_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# FTS5 schema + migration
# ---------------------------------------------------------------------------

FTS5_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    decision,
    rationale,
    context,
    category,
    content=decisions,
    content_rowid=id
);
"""

FTS5_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
    INSERT INTO decisions_fts(rowid, decision, rationale, context, category)
    VALUES (new.id, new.decision, new.rationale, new.context, new.category);
END;

CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, decision, rationale, context, category)
    VALUES ('delete', old.id, old.decision, old.rationale, old.context, old.category);
END;

CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, decision, rationale, context, category)
    VALUES ('delete', old.id, old.decision, old.rationale, old.context, old.category);
    INSERT INTO decisions_fts(rowid, decision, rationale, context, category)
    VALUES (new.id, new.decision, new.rationale, new.context, new.category);
END;
"""

# Schema additions for memory taxonomy
TAXONOMY_SCHEMA = """
ALTER TABLE decisions ADD COLUMN kind TEXT NOT NULL DEFAULT '';
ALTER TABLE decisions ADD COLUMN scope TEXT NOT NULL DEFAULT 'project';
ALTER TABLE decisions ADD COLUMN confidence REAL NOT NULL DEFAULT 0.5;
ALTER TABLE decisions ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE decisions ADD COLUMN expires_at TEXT;
ALTER TABLE decisions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;
"""

TAXONOMY_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_decisions_kind ON decisions(kind);
CREATE INDEX IF NOT EXISTS idx_decisions_scope ON decisions(scope);
CREATE INDEX IF NOT EXISTS idx_decisions_pinned ON decisions(pinned);
CREATE INDEX IF NOT EXISTS idx_decisions_expires ON decisions(expires_at);
"""


def migrate_taxonomy(conn: sqlite3.Connection) -> None:
    """Add taxonomy columns to decisions table if they don't exist."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
    if "kind" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN kind TEXT NOT NULL DEFAULT ''")
    if "scope" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN scope TEXT NOT NULL DEFAULT 'project'")
    if "confidence" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN confidence REAL NOT NULL DEFAULT 0.5")
    if "tags" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    if "expires_at" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN expires_at TEXT")
    if "pinned" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
    # Create indexes
    conn.executescript(TAXONOMY_INDEXES)


def migrate_fts5(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table and sync triggers."""
    conn.executescript(FTS5_SCHEMA)
    conn.executescript(FTS5_TRIGGERS)
    # Backfill existing rows
    conn.execute("""
        INSERT OR REPLACE INTO decisions_fts(rowid, decision, rationale, context, category)
        SELECT id, decision, rationale, context, category FROM decisions
    """)


def recall_ranked(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    project_path: str | None = None,
    limit: int = 10,
    weights: RankWeights | None = None,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    """Ranked recall using FTS5 + heuristic scoring.

    If query is empty, falls back to recency + metadata scoring (no FTS).
    """
    if weights is None:
        weights = RankWeights()

    limit = max(1, min(int(limit), 100))

    if query.strip():
        # FTS5 search: join decisions with fts table for BM25 rank
        rows = conn.execute(
            """
            SELECT d.id, d.timestamp, d.category, d.context, d.decision,
                   d.rationale, d.source, d.kind, d.scope, d.confidence,
                   d.tags, d.expires_at, d.pinned,
                   p.name AS project_name, p.path AS project_path,
                   fts.rank AS _fts_rank
            FROM decisions_fts fts
            JOIN decisions d ON d.id = fts.rowid
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE decisions_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ?
            """,
            (query, limit * 3),  # over-fetch for post-ranking
        ).fetchall()
    else:
        # No query: return recent decisions, scored by metadata only
        if not include_expired:
            expire_filter = "(d.expires_at IS NULL OR d.expires_at > datetime('now'))"
        else:
            expire_filter = "1=1"

        rows = conn.execute(
            f"""
            SELECT d.id, d.timestamp, d.category, d.context, d.decision,
                   d.rationale, d.source, d.kind, d.scope, d.confidence,
                   d.tags, d.expires_at, d.pinned,
                   p.name AS project_name, p.path AS project_path,
                   NULL AS _fts_rank
            FROM decisions d
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE {expire_filter}
            ORDER BY d.timestamp DESC, d.id DESC
            LIMIT ?
            """,
            (limit * 3,),
        ).fetchall()

    # Filter expired
    if not include_expired:
        now_str = datetime.now(timezone.utc).isoformat()
        rows = [
            r for r in rows
            if not r["expires_at"] or r["expires_at"] > now_str
        ]

    # Convert to dicts
    result = [dict(r) for r in rows]

    # Apply ranking
    ranked = rank_memories(
        result,
        current_project_path=project_path,
        weights=weights,
    )

    return ranked[:limit]
