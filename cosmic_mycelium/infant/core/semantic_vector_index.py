"""
Semantic Vector Index — FAISS-based similarity search for feature codes.

Provides fast (<10ms for 10k vectors) nearest-neighbor search using FAISS.
Falls back to numpy brute-force if FAISS unavailable (but FAISS is a core dependency).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class SemanticVectorIndex:
    """
    Vector index for semantic similarity search over feature code embeddings.

    Uses FAISS IndexFlatIP (inner product) for cosine similarity after L2 normalization.
    Maintains a mapping from FAISS row IDs to feature_code IDs.
    """

    def __init__(self, dim: int, index_path: str | Path | None = None):
        """
        Initialize vector index.

        Args:
            dim: Embedding dimension
            index_path: Optional path to load persisted index from
        """
        self.dim = dim
        self.id_map: list[str] = []  # row_index → feature_code_id
        self._lock = RLock()  # Sprint 5: thread-safe concurrent access

        if FAISS_AVAILABLE:
            # Inner product on L2-normalized vectors = cosine similarity
            self.index = faiss.IndexFlatIP(dim)
        else:
            self.index = None  # Will fall back to numpy

        if index_path and Path(index_path).exists():
            self.load(index_path)

    def add(self, feature_code_id: str, vector: np.ndarray) -> None:
        """
        Add a vector to the index.

        Args:
            feature_code_id: Unique identifier for the feature code
            vector: Embedding vector (will be normalized if not already)
        """
        vec = vector.astype(np.float32).reshape(1, -1)
        # Normalize for cosine similarity
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        with self._lock:
            if FAISS_AVAILABLE and self.index is not None:
                self.index.add(vec)
            else:
                # Numpy fallback: store flattened vector for dot product
                if not hasattr(self, "_fallback_vectors"):
                    self._fallback_vectors = []
                self._fallback_vectors.append((feature_code_id, vec.ravel()))

            self.id_map.append(feature_code_id)

    def search(self, query_vector: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """
        Search for the k most similar vectors.

        Args:
            query_vector: Query embedding (will be normalized)
            k: Number of nearest neighbors to return

        Returns:
            List of (feature_code_id, similarity_score) sorted by score descending
        """
        if k <= 0:
            return []

        q = query_vector.astype(np.float32).reshape(1, -1)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        with self._lock:
            # Fallback mode
            if not FAISS_AVAILABLE or self.index is None or not hasattr(self, "index"):
                results = []
                for fid, vec in getattr(self, "_fallback_vectors", []):
                    sim = float(np.dot(q, vec).squeeze())
                    results.append((fid, sim))
                results.sort(key=lambda x: -x[1])
                return results[:k]

            # FAISS search
            k_actual = min(k, len(self.id_map))
            if k_actual == 0:
                return []

            distances, indices = self.index.search(q, k_actual)
            results = []
            for dist, idx in zip(distances[0], indices[0], strict=True):
                if idx < len(self.id_map) and idx >= 0:
                    results.append((self.id_map[idx], float(dist)))
            return results

    def save(self, path: str | Path) -> None:
        """
        Persist index and id_map to disk.

        Args:
            path: Directory path where index files will be written
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        if FAISS_AVAILABLE and self.index is not None:
            index_file = path / "index.faiss"
            faiss.write_index(self.index, str(index_file))

        id_map_file = path / "id_map.pkl"
        with id_map_file.open("wb") as f:
            pickle.dump(self.id_map, f)

    def load(self, path: str | Path) -> None:
        """
        Load index and id_map from disk.

        Args:
            path: Directory path containing index.faiss and id_map.pkl
        """
        path = Path(path)
        index_file = path / "index.faiss"
        id_map_file = path / "id_map.pkl"

        if index_file.exists():
            if FAISS_AVAILABLE:
                self.index = faiss.read_index(str(index_file))
            else:
                self.index = None
        else:
            self.index = None

        if id_map_file.exists():
            with id_map_file.open("rb") as f:
                self.id_map = pickle.load(f)

    def __len__(self) -> int:
        return len(self.id_map)

    def clear(self) -> None:
        """Remove all vectors from the index."""
        if FAISS_AVAILABLE and self.index is not None:
            self.index.reset()
        self.id_map.clear()
        if hasattr(self, "_fallback_vectors"):
            self._fallback_vectors.clear()
