from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import __version__
from .git_provider import collect_project
from .paths import db_path, socket_path
from .redaction import redact_text
from .store import AwarenessStore


def _cwd(params: dict[str, Any]) -> str:
    cwd = params.get("cwd")
    return str(Path(cwd).expanduser()) if cwd else os.getcwd()


def handle_request(method: str, params: dict[str, Any] | None = None) -> Any:
    params = params or {}

    with AwarenessStore() as store:
        if method == "health":
            return {
                "ok": True,
                "version": __version__,
                "db_path": str(db_path()),
                "socket_path": str(socket_path()),
            }

        if method in {"status", "context.status"}:
            project = collect_project(_cwd(params))
            store.upsert_project(project)
            result = store.status()
            result.update(
                {
                    "ok": True,
                    "version": __version__,
                    "socket_path": str(socket_path()),
                    "current_project": project,
                }
            )
            return result

        if method in {"context.project", "project.context"}:
            project = collect_project(_cwd(params))
            store.upsert_project(project)
            return project

        if method == "memory.remember":
            text = params.get("text")
            if not text:
                raise ValueError("memory.remember requires params.text")

            project = collect_project(_cwd(params))
            memory_id = store.remember(
                str(text),
                category=str(params.get("category") or "note"),
                context=str(params.get("context") or f"cwd={_cwd(params)}"),
                rationale=str(params.get("rationale") or ""),
                source=str(params.get("source") or "user"),
                project=project,
            )

            return {
                "stored": True,
                "id": memory_id,
                "project": project.get("name"),
                "redacted": redact_text(text) != str(text),
            }

        if method == "memory.recall":
            query = str(params.get("query") or "")
            limit = int(params.get("limit") or 10)
            return {
                "query": query,
                "items": store.recall(query, limit),
            }

    raise ValueError(f"unknown method: {method}")
