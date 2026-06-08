from __future__ import annotations

import hashlib
import math
import struct
from typing import Optional

import numpy as np

# Embedding dimensionality — 384 is a common small-model size (all-MiniLM-L6-v2).
# We use feature hashing so no model is needed.
EMBED_DIM = 384

# ---------------------------------------------------------------------------
# Hash-based (feature-hashing) embedding — fully offline, no model, no network
# ---------------------------------------------------------------------------

def _hash_token(token: str, seed: int = 0) -> tuple[int, float]:
    """Hash a token to (index, sign) using a single SHA-256 call."""
    h = hashlib.sha256(f"{seed}:{token}".encode("utf-8")).digest()
    # First 4 bytes → index, 5th byte → sign
    idx = struct.unpack("<I", h[:4])[0] % EMBED_DIM
    sign = 1.0 if h[4] < 128 else -1.0
    return idx, sign


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer with character trigrams for short tokens."""
    import re
    tokens: list[str] = []
    for raw in re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower()):
        tokens.append(raw)
        # Add character trigrams for sub-word matching
        if len(raw) >= 3:
            for i in range(len(raw) - 2):
                tokens.append(raw[i:i + 3])
    return tokens


def hash_embed(text: str) -> bytes:
    """Produce a deterministic float32 embedding from text via feature hashing.

    Returns:
        bytes — EMBED_DIM float32 values (little-endian), suitable for BLOB storage.
    """
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec.tobytes()

    for tok in tokens:
        idx, sign = _hash_token(tok)
        vec[idx] += sign

    # L2-normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm

    return vec.tobytes()


# ---------------------------------------------------------------------------
# Optional sentence-transformers backend
# ---------------------------------------------------------------------------

_st_model = None


def _get_st_model():
    """Lazily load a sentence-transformers model. Returns None if unavailable."""
    global _st_model
    if _st_model is not None:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: ~80MB, 384-dim, fast on CPU
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        return _st_model
    except Exception:
        return None


def model_embed(text: str) -> Optional[bytes]:
    """Try to embed using a local sentence-transformers model.

    Returns None if the model/library is unavailable (fail-closed).
    """
    model = _get_st_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.astype(np.float32).tobytes()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Unified embedder — tries model first, falls back to hash
# ---------------------------------------------------------------------------

def embed_text(text: str, *, use_model: bool = False) -> bytes:
    """Embed text into a float32 BLOB.

    Args:
        text: The text to embed.
        use_model: If True, try sentence-transformers first.
                   Always falls back to hash_embed if model unavailable.

    Returns:
        bytes — EMBED_DIM float32 values.
    """
    if use_model:
        result = model_embed(text)
        if result is not None:
            return result
    return hash_embed(text)


def blob_to_numpy(blob: bytes) -> np.ndarray:
    """Convert a float32 BLOB back to a numpy array."""
    return np.frombuffer(blob, dtype=np.float32).copy()


def cosine_similarity(a_bytes: bytes, b_bytes: bytes) -> float:
    """Cosine similarity between two float32 BLOBs. Returns [0, 1]."""
    a = blob_to_numpy(a_bytes)
    b = blob_to_numpy(b_bytes)
    dot = float(np.dot(a, b))
    # Clamp to [0, 1] — negative similarity treated as 0
    return max(0.0, min(1.0, dot))
