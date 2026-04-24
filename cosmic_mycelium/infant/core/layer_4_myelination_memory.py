"""
Layer 4 — Myelination Memory (Myelination Layer)
Hebbian learning, path reinforcement, forgetting curve, long-term memory.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any

import numpy as np


class DecaySchedule(Enum):
    """Forgetting curve schedules."""

    EXPONENTIAL = "exponential"  # Continuous decay: s(t) = s0 * exp(-λt)
    STEP = "step"  # Discrete drops at intervals
    SIGMOID = "sigmoid"  # Slow then fast decay (Ebbinghaus)


@dataclass
class MemoryTrace:
    """A memory trace with strength and timestamps."""

    path: str
    strength: float
    last_accessed: float
    access_count: int = 1
    created: float = field(default_factory=time.time)
    decay_schedule: DecaySchedule = DecaySchedule.EXPONENTIAL
    decay_rate: float = 0.01  # Per hour
    # Epic 3: semantic embedding of the end state for semantic consolidation
    state_embedding: np.ndarray | None = None


class MyelinationMemory:
    """
    Layer 4: Myelination Memory.

    Frequently used paths get "myelinated" (strengthened).
    Infrequently used paths decay (forgetting curve).
    Encodes "intuition" from repeated experience.

    Learning: Hebbian reinforcement + Ebbinghaus forgetting curve.
    """

    def __init__(
        self,
        max_traces: int = 10000,
        decay_schedule: DecaySchedule | str = DecaySchedule.EXPONENTIAL,
        decay_rate: float = 0.01,
        consolidation_threshold: float = 0.8,
        semantic_mapper: Any = None,
    ):
        """
        Args:
                max_traces: Maximum number of memory traces to retain.
                decay_schedule: Forgetting curve type (exponential/step/sigmoid).
                decay_rate: Base decay per hour (λ for exponential).
                consolidation_threshold: Similarity threshold for path consolidation.
                semantic_mapper: Optional SemanticMapper for computing state embeddings (Epic 3).
        """
        self.max_traces = max_traces
        self.decay_schedule = (
            DecaySchedule(decay_schedule)
            if isinstance(decay_schedule, str)
            else decay_schedule
        )
        self.decay_rate = decay_rate
        self.consolidation_threshold = consolidation_threshold
        self.semantic_mapper = semantic_mapper
        self.traces: dict[str, MemoryTrace] = {}
        self.feature_codebook: dict[str, int] = {}
        self.access_history: deque = deque(maxlen=500)
        self._total_reinforcements = 0
        self._lock = RLock()  # Sprint 5: thread-safe concurrent access

    def reinforce(
        self,
        path: list[str],
        success: bool = True,
        saliency: float = 1.0,
        end_state: dict | None = None,
    ) -> None:
        """
        Reinforce a path (Hebbian learning: neurons that fire together wire together).

        Success strengthens the path; failure weakens it. Reinforcement magnitude is
        scaled by saliency — high-saliency events (near energy red line, low confidence)
        produce stronger memory updates.

        Args:
            path: Sequence of actions/features.
            success: Whether the path led to successful outcome.
            saliency: Saliency factor (0.1 ~ 2.0). Default 1.0. High-saliency events
                      (e.g., energy near suspend threshold, low confidence) cause larger
                      strength adjustments.
            end_state: Optional physical state dict at path end. If provided and
                       semantic_mapper available, computes state_embedding for semantic
                       consolidation (Epic 3).
        """
        with self._lock:
            path_str = "->".join(path)
            self._total_reinforcements += 1

            # Compute effective multiplicative factor based on saliency.
            # Base success factor = 1.2 (+20%), base failure factor = 0.8 (-20%).
            # Saliency scales the deviation from 1.0: e.g., saliency=2 → success 1.4, failure 0.6.
            effective_factor = 1.0 + 0.2 * saliency

            if path_str in self.traces:
                trace = self.traces[path_str]
                if success:
                    trace.strength *= effective_factor
                else:
                    # Failure multiplier is symmetric: 2.0 - effective_factor
                    trace.strength *= (2.0 - effective_factor)
                trace.last_accessed = time.time()
                trace.access_count += 1
            else:
                strength = (1.0 + 0.2 * saliency) if success else (1.0 - 0.2 * saliency)
                strength = max(0.1, min(10.0, strength))
                trace = MemoryTrace(
                    path=path_str,
                    strength=strength,
                    last_accessed=time.time(),
                    access_count=1,
                    decay_schedule=self.decay_schedule,
                    decay_rate=self.decay_rate,
                )
                self.traces[path_str] = trace

            # Epic 3: compute state embedding if end_state provided
            if end_state is not None and self.semantic_mapper is not None:
                concept = self.semantic_mapper.map(end_state)
                trace.state_embedding = concept.feature_vector.copy()

            # Cap strength within bounds
            self.traces[path_str].strength = max(
                0.1, min(10.0, self.traces[path_str].strength)
            )

    def extract_feature(self, data: dict) -> str:
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

        with self._lock:
            self.feature_codebook[feature] = self.feature_codebook.get(feature, 0) + 1
        return feature

    def recall(self, path: list[str], min_strength: float = 0.5) -> MemoryTrace | None:
        """Recall a memory trace if it exists and is strong enough."""
        path_str = "->".join(path)
        with self._lock:
            trace = self.traces.get(path_str)
            if trace and trace.strength >= min_strength:
                trace.last_accessed = time.time()
                trace.access_count += 1
                return trace
            return None

    def forget(self, decay_factor: float | None = None) -> None:
        """
        Forgetting: decay unused paths and enforce capacity limits.
        Uses configurable decay schedule for biologically-plausible forgetting curves.

        - Exponential: continuous decay s(t) = s0 * exp(-λt)
        - Step: discrete drops at hourly boundaries
        - Sigmoid: slow → fast → slow (Ebbinghaus-inspired)

        Args:
                decay_factor: Optional override for decay rate for this call.
        """
        current_time = time.time()
        cutoff = current_time - 3600  # 1 hour threshold
        rate = decay_factor if decay_factor is not None else self.decay_rate

        with self._lock:
            for path_str, trace in list(self.traces.items()):
                age_hours = (current_time - trace.last_accessed) / 3600.0

                if trace.last_accessed < cutoff:
                    if trace.last_accessed == 0.0:
                        decay = 0.99
                    elif trace.decay_schedule == DecaySchedule.EXPONENTIAL:
                        decay = math.exp(-rate * age_hours)
                    elif trace.decay_schedule == DecaySchedule.STEP:
                        steps = int(age_hours)
                        decay = (1.0 - rate) ** steps
                    elif trace.decay_schedule == DecaySchedule.SIGMOID:
                        k = 2.0
                        t0 = 5.0
                        decay = 1.0 / (1.0 + math.exp(k * (age_hours - t0)))
                    else:
                        decay = 1.0 - min(rate * age_hours, 0.99)

                    trace.strength *= decay
                    if trace.strength < 0.05:
                        del self.traces[path_str]

            while len(self.traces) > self.max_traces:
                weakest_key = min(
                    self.traces.items(),
                    key=lambda item: (item[1].strength, item[1].last_accessed),
                )[0]
                del self.traces[weakest_key]

    def consolidate_similar_paths(self) -> int:
        """
        Merge paths that share a common prefix pattern (structural similarity).
        Paths like "a->b->c" and "a->b->d" share "a->b" prefix — consolidate
        the shared prefix into a stronger trace if similarity exceeds threshold.

        Returns:
                Number of traces merged/consolidated.
        """
        merged = 0
        prefix_strengths: dict[str, list[tuple[str, MemoryTrace]]] = {}

        # Group traces by their first N steps (prefix)
        for path_str, trace in list(self.traces.items()):
            parts = path_str.split("->")
            if len(parts) >= 2:
                prefix = "->".join(parts[:2])  # First 2 steps as prefix key
                prefix_strengths.setdefault(prefix, []).append((path_str, trace))

        # Consolidate groups with multiple members
        for prefix, members in prefix_strengths.items():
            if len(members) >= 2:
                # Calculate combined strength
                total_strength = sum(t.strength for _, t in members)
                avg_strength = total_strength / len(members)

                # Create/strengthen the prefix trace
                if prefix in self.traces:
                    prefix_trace = self.traces[prefix]
                    prefix_trace.strength = min(
                        10.0, prefix_trace.strength + avg_strength * 0.3
                    )
                else:
                    self.traces[prefix] = MemoryTrace(
                        path=prefix,
                        strength=min(10.0, avg_strength * 0.5),
                        last_accessed=time.time(),
                        access_count=len(members),
                        decay_schedule=self.decay_schedule,
                        decay_rate=self.decay_rate,
                    )
                    merged += 1

        return merged

    def consolidate_semantic_paths(self, similarity_threshold: float = 0.9) -> int:
        """
        Epic 3: Merge paths that lead to semantically similar end states.

        Unlike prefix-based consolidation, this merges paths whose final state
        embeddings are highly similar (cosine similarity > threshold), even if
        the action sequences (prefixes) are completely different.

        Args:
            similarity_threshold: Cosine similarity threshold (0-1). Higher = stricter.

        Returns:
            Number of traces merged/consolidated.
        """
        if self.semantic_mapper is None:
            return 0

        # Collect traces with state embeddings
        candidates = [
            (path_str, trace)
            for path_str, trace in self.traces.items()
            if trace.state_embedding is not None
        ]
        if len(candidates) < 2:
            return 0

        merged = 0
        # Build embedding matrix
        paths = []
        vecs = []
        for path_str, trace in candidates:
            paths.append(path_str)
            vecs.append(trace.state_embedding)

        arr = np.stack(vecs).astype(np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr_norm = arr / (norms + 1e-8)

        # Compute pairwise cosine similarity matrix
        sims = arr_norm @ arr_norm.T  # (N, N)

        # Greedy merging: for each pair with high similarity, merge weaker into stronger
        merged_set: set[str] = set()
        n = len(paths)
        for i in range(n):
            if paths[i] in merged_set:
                continue
            for j in range(i + 1, n):
                if paths[j] in merged_set:
                    continue
                if sims[i, j] >= similarity_threshold:
                    # Merge j into i (keep stronger, absorb weaker)
                    trace_i = self.traces[paths[i]]
                    trace_j = self.traces[paths[j]]
                    # Stronger trace gets a boost proportional to weaker's strength
                    if trace_i.strength >= trace_j.strength:
                        stronger, weaker = trace_i, trace_j
                    else:
                        stronger, weaker = trace_j, trace_i
                    stronger.strength = min(10.0, stronger.strength + weaker.strength * 0.3)
                    stronger.access_count += weaker.access_count
                    # Remove weaker trace
                    del self.traces[paths[j]]
                    merged_set.add(paths[j])
                    merged += 1
                    break  # restart scanning for i after merge

        return merged

    def normalize_strengths(self, target_max: float = 5.0) -> None:
        """
        Min-max normalize all trace strengths to [0.1, target_max] range.
        Prevents strength saturation and maintains discrimination.

        Args:
                target_max: Upper bound after normalization.
        """
        if not self.traces:
            return

        strengths = [t.strength for t in self.traces.values()]
        min_s = min(strengths)
        max_s = max(strengths)

        if max_s <= min_s:
            return  # No normalization needed

        for trace in self.traces.values():
            # Scale to [0.1, target_max] preserving relative ordering
            normalized = 0.1 + (target_max - 0.1) * (trace.strength - min_s) / (
                max_s - min_s
            )
            trace.strength = normalized

    def get_best_paths(self, limit: int = 5) -> list[tuple[str, float]]:
        """Get the strongest (most myelinated) paths."""
        sorted_traces = sorted(
            self.traces.items(), key=lambda x: x[1].strength, reverse=True
        )
        return [(path, trace.strength) for path, trace in sorted_traces[:limit]]

    def get_coverage_ratio(self) -> float:
        """
        Compute memory coverage as weighted combination of:
        - Capacity utilization: traces_filled / max_traces
        - Strength diversity: normalized entropy of strength distribution
        - Access richness: avg access_count across traces

        Returns:
                Float in [0, 1]: 1.0 = fully myelinated, 0.0 = empty.
        """
        if not self.traces:
            return 0.0

        # Capacity component
        capacity_ratio = len(self.traces) / self.max_traces

        # Strength diversity component (normalized entropy)
        strengths = [t.strength for t in self.traces.values()]
        total = sum(strengths)
        if total > 0:
            probs = [s / total for s in strengths]
            entropy = -sum(p * math.log(p + 1e-10) for p in probs)
            max_entropy = math.log(len(strengths))
            diversity = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            diversity = 0.0

        # Access richness component
        avg_access = sum(t.access_count for t in self.traces.values()) / len(
            self.traces
        )
        richness = min(avg_access / 10.0, 1.0)  # Cap at 10 accesses

        # Weighted combination
        coverage = 0.4 * capacity_ratio + 0.4 * diversity + 0.2 * richness
        return max(0.0, min(1.0, coverage))

    def get_status(self) -> dict:
        """Return memory status for monitoring."""
        return {
            "trace_count": len(self.traces),
            "max_traces": self.max_traces,
            "capacity_utilization": len(self.traces) / self.max_traces,
            "total_reinforcements": self._total_reinforcements,
            "avg_strength": (
                sum(t.strength for t in self.traces.values()) / len(self.traces)
                if self.traces
                else 0.0
            ),
            "coverage_ratio": self.get_coverage_ratio(),
            "decay_schedule": self.decay_schedule.value,
            "feature_codebook_size": len(self.feature_codebook),
        }
