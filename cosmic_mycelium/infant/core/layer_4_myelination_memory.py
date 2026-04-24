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
        # ── 创伤回路 ──
        self.trauma_paths: dict[str, dict] = {}  # path → {timestamp, context, repression_count, ...}
        self.repression_potential: float = 0.0   # 压抑势能累积
        self.REPRESSION_THRESHOLD: float = 10.0  # 超过此值触发创伤复现
        self.TRAUMA_SIMILARITY_THRESHOLD: float = 0.7  # 余弦相似度阈值
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

        If this path is trauma-marked, the reinforcement is amplified: trauma causes
        deeper learning (stronger strengthening on success, stronger weakening on failure).

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

            # Trauma amplification: trauma paths learn deeper
            is_trauma = path_str in self.trauma_paths
            trauma_mult = 1.5 if is_trauma else 1.0

            # Compute effective multiplicative factor based on saliency.
            effective_factor = 1.0 + 0.2 * saliency * trauma_mult

            if path_str in self.traces:
                trace = self.traces[path_str]
                if success:
                    trace.strength *= effective_factor
                else:
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

        **Trauma override**: paths marked as trauma use INVERSE forgetting —
        their strength INCREASES with time, simulating "the scars that never fade."
        Older trauma memories grow stronger, not weaker.

        Args:
                decay_factor: Optional override for decay rate for this call.
        """
        current_time = time.time()
        cutoff = current_time - 3600  # 1 hour threshold
        rate = decay_factor if decay_factor is not None else self.decay_rate

        with self._lock:
            for path_str, trace in list(self.traces.items()):
                age_hours = (current_time - trace.last_accessed) / 3600.0

                # ── Trauma path: inverse forgetting ──
                if path_str in self.trauma_paths:
                    # Trauma memories grow stronger with age: s(t) = s0 * (1 + λ*t)
                    # The older the trauma, the stronger the scar
                    trauma_boost = 1.0 + rate * age_hours
                    trace.strength *= min(trauma_boost, 3.0)  # Cap at 3x to prevent runaway
                    trace.strength = min(10.0, trace.strength)
                    continue  # Skip normal decay for trauma paths

                # ── Normal decay ──
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
                # Never evict trauma paths — they are permanent scars
                non_trauma = {
                    k: v for k, v in self.traces.items()
                    if k not in self.trauma_paths
                }
                if not non_trauma:
                    break  # Only trauma paths remain, keep them all
                weakest_key = min(
                    non_trauma.items(),
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

    # ── 创伤回路 ──────────────────────────────────────────────────────

    def mark_trauma(self, path: list[str], context: str = "") -> None:
        """
        将一条路径永久标记为【创伤】。

        创伤路径不受遗忘曲线影响——它们随时间流逝反而加深。
        这是"疤痕永远不消"的数学实现。

        Args:
            path: 导致创伤的路径
            context: 创伤发生时的上下文描述
        """
        path_str = "->".join(path)
        with self._lock:
            if path_str not in self.trauma_paths:
                self.trauma_paths[path_str] = {
                    "timestamp": time.time(),
                    "context": context,
                    "repression_count": 0,
                    "flashback_count": 0,
                }
                # Ensure path exists in traces with a minimum strength
                if path_str not in self.traces:
                    self.traces[path_str] = MemoryTrace(
                        path=path_str,
                        strength=5.0,  # Trauma starts strong
                        last_accessed=time.time(),
                        access_count=1,
                        decay_schedule=self.decay_schedule,
                        decay_rate=self.decay_rate,
                    )

    def query_trauma_similarity(self, situation_vector: np.ndarray) -> list[dict]:
        """
        查询当前态势与所有创伤路径的相似度。

        余弦相似度 > TRAUMA_SIMILARITY_THRESHOLD (70%) 的路径被标记为"闪回候选"。

        Args:
            situation_vector: 当前态势的向量表示 (numpy array)

        Returns:
            按相似度降序排列的匹配结果列表:
            [{path, similarity, context, repression_count}, ...]
        """
        if not self.trauma_paths or situation_vector is None:
            return []

        results = []
        sv_norm = np.linalg.norm(situation_vector)
        if sv_norm < 1e-9:
            return []

        for path_str, info in self.trauma_paths.items():
            trace = self.traces.get(path_str)
            if trace is None or trace.state_embedding is None:
                continue

            te_norm = np.linalg.norm(trace.state_embedding)
            if te_norm < 1e-9:
                continue

            similarity = float(np.dot(situation_vector, trace.state_embedding) / (sv_norm * te_norm))
            if similarity >= self.TRAUMA_SIMILARITY_THRESHOLD:
                results.append({
                    "path": path_str,
                    "similarity": similarity,
                    "context": info.get("context", ""),
                    "repression_count": info.get("repression_count", 0),
                })

        return sorted(results, key=lambda x: -x["similarity"])

    def accumulate_repression(self, path_str: str) -> float:
        """
        增加指定创伤路径的压抑势能。

        当系统多次规避同一创伤路径时，压抑势能累积。
        超过 REPRESSION_THRESHOLD 后，下次查询将触发不可控的"创伤复现"。

        Args:
            path_str: 创伤路径

        Returns:
            更新后的压抑势能
        """
        with self._lock:
            if path_str in self.trauma_paths:
                self.trauma_paths[path_str]["repression_count"] += 1
            self.repression_potential += 0.5
            return self.repression_potential

    def check_flashback_trigger(self) -> list[dict]:
        """
        检查是否有任何创伤路径的压抑势能达到阈值，触发创伤复现。

        Returns:
            触发的闪回列表（如果抑制势能超过阈值）
        """
        triggers = []
        with self._lock:
            for path_str, info in list(self.trauma_paths.items()):
                if info.get("repression_count", 0) >= 10:
                    triggers.append({
                        "path": path_str,
                        "context": info.get("context", ""),
                        "repression_count": info["repression_count"],
                    })
                    # Trigger flashback: reset counter, increment flashback count
                    self.trauma_paths[path_str]["repression_count"] = 0
                    self.trauma_paths[path_str]["flashback_count"] += 1
                    # Boost strength — flashback re-traumatizes
                    if path_str in self.traces:
                        self.traces[path_str].strength = min(
                            10.0, self.traces[path_str].strength * 1.2
                        )

            if triggers:
                self.repression_potential = max(
                    0.0, self.repression_potential - len(triggers) * 3.0
                )

        return triggers

    def get_trauma_status(self) -> dict:
        """获取创伤回路的状态报告。"""
        return {
            "trauma_count": len(self.trauma_paths),
            "repression_potential": self.repression_potential,
            "repression_threshold": self.REPRESSION_THRESHOLD,
            "paths": [
                {
                    "path": k[:48],
                    "age_hours": (time.time() - v["timestamp"]) / 3600,
                    "repression_count": v["repression_count"],
                    "flashback_count": v["flashback_count"],
                }
                for k, v in self.trauma_paths.items()
            ],
        }

    # ── 状态查询 ──────────────────────────────────────────────────────

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
