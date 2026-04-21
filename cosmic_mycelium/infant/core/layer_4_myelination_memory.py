"""
Layer 4 — Myelination Memory (Myelination Layer)
Hebbian learning, path reinforcement, forgetting curve, long-term memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque
import time
import hashlib
import json


@dataclass
class MemoryTrace:
    """A memory trace with strength and timestamps."""
    path: str
    strength: float
    last_accessed: float
    access_count: int = 1


class MyelinationMemory:
    """
    Layer 4: Myelination Memory.

    Frequently used paths get "myelinated" (strengthened).
    Infrequently used paths decay (forgetting curve).
    Encodes "intuition" from repeated experience.
    """

    def __init__(self, max_traces: int = 10000):
        self.max_traces = max_traces
        self.traces: Dict[str, MemoryTrace] = {}
        self.feature_codebook: Dict[str, int] = {}
        self.access_history: deque = deque(maxlen=500)

    def reinforce(
        self,
        path: List[str],
        success: bool = True,
        factor: float = 1.2,
    ) -> None:
        """
        Reinforce a path (Hebbian learning: neurons that fire together wire together).
        Success strengthens, failure weakens.
        """
        path_str = "->".join(path)

        if path_str in self.traces:
            trace = self.traces[path_str]
            if success:
                trace.strength *= factor
            else:
                trace.strength *= (2.0 - factor)  # Weaken
            trace.last_accessed = time.time()
            trace.access_count += 1
        else:
            # New path
            strength = 2.0 if success else 0.5
            self.traces[path_str] = MemoryTrace(
                path=path_str,
                strength=strength,
                last_accessed=time.time(),
                access_count=1,
            )

        # Cap strength
        self.traces[path_str].strength = max(0.1, min(10.0, self.traces[path_str].strength))

    def extract_feature(self, data: Dict) -> str:
        """
        Extract a compact feature code from raw data.
        This is the "feature码" — a distilled pattern.

        Note: Uses SHA256 for collision resistance per physical anchor principle.
        Weak hashes (MD5) violate the collision-resistance requirement and
        could allow feature collisions that corrupt memory indexing.
        """
        # Simple hash-based feature extraction
        data_str = json.dumps(data, sort_keys=True, default=str)
        digest = hashlib.sha256(data_str.encode()).hexdigest()
        feature = digest[:8]  # 8-char feature code

        self.feature_codebook[feature] = self.feature_codebook.get(feature, 0) + 1
        return feature

    def recall(self, path: List[str], min_strength: float = 0.5) -> Optional[MemoryTrace]:
        """Recall a memory trace if it exists and is strong enough."""
        path_str = "->".join(path)
        trace = self.traces.get(path_str)
        if trace and trace.strength >= min_strength:
            trace.last_accessed = time.time()
            trace.access_count += 1
            return trace
        return None

    def forget(self, decay_factor: float = 0.99) -> None:
        """
        Forgetting: decay unused paths and enforce capacity limits.
        - Old traces (not accessed in 1 hour) decay multiplicatively.
        - If still over capacity after decay, evict weakest (and oldest on ties).
        """
        current_time = time.time()
        cutoff = current_time - 3600  # 1 hour

        # First, decay old traces
        for path_str, trace in list(self.traces.items()):
            if trace.last_accessed < cutoff:
                trace.strength *= decay_factor
                if trace.strength < 0.05:
                    del self.traces[path_str]

        # Enforce capacity: evict weakest (and oldest if tied) until under limit
        while len(self.traces) > self.max_traces:
            # Find trace with minimum strength; break ties by oldest last_accessed
            weakest_key = min(
                self.traces.items(),
                key=lambda item: (item[1].strength, item[1].last_accessed)
            )[0]
            del self.traces[weakest_key]

    def get_best_paths(self, limit: int = 5) -> List[tuple[str, float]]:
        """Get the strongest (most myelinated) paths."""
        sorted_traces = sorted(
            self.traces.items(),
            key=lambda x: x[1].strength,
            reverse=True
        )
        return [(path, trace.strength) for path, trace in sorted_traces[:limit]]

    def get_coverage_ratio(self) -> float:
        """Ratio of myelinated paths to total possible paths (simplified)."""
        if not self.traces:
            return 0.0
        # Simplified: average strength as coverage proxy
        avg_strength = sum(t.strength for t in self.traces.values()) / len(self.traces)
        return min(avg_strength / 5.0, 1.0)  # Normalize to [0, 1]
