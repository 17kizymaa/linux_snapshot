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
    migrate_fts5,
    migrate_taxonomy,
    recall_ranked,
)
from .redaction import redact_text

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

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO decisions(project_id, category, context, decision, rationale, source, kind)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    parsed_category,
                    redact_text(context),
                    decision,
                    redact_text(rationale),
                    redact_text(source) or "user",
                    kind,
                ),
            )
        self._secure_files()
        return int(cur.lastrowid)

    def recall(
        self,
        query: str = "",
        limit: int = 10,
        *,
        project_path: str | None = None,
        weights: RankWeights | None = None,
    ) -> list[dict[str, Any]]:
        """Ranked recall using FTS5 + heuristic scoring.

        Falls back to recency + metadata scoring when query is empty.
        Results include '_score' and '_score_breakdown' when ranked.
        """
        return recall_ranked(
            self.conn,
            query,
            project_path=project_path or self._current_project_path(),
            limit=limit,
            weights=weights,
        )

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
