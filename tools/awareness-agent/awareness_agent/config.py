from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

from .paths import config_path, write_default_config
from .ranking import RankWeights, set_default_rank_weights
from .store import set_embedding_backend, set_embedding_model, set_embeddings_enabled


DEFAULT_CONFIG: dict[str, Any] = {
    "daemon": {"socket": "auto"},
    "embedding": {
        "enabled": False,
        "backend": "hash",
        "model": "all-MiniLM-L6-v2",
    },
    "ranking": {
        "weights": {
            "fts_bm25": 1.0,
            "recency": 0.3,
            "project_match": 0.4,
            "pinned_boost": 0.5,
            "error_boost": 0.2,
            "source_boost": 0.1,
            "embedding": 0.0,
            "embedding_threshold": 0.3,
            "recency_half_life_days": 30.0,
        }
    },
    "retention": {
        "sessions_days": 30,
        "commands_days": 7,
        "model_telemetry_hours": 24,
    },
}


def _merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_runtime_config() -> dict[str, Any]:
    path: Path = config_path()
    if not path.exists():
        write_default_config()

    raw = path.read_text(encoding="utf-8")
    loaded = tomllib.loads(raw)
    return _merge(DEFAULT_CONFIG, loaded)


def build_rank_weights(config: dict[str, Any] | None = None) -> RankWeights:
    config = config or load_runtime_config()
    weights = config.get("ranking", {}).get("weights", {})
    return RankWeights(
        fts_bm25=float(weights.get("fts_bm25", 1.0)),
        recency=float(weights.get("recency", 0.3)),
        project_match=float(weights.get("project_match", 0.4)),
        pinned_boost=float(weights.get("pinned_boost", 0.5)),
        error_boost=float(weights.get("error_boost", 0.2)),
        source_boost=float(weights.get("source_boost", 0.1)),
        embedding=float(weights.get("embedding", 0.0)),
        embedding_threshold=float(weights.get("embedding_threshold", 0.3)),
        recency_half_life_days=float(weights.get("recency_half_life_days", 30.0)),
    )


def apply_runtime_config() -> None:
    config = load_runtime_config()
    embedding = config.get("embedding", {})
    set_embeddings_enabled(bool(embedding.get("enabled", False)))
    set_embedding_backend(str(embedding.get("backend", "hash")))
    set_embedding_model(str(embedding.get("model", "all-MiniLM-L6-v2")))
    set_default_rank_weights(build_rank_weights(config))
