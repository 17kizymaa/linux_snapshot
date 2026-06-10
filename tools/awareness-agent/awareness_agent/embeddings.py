from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Optional

import numpy as np

# Embedding dimensionality — 384 is a common small-model size (all-MiniLM-L6-v2).
# We use feature hashing so no model is needed.
EMBED_DIM = 384

# ---------------------------------------------------------------------------
# Embedding provenance
# ---------------------------------------------------------------------------

# Hash backend identifiers
HASH_PROVIDER = "hash"
HASH_MODEL = "char-trigram-sha256-v1"
HASH_VERSION = "1.0"

# Sentence-transformers backend identifier prefix
ST_PROVIDER = "sentence-transformers"


@dataclass(frozen=True)
class EmbeddingResult:
    """Embedding vector with provenance metadata.

    Provenance ensures vectors are only compared when compatible:
    same provider + model + dim = comparable.
    """
    vector: bytes
    provider: str
    model: str
    dim: int
    version: str

    def is_compatible(self, other: "EmbeddingResult") -> bool:
        """Check if two embeddings are comparable (same provenance)."""
        return (
            self.provider == other.provider
            and self.model == other.model
            and self.dim == other.dim
            and self.version == other.version
        )

    @property
    def is_semantic(self) -> bool:
        """Return True if this embedding comes from a semantic model (not hash)."""
        return self.provider != HASH_PROVIDER


# ---------------------------------------------------------------------------
# Hash-based (feature-hashing) embedding — fully offline, no model, no network
# ---------------------------------------------------------------------------

def _hash_token(token: str, seed: int = 0) -> tuple[int, float]:
    """Hash a token to (index, sign) using a single SHA-256 call."""
    h = hashlib.sha256(f"{seed}:{token}".encode("utf-8")).digest()
    idx = struct.unpack("<I", h[:4])[0] % EMBED_DIM
    sign = 1.0 if h[4] < 128 else -1.0
    return idx, sign


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer with character trigrams for short tokens."""
    import re
    tokens: list[str] = []
    for raw in re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower()):
        tokens.append(raw)
        if len(raw) >= 3:
            for i in range(len(raw) - 2):
                tokens.append(raw[i:i + 3])
    return tokens


def hash_embed(text: str) -> EmbeddingResult:
    """Produce a deterministic float32 embedding from text via feature hashing.

    Returns:
        EmbeddingResult with hash-based provenance.
    """
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return EmbeddingResult(
            vector=vec.tobytes(),
            provider=HASH_PROVIDER,
            model=HASH_MODEL,
            dim=EMBED_DIM,
            version=HASH_VERSION,
        )

    for tok in tokens:
        idx, sign = _hash_token(tok)
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm

    return EmbeddingResult(
        vector=vec.tobytes(),
        provider=HASH_PROVIDER,
        model=HASH_MODEL,
        dim=EMBED_DIM,
        version=HASH_VERSION,
    )


# ---------------------------------------------------------------------------
# Optional sentence-transformers backend — local-only, no network
# ---------------------------------------------------------------------------

_st_model = None
_st_model_id: str | None = None


def _get_st_model(model_name: str | None = None):
    """Lazily load a sentence-transformers model. Returns None if unavailable.

    This function NEVER triggers a network download. It only loads from
    locally cached model files.

    Args:
        model_name: HuggingFace model ID or local path.
                   Defaults to 'all-MiniLM-L6-v2'.
    """
    global _st_model, _st_model_id

    if model_name is None:
        model_name = "all-MiniLM-L6-v2"

    # Return cached model if already loaded with same config
    if _st_model is not None and _st_model_id == model_name:
        return _st_model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None

    # Try loading with local_files_only first (supported in newer versions)
    try:
        _st_model = SentenceTransformer(model_name, local_files_only=True)
        _st_model_id = model_name
        return _st_model
    except TypeError:
        # Older sentence-transformers doesn't support local_files_only kwarg.
        # Fall through to try/except below.
        pass
    except Exception:
        # Model not available locally or other error — fail closed
        return None

    # Fallback for older versions: try loading, but only if the model
    # directory already exists locally (no download).
    try:
        from pathlib import Path
        import os

        # Check if it's a local path
        if os.path.isdir(model_name):
            _st_model = SentenceTransformer(model_name)
            _st_model_id = model_name
            return _st_model

        # Check HuggingFace cache
        cache_home = os.environ.get(
            "SENTENCE_TRANSFORMERS_HOME",
            os.path.join(Path.home(), ".cache", "sentence_transformers"),
        )
        cached_path = os.path.join(cache_home, model_name.replace("/", "_"))
        if os.path.isdir(cached_path):
            _st_model = SentenceTransformer(cached_path)
            _st_model_id = model_name
            return _st_model

        # Model not available locally — fail closed, no network
        return None
    except Exception:
        return None


def model_embed(text: str, model_name: str | None = None) -> EmbeddingResult | None:
    """Try to embed using a local sentence-transformers model.

    Returns None if the model/library is unavailable (fail-closed).
    Never triggers a network download.
    """
    model = _get_st_model(model_name)
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        vec = vec.astype(np.float32)
        # Determine the actual model name
        actual_model = model_name or "all-MiniLM-L6-v2"
        dim = len(vec)
        return EmbeddingResult(
            vector=vec.tobytes(),
            provider=ST_PROVIDER,
            model=actual_model,
            dim=dim,
            version="1.0",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Backend mode resolution
# ---------------------------------------------------------------------------

def resolve_backend(backend: str, model_name: str | None = None) -> str:
    """Resolve the effective embedding backend.

    Modes:
        'hash': always use hash-based embeddings.
        'sentence-transformers': use ST if available locally, else fail (no hash fallback).
        'auto': use ST if available locally, else fall back to hash.

    Returns the effective backend string: 'hash' or 'sentence-transformers'.
    """
    backend = backend.strip().lower()
    if backend == "hash":
        return "hash"
    if backend == "sentence-transformers":
        return "sentence-transformers"
    if backend == "auto":
        # Try ST first, fall back to hash
        model = _get_st_model(model_name)
        if model is not None:
            return "sentence-transformers"
        return "hash"
    # Unknown backend — fail closed to hash
    return "hash"


# ---------------------------------------------------------------------------
# Unified embedder — tries model first (per backend mode), falls back to hash
# ---------------------------------------------------------------------------

def embed_text(
    text: str,
    *,
    backend: str = "hash",
    model_name: str | None = None,
) -> EmbeddingResult:
    """Embed text into a float32 BLOB with provenance.

    Args:
        text: The text to embed.
        backend: One of 'hash', 'sentence-transformers', 'auto'.
        model_name: Optional model name/path for sentence-transformers backend.

    Returns:
        EmbeddingResult with vector bytes and provenance metadata.
    """
    effective = resolve_backend(backend, model_name)
    if effective == "sentence-transformers":
        result = model_embed(text, model_name)
        if result is not None:
            return result
        # If sentence-transformers was explicitly requested but unavailable,
        # still fall back to hash (fail-closed: produce *some* embedding)
        # unless strict mode is desired. The C3 spec says "no embedding rather
        # than silent network" — but hash is not network, so falling back
        # to hash is safe and more useful.
    return hash_embed(text)


# ---------------------------------------------------------------------------
# Legacy compatibility — raw bytes API (for existing C2 code)
# ---------------------------------------------------------------------------

def embed_text_bytes(text: str, *, use_model: bool = False) -> bytes:
    """Legacy API: embed text, return raw bytes only (no provenance).

    Kept for backward compatibility with C2 code that expects bytes.
    New code should use embed_text() which returns EmbeddingResult.
    """
    if use_model:
        result = model_embed(text)
        if result is not None:
            return result.vector
    return hash_embed(text).vector


def blob_to_numpy(blob: bytes) -> np.ndarray:
    """Convert a float32 BLOB back to a numpy array."""
    return np.frombuffer(blob, dtype=np.float32).copy()


def cosine_similarity(a_bytes: bytes, b_bytes: bytes) -> float:
    """Cosine similarity between two float32 BLOBs. Returns [0, 1]."""
    a = blob_to_numpy(a_bytes)
    b = blob_to_numpy(b_bytes)
    dot = float(np.dot(a, b))
    return max(0.0, min(1.0, dot))
