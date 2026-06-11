from __future__ import annotations

import copy
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Union

from .embeddings import EmbeddingResult

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
    "dec": MemoryKind.DECISION,
    "preference": MemoryKind.PREFERENCE,
    "pref": MemoryKind.PREFERENCE,
    "prefer": MemoryKind.PREFERENCE,
    "fact": MemoryKind.FACT,
    "procedure": MemoryKind.PROCEDURE,
    "proc": MemoryKind.PROCEDURE,
    "error": MemoryKind.ERROR,
    "err": MemoryKind.ERROR,
    "bug": MemoryKind.ERROR,
    "note": MemoryKind.NOTE,
    "task": MemoryKind.TASK,
    "todo": MemoryKind.TASK,
    "pinned": MemoryKind.PINNED,
    "pin": MemoryKind.PINNED,
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

    # Embedding hybrid scoring (C2c)
    embedding: float = 0.0        # Weight for cosine similarity (0 = embeddings disabled)
    embedding_threshold: float = 0.3  # Minimum cosine sim to include embedding boost


_DEFAULT_RANK_WEIGHTS = RankWeights()


def set_default_rank_weights(weights: RankWeights) -> None:
    global _DEFAULT_RANK_WEIGHTS
    _DEFAULT_RANK_WEIGHTS = copy.deepcopy(weights)


def default_rank_weights() -> RankWeights:
    return copy.deepcopy(_DEFAULT_RANK_WEIGHTS)


# ---------------------------------------------------------------------------
# Per-kind TTL config
# ---------------------------------------------------------------------------

# Default TTL (in days) per memory kind.  None = never expires.
KIND_TTL_DEFAULTS: dict[str, int | None] = {
    MemoryKind.DECISION: None,      # permanent
    MemoryKind.PREFERENCE: None,    # permanent
    MemoryKind.FACT: None,          # permanent
    MemoryKind.PROCEDURE: None,     # permanent
    MemoryKind.ERROR: 90,           # 90 days
    MemoryKind.NOTE: 30,            # 30 days
    MemoryKind.TASK: 30,            # 30 days
    MemoryKind.PINNED: None,        # permanent
}

# Config table for runtime TTL overrides.
KIND_TTL_TABLE = """
CREATE TABLE IF NOT EXISTS kind_ttls (
    kind TEXT PRIMARY KEY,
    ttl_days INTEGER  -- NULL = never expires
);
"""


def migrate_kind_ttls(conn: sqlite3.Connection) -> None:
    """Create kind_ttls config table and seed defaults."""
    conn.executescript(KIND_TTL_TABLE)
    # Seed defaults (idempotent)
    for kind, ttl in KIND_TTL_DEFAULTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO kind_ttls(kind, ttl_days) VALUES (?, ?)",
            (kind, ttl),
        )
    conn.commit()


def get_ttl_days(conn: sqlite3.Connection, kind: str) -> int | None:
    """Look up TTL for a kind. Falls back to KIND_TTL_DEFAULTS, then 30."""
    row = conn.execute(
        "SELECT ttl_days FROM kind_ttls WHERE kind = ?", (kind,)
    ).fetchone()
    if row is not None:
        return row[0]  # could be None (never expires)
    return KIND_TTL_DEFAULTS.get(kind, 30)


def compute_expires_at(
    conn: sqlite3.Connection, kind: str, now: datetime | None = None,
) -> str | None:
    """Return ISO-8601 expiry timestamp for a kind, or None for no expiry."""
    ttl = get_ttl_days(conn, kind)
    if ttl is None:
        return None  # never expires
    if now is None:
        now = datetime.now(timezone.utc)
    return (now + timedelta(days=ttl)).isoformat()


# ---------------------------------------------------------------------------
# Scope auto-detection
# ---------------------------------------------------------------------------

# Keywords that suggest a memory is project-specific when found in context/decision.
_PROJECT_SIGNS = ("cwd=", "project", "repo", "deploy", "build", "makefile",
                  "package.json", "setup.py", "cargo.toml", "go.mod",
                  "requirements.txt", "dockerfile", "docker-compose")

# Kinds that default to global unless project context is detected.
_GLOBAL_KINDS = {MemoryKind.PREFERENCE, MemoryKind.PINNED}


def detect_scope(
    *,
    kind: str,
    context: str,
    decision: str,
    project_id: int | None,
    known_project_paths: list[str] | None = None,
) -> str:
    """Deterministic scope auto-detection.

    Heuristic:
      1. If no project association (project_id is None) and no project paths
         referenced in context/decision → GLOBAL.
      2. If kind is preference/pinned and context has no project path reference
         → GLOBAL (cross-cutting preferences).
      3. If context or decision text references a known project path → PROJECT.
      4. If project_id is set and context contains cwd= or project signals → PROJECT.
      5. Fail-closed default: PROJECT (safe — won't leak, just narrower).

    Returns one of MemoryScope.GLOBAL or MemoryScope.PROJECT.
    """
    text = f"{context} {decision}".lower()

    # Check if any known project path appears in the text
    if known_project_paths:
        for p in known_project_paths:
            if p.lower() in text:
                return MemoryScope.PROJECT

    # Check for project-specific signals in text
    for sign in _PROJECT_SIGNS:
        if sign in text:
            return MemoryScope.PROJECT

    # If project_id is set, the memory was explicitly associated with a project
    if project_id is not None:
        return MemoryScope.PROJECT

    # Preferences/pinned without project signals → global
    if kind in _GLOBAL_KINDS:
        return MemoryScope.GLOBAL

    # Fail-closed: default to project (narrower, safer)
    return MemoryScope.PROJECT


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
    query_embedding: EmbeddingResult | bytes | None = None,
) -> list[dict[str, Any]]:
    """Rank a list of memory rows with score breakdown.

    Each row gets a '_score' and '_score_breakdown' added.
    Rows are sorted by _score descending.

    If query_embedding is provided and weights.embedding > 0, cosine similarity
    is computed against each row's stored embedding and added as an embedding
    boost component.
    """
    if weights is None:
        weights = default_rank_weights()

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

        # 7) Embedding cosine similarity (C2c/C3)
        breakdown["embedding"] = 0.0
        if (
            query_embedding is not None
            and weights.embedding > 0
            and "embedding" in row
            and row["embedding"] is not None
        ):
            # C3: provenance compatibility check
            row_provider = row.get("embedding_provider")
            row_model = row.get("embedding_model")
            row_dim = row.get("embedding_dim")
            query_provider = query_embedding.provider if isinstance(query_embedding, EmbeddingResult) else None
            query_model = query_embedding.model if isinstance(query_embedding, EmbeddingResult) else None
            query_dim = query_embedding.dim if isinstance(query_embedding, EmbeddingResult) else None

            # Skip if provenance is known and incompatible
            if query_provider is not None and row_provider is not None:
                if (query_provider != row_provider
                        or query_model != row_model
                        or query_dim != row_dim):
                    breakdown["embedding"] = 0.0
                    total = sum(breakdown.values())
                    scored.append({**row, "_score": round(total, 4), "_score_breakdown": breakdown})
                    continue

            try:
                vec_bytes = query_embedding.vector if isinstance(query_embedding, EmbeddingResult) else query_embedding
                from .embeddings import cosine_similarity
                sim = cosine_similarity(vec_bytes, row["embedding"])
                if math.isnan(sim) or math.isinf(sim):
                    breakdown["embedding"] = 0.0
                elif sim >= weights.embedding_threshold:
                    breakdown["embedding"] = weights.embedding * sim
                else:
                    breakdown["embedding"] = 0.0
            except Exception:
                breakdown["embedding"] = 0.0

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
    content_rowid=id,
    tokenize='trigram'
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

# Schema additions for embeddings (C2c + C3)
EMBEDDING_SCHEMA = """
ALTER TABLE decisions ADD COLUMN embedding BLOB;
"""

EMBEDDING_PROVENANCE_SCHEMA = """
ALTER TABLE decisions ADD COLUMN embedding_provider TEXT;
ALTER TABLE decisions ADD COLUMN embedding_model TEXT;
ALTER TABLE decisions ADD COLUMN embedding_dim INTEGER;
ALTER TABLE decisions ADD COLUMN embedding_version TEXT;
"""

EMBEDDING_INDEX = """
CREATE INDEX IF NOT EXISTS idx_decisions_embedding ON decisions(embedding);
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
    if "embedding" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN embedding BLOB")
    # C3: embedding provenance columns
    if "embedding_provider" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN embedding_provider TEXT")
    if "embedding_model" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN embedding_model TEXT")
    if "embedding_dim" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN embedding_dim INTEGER")
    if "embedding_version" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN embedding_version TEXT")
    # Create indexes
    conn.executescript(TAXONOMY_INDEXES)
    conn.executescript(EMBEDDING_INDEX)


def migrate_fts5(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table and sync triggers."""
    conn.executescript(FTS5_SCHEMA)
    conn.executescript(FTS5_TRIGGERS)
    # Backfill existing rows
    conn.execute("""
        INSERT OR REPLACE INTO decisions_fts(rowid, decision, rationale, context, category)
        SELECT id, decision, rationale, context, category FROM decisions
    """)


def _jaccard_similarity(a: str, b: str) -> float:
    """Character-level bigram Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    a_bigrams = set(a[i:i + 2] for i in range(len(a) - 1))
    b_bigrams = set(b[i:i + 2] for i in range(len(b) - 1))
    if not a_bigrams or not b_bigrams:
        return 0.0
    intersection = a_bigrams & b_bigrams
    union = a_bigrams | b_bigrams
    return len(intersection) / len(union)


def _dedup_memories(
    memories: list[dict[str, Any]],
    threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Remove near-duplicate memories, keeping the higher-scored one.

    Uses character-bigram Jaccard similarity on the decision text.
    Only deduplicates among items that are adjacent in the ranked list
    (i.e. likely to be similar).
    """
    if len(memories) <= 1:
        return memories

    kept: list[dict[str, Any]] = []
    seen_texts: list[str] = []

    for mem in memories:
        decision = (mem.get("decision") or "").lower().strip()
        is_dup = False
        for seen in seen_texts:
            if _jaccard_similarity(decision, seen) >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(mem)
            seen_texts.append(decision)

    return kept


def _escape_fts5_query(query: str) -> str:
    """Escape a user query for safe FTS5 MATCH usage.

    Splits on whitespace, quotes each term to avoid FTS5 operators
    (NOT, AND, OR, -, ^, *, etc.), and joins with AND.
    Falls back to the original query if empty after escaping.
    """
    import re
    # Split on whitespace, filter empty
    terms = [t for t in query.strip().split() if t]
    if not terms:
        return ""
    # Quote each term — double-quote wrapping prevents FTS5 operator parsing
    escaped = " ".join(f'"{t}"' for t in terms)
    return escaped


def _embedding_widening_candidates(
    conn: sqlite3.Connection,
    *,
    query_embedding: EmbeddingResult,
    project_path: str | None,
    scope_filter: str,
    scope_params: tuple,
    limit: int,
    include_expired: bool,
) -> list[sqlite3.Row]:
    """Fetch embedding-only candidates via brute-force cosine similarity.

    This is the C3 semantic candidate widening step: find memories whose
    embeddings are similar to the query embedding, even if they share no
    lexical overlap with the query text.

    Returns rows that pass TTL/scope filters and have compatible provenance.
    """
    # Fetch all non-expired rows with embeddings and provenance
    if not include_expired:
        expire_filter = "(d.expires_at IS NULL OR d.expires_at > datetime('now'))"
    else:
        expire_filter = "1=1"

    # We need rows with embeddings AND compatible provenance.
    # Compatible = same provider + model + dim, OR NULL provenance (legacy rows).
    q_provider = query_embedding.provider
    q_model = query_embedding.model
    q_dim = query_embedding.dim

    rows = conn.execute(
        f"""
        SELECT d.id, d.timestamp, d.category, d.context, d.decision,
               d.rationale, d.source, d.kind, d.scope, d.confidence,
               d.tags, d.expires_at, d.pinned,
               d.embedding,
               d.embedding_provider, d.embedding_model, d.embedding_dim,
               p.name AS project_name, p.path AS project_path,
               NULL AS _fts_rank
        FROM decisions d
        LEFT JOIN projects p ON p.id = d.project_id
        WHERE d.embedding IS NOT NULL
          AND {expire_filter}
          AND {scope_filter}
          AND (
              d.embedding_provider IS NULL
              OR (d.embedding_provider = ?
                    AND d.embedding_model = ?
                    AND d.embedding_dim = ?)
          )
        LIMIT ?
        """,
        (*scope_params, q_provider, q_model, q_dim, max(limit * 10, 200)),
    ).fetchall()

    # Post-filter expired (belt-and-suspenders)
    if not include_expired:
        now_str = datetime.now(timezone.utc).isoformat()
        rows = [r for r in rows if not r["expires_at"] or r["expires_at"] > now_str]

    return rows


def recall_ranked(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    project_path: str | None = None,
    limit: int = 10,
    weights: RankWeights | None = None,
    include_expired: bool = False,
    query_embedding: EmbeddingResult | bytes | None = None,
) -> list[dict[str, Any]]:
    """Ranked recall using FTS5 + heuristic scoring (+ optional embeddings).

    If query is empty, falls back to recency + metadata scoring (no FTS).
    If query_embedding is provided and weights.embedding > 0, cosine similarity
    is blended into the score (hybrid recall).

    C3: When embeddings are enabled and weighted, performs candidate widening:
    lexical candidates UNION embedding candidates → final ranking.
    """
    if weights is None:
        weights = default_rank_weights()

    limit = max(1, min(int(limit), 100))

    # Normalize query_embedding: if it's legacy bytes, wrap it
    if isinstance(query_embedding, bytes):
        from .embeddings import HASH_PROVIDER, HASH_MODEL, HASH_VERSION, EMBED_DIM
        query_embedding = EmbeddingResult(
            vector=query_embedding,
            provider=HASH_PROVIDER,
            model=HASH_MODEL,
            dim=EMBED_DIM,
            version=HASH_VERSION,
        )

    # Build project-scoped filtering SQL fragment.
    if project_path:
        scope_filter = (
            "(d.scope IS NULL OR d.scope = 'global' "
            " OR (d.scope = 'project' AND p.path = ?))"
        )
        scope_params: tuple = (project_path,)
    else:
        scope_filter = "(d.scope IS NULL OR d.scope = 'global' OR d.scope != 'project')"
        scope_params = ()

    embedding_select = ", d.embedding AS embedding"
    prov_select = (
        ", d.embedding_provider, d.embedding_model, d.embedding_dim"
    )

    # Determine if we should do embedding candidate widening
    do_embedding_widening = (
        query_embedding is not None
        and weights.embedding > 0
        and isinstance(query_embedding, EmbeddingResult)
    )

    lexical_rows: list[sqlite3.Row] = []

    if query.strip():
        fts_query = _escape_fts5_query(query)
        if not fts_query:
            return []
        # FTS5 search: join decisions with fts table for BM25 rank
        lexical_rows = conn.execute(
            f"""
            SELECT d.id, d.timestamp, d.category, d.context, d.decision,
                   d.rationale, d.source, d.kind, d.scope, d.confidence,
                   d.tags, d.expires_at, d.pinned,
                   p.name AS project_name, p.path AS project_path,
                   fts.rank AS _fts_rank{embedding_select}{prov_select}
            FROM decisions_fts fts
            JOIN decisions d ON d.id = fts.rowid
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE decisions_fts MATCH ?
              AND {scope_filter}
            ORDER BY fts.rank
            LIMIT ?
            """,
            (fts_query, *scope_params, limit * 3),
        ).fetchall()
    else:
        # No query: return recent decisions, scored by metadata only
        if not include_expired:
            expire_filter = "(d.expires_at IS NULL OR d.expires_at > datetime('now'))"
        else:
            expire_filter = "1=1"

        lexical_rows = conn.execute(
            f"""
            SELECT d.id, d.timestamp, d.category, d.context, d.decision,
                   d.rationale, d.source, d.kind, d.scope, d.confidence,
                   d.tags, d.expires_at, d.pinned,
                   p.name AS project_name, p.path AS project_path,
                   NULL AS _fts_rank{embedding_select}{prov_select}
            FROM decisions d
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE {expire_filter}
              AND {scope_filter}
            ORDER BY d.timestamp DESC, d.id DESC
            LIMIT ?
            """,
            (*scope_params, limit * 3),
        ).fetchall()

    # Filter expired from lexical rows
    if not include_expired:
        now_str = datetime.now(timezone.utc).isoformat()
        lexical_rows = [
            r for r in lexical_rows
            if not r["expires_at"] or r["expires_at"] > now_str
        ]

    # C3: Semantic candidate widening
    embedding_rows: list[sqlite3.Row] = []
    if do_embedding_widening:
        embedding_rows = _embedding_widening_candidates(
            conn,
            query_embedding=query_embedding,  # type: ignore[arg-type]
            project_path=project_path,
            scope_filter=scope_filter,
            scope_params=scope_params,
            limit=limit,
            include_expired=include_expired,
        )

    # Merge: lexical UNION embedding, deduplicated by id
    seen_ids: set[int] = set()
    merged: list[dict[str, Any]] = []
    for r in list(lexical_rows) + list(embedding_rows):
        rid = r["id"]
        if rid not in seen_ids:
            seen_ids.add(rid)
            merged.append(dict(r))

    # Apply ranking (with optional embedding scoring)
    ranked = rank_memories(
        merged,
        current_project_path=project_path,
        weights=weights,
        query_embedding=query_embedding,
    )

    # Deduplicate near-identical decisions
    ranked = _dedup_memories(ranked)

    return ranked[:limit]
