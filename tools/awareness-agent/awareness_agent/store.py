from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .paths import db_path, ensure_dirs, secure_chmod
from .ranking import (
    RankWeights,
    category_to_kind,
    compute_expires_at,
    detect_scope,
    migrate_fts5,
    migrate_kind_ttls,
    migrate_taxonomy,
    recall_ranked,
)
from .redaction import redact_text

# Global config: embeddings enabled flag (default off to keep baseline green)
_EMBEDDINGS_ENABLED = False

# Global config: embedding backend mode (default: hash)
_EMBEDDING_BACKEND = "hash"

# Global config: sentence-transformers model name/path (default local cached model)
_EMBEDDING_MODEL: str | None = "all-MiniLM-L6-v2"


def set_embeddings_enabled(enabled: bool) -> None:
    """Enable or disable embedding computation at remember() time.

    When enabled, embeddings are computed for every remembered text and
    stored in the embedding BLOB column. When disabled (default), no
    embedding is computed or stored — pure C1 FTS5 behavior.
    """
    global _EMBEDDINGS_ENABLED
    _EMBEDDINGS_ENABLED = bool(enabled)


def embeddings_enabled() -> bool:
    """Return whether embeddings are currently enabled."""
    return _EMBEDDINGS_ENABLED


def set_embedding_backend(backend: str) -> None:
    """Set the embedding backend mode.

    Args:
        backend: One of 'hash', 'sentence-transformers', 'auto'.
    """
    global _EMBEDDING_BACKEND
    _EMBEDDING_BACKEND = backend


def embedding_backend() -> str:
    """Return the current embedding backend mode."""
    return _EMBEDDING_BACKEND


def set_embedding_model(model_name: str | None) -> None:
    """Set the optional sentence-transformers model name or local path."""
    global _EMBEDDING_MODEL
    _EMBEDDING_MODEL = model_name


def embedding_model() -> str | None:
    """Return the current sentence-transformers model name or local path."""
    return _EMBEDDING_MODEL


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT,
    language TEXT,
    framework TEXT,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    summary TEXT,
    commands_run INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    category TEXT NOT NULL DEFAULT 'note',
    context TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    scope TEXT NOT NULL DEFAULT 'global',
    source TEXT NOT NULL DEFAULT 'user',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(path);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_category ON decisions(category);
CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key);
"""


class AwarenessStore:
    def __init__(self, path: str | Path | None = None) -> None:
        ensure_dirs()
        self.path = Path(path) if path else db_path()
        self.conn = sqlite3.connect(str(self.path), timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()
        self._secure_files()

    def __enter__(self) -> "AwarenessStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._secure_files()
        self.conn.close()

    def _secure_files(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            secure_chmod(Path(str(self.path) + suffix), 0o600)

    def _migrate(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)
        migrate_taxonomy(self.conn)
        migrate_fts5(self.conn)
        migrate_kind_ttls(self.conn)

    def upsert_project(self, project: dict[str, Any]) -> int:
        path = project.get("root") or project.get("path")
        if not path:
            raise ValueError("project requires root or path")

        name = project.get("name") or Path(str(path)).name
        metadata = json.dumps(project, sort_keys=True)

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO projects(path, name, language, framework, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    name=excluded.name,
                    language=excluded.language,
                    framework=excluded.framework,
                    metadata=excluded.metadata,
                    last_active=CURRENT_TIMESTAMP
                """,
                (
                    str(path),
                    str(name),
                    project.get("language"),
                    project.get("framework"),
                    metadata,
                ),
            )
        self._secure_files()

        row = self.conn.execute("SELECT id FROM projects WHERE path = ?", (str(path),)).fetchone()
        if row is None:
            raise RuntimeError("failed to upsert project")
        return int(row["id"])

    def remember(
        self,
        text: str,
        *,
        category: str = "note",
        context: str = "",
        rationale: str = "",
        source: str = "user",
        project: dict[str, Any] | None = None,
    ) -> int:
        clean = redact_text(text).strip()
        if not clean:
            raise ValueError("cannot remember empty text")

        parsed_category = redact_text(category or "note").strip().lower()[:64] or "note"
        decision = clean

        if parsed_category == "note" and ":" in clean:
            prefix, rest = clean.split(":", 1)
            normalized = prefix.strip().lower().replace(" ", "_")
            if (
                1 <= len(normalized) <= 32
                and all(ch.isalnum() or ch in "_-" for ch in normalized)
                and rest.strip()
            ):
                parsed_category = normalized
                decision = rest.strip()

        project_id = self.upsert_project(project) if project else None
        kind = category_to_kind(parsed_category)
        expires_at = compute_expires_at(self.conn, kind)

        # Gather known project paths for scope detection
        known_paths = [
            row[0] for row in self.conn.execute("SELECT path FROM projects").fetchall()
        ]
        scope = detect_scope(
            kind=kind,
            context=context,
            decision=decision,
            project_id=project_id,
            known_project_paths=known_paths,
        )

        # Compute embedding if enabled
        embedding_result = None
        if _EMBEDDINGS_ENABLED:
            try:
                from .embeddings import embed_text
                embedding_text = f"{decision} {redact_text(rationale)} {redact_text(context)}".strip()
                embedding_result = embed_text(embedding_text, backend=_EMBEDDING_BACKEND, model_name=_EMBEDDING_MODEL)
            except Exception:
                embedding_result = None  # fail-closed: no embedding, no error

        with self.conn:
            if embedding_result is not None:
                cur = self.conn.execute(
                    """
                    INSERT INTO decisions(project_id, category, context, decision, rationale, source, kind, expires_at, scope, embedding, embedding_provider, embedding_model, embedding_dim, embedding_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        parsed_category,
                        redact_text(context),
                        decision,
                        redact_text(rationale),
                        redact_text(source) or "user",
                        kind,
                        expires_at,
                        scope,
                        embedding_result.vector,
                        embedding_result.provider,
                        embedding_result.model,
                        embedding_result.dim,
                        embedding_result.version,
                    ),
                )
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO decisions(project_id, category, context, decision, rationale, source, kind, expires_at, scope)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        parsed_category,
                        redact_text(context),
                        decision,
                        redact_text(rationale),
                        redact_text(source) or "user",
                        kind,
                        expires_at,
                        scope,
                    ),
                )
        self._secure_files()
        return int(cur.lastrowid)

    def recall(
        self,
        query: str = "",
        limit: int = 10,
        *,
        project_path: str | None | type(...) = ...,
        weights: RankWeights | None = None,
    ) -> list[dict[str, Any]]:
        """Ranked recall using FTS5 + heuristic scoring (+ optional embeddings).

        Falls back to recency + metadata scoring when query is empty.
        Results include '_score' and '_score_breakdown' when ranked.

        If embeddings are enabled (set_embeddings_enabled(True)), a query
        embedding is computed and passed to recall_ranked for hybrid scoring
        with candidate widening.
        """
        if project_path is ...:
            project_path = self._current_project_path()

        # Compute query embedding if enabled and query is non-empty
        query_embedding = None
        if _EMBEDDINGS_ENABLED and query.strip():
            try:
                from .embeddings import embed_text
                query_embedding = embed_text(query, backend=_EMBEDDING_BACKEND, model_name=_EMBEDDING_MODEL)
            except Exception:
                query_embedding = None  # fail-closed

        return recall_ranked(
            self.conn,
            query,
            project_path=project_path,
            limit=limit,
            weights=weights,
            query_embedding=query_embedding,
        )

    def backfill_embeddings(
        self,
        *,
        force: bool = False,
        limit: int | None = None,
    ) -> dict[str, int]:
        """Compute and store embeddings for existing memories that lack them.

        Args:
            force: If True, recompute embeddings even if already present.
            limit: Maximum number of rows to process. None = all.

        Returns:
            Dict with counts: scanned, updated, skipped_existing,
            skipped_expired, skipped_incompatible, failed.
        """
        from .embeddings import embed_text, HASH_PROVIDER

        now_str = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()

        # Find rows needing embeddings
        if force:
            where = "WHERE 1=1"
        else:
            where = "WHERE embedding IS NULL OR embedding_provider IS NULL"

        # Exclude expired rows
        where += " AND (expires_at IS NULL OR expires_at > ?)"

        # Get the current backend's provenance so we don't overwrite
        # higher-quality vectors with lower-quality ones
        current_backend = _EMBEDDING_BACKEND
        try:
            from .embeddings import resolve_backend
            effective_backend = resolve_backend(current_backend, _EMBEDDING_MODEL)
        except Exception:
            effective_backend = "hash"

        # Determine what provider the current backend produces
        if effective_backend == "sentence-transformers":
            # We'd be producing sentence-transformers vectors — don't overwrite
            # existing sentence-transformers vectors with hash
            skip_if_provider = HASH_PROVIDER
        else:
            # We're producing hash vectors — don't overwrite any existing
            # sentence-transformers vectors (higher quality)
            skip_if_provider = "sentence-transformers"

        query = f"SELECT id, decision, rationale, context, embedding_provider FROM decisions {where} ORDER BY id"
        params: list = [now_str]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        rows = self.conn.execute(query, params).fetchall()

        counts = {
            "scanned": 0,
            "updated": 0,
            "skipped_existing": 0,
            "skipped_expired": 0,
            "skipped_incompatible": 0,
            "failed": 0,
        }

        for row in rows:
            counts["scanned"] += 1
            rid = row["id"]
            existing_provider = row["embedding_provider"]

            # Skip if already has a compatible embedding (not forcing)
            if not force and existing_provider is not None:
                counts["skipped_existing"] += 1
                continue

            # Skip if existing provider is higher quality than what we'd produce
            if (force and existing_provider is not None
                    and existing_provider == "sentence-transformers"
                    and skip_if_provider == "sentence-transformers"):
                # Don't overwrite ST vectors with hash
                counts["skipped_incompatible"] += 1
                continue

            try:
                text = f"{row['decision']} {row['rationale']} {row['context']}".strip()
                emb = embed_text(text, backend=current_backend, model_name=_EMBEDDING_MODEL)
                self.conn.execute(
                    """
                    UPDATE decisions
                    SET embedding = ?,
                        embedding_provider = ?,
                        embedding_model = ?,
                        embedding_dim = ?,
                        embedding_version = ?
                    WHERE id = ?
                    """,
                    (
                        emb.vector,
                        emb.provider,
                        emb.model,
                        emb.dim,
                        emb.version,
                        rid,
                    ),
                )
                counts["updated"] += 1
            except Exception:
                counts["failed"] += 1

        self.conn.commit()
        self._secure_files()
        return counts

    def sweep(self) -> int:
        """Hard-delete expired rows. Returns the number of rows removed.

        Safe to call at any time. Recall already filters expired rows
        lazily, so sweep is optional cleanup, not required for correctness.
        """
        with self.conn:
            cur = self.conn.execute(
                """
                DELETE FROM decisions
                WHERE expires_at IS NOT NULL
                  AND expires_at <= datetime('now')
                """
            )
        self._secure_files()
        return cur.rowcount

    def _current_project_path(self) -> str | None:
        """Best-effort current project path from the most recently active project."""
        row = self.conn.execute(
            "SELECT path FROM projects ORDER BY last_active DESC LIMIT 1"
        ).fetchone()
        return row["path"] if row else None

    def status(self) -> dict[str, Any]:
        projects = self.conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
        decisions = self.conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
        sessions = self.conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
        last_decision = self.conn.execute(
            """
            SELECT id, timestamp, category, decision
            FROM decisions
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

        return {
            "db_path": str(self.path),
            "counts": {
                "projects": int(projects),
                "sessions": int(sessions),
                "decisions": int(decisions),
            },
            "last_decision": dict(last_decision) if last_decision else None,
        }
