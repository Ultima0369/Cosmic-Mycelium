"""
Embedding Utilities — deterministic text → vector conversion.

Uses SHA256 hash of the text, truncated and normalized to [0,1].
This provides a deterministic, reproducible embedding in a fixed-dimensional space.
Suitable for semantic caching and feature code indexing where full LLM embeddings
are unnecessary overhead.

Note: For production semantic search, consider upgrading to sentence-transformers.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np


def text_to_embedding(text: str, dim: int = 16) -> np.ndarray:
    """
    Convert text to a fixed-dimensional embedding vector.

    Algorithm:
    1. SHA256 hash the UTF-8 encoded text (32 bytes)
    2. Truncate or cycle to reach `dim` entries
    3. Normalize bytes to float32 in [0, 1] by dividing by 255

    This is deterministic: same text → same vector every time.
    Similar texts share prefix of hash → some similarity preserved.

    Args:
        text: Input string
        dim: Desired embedding dimension (default 16, matches SemanticMapper default)

    Returns:
        np.ndarray of shape (dim,) with dtype float32, values in [0, 1]
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Convert bytes to array of floats
    arr = np.frombuffer(h[:dim], dtype=np.uint8).astype(np.float32)
    arr = arr / 255.0
    return arr


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")
    na = a / (np.linalg.norm(a) + 1e-8)
    nb = b / (np.linalg.norm(b) + 1e-8)
    return float(np.dot(na, nb))
