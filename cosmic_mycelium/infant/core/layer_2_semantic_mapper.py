"""
Layer 2 — Semantic Mapper
Maps physical entities to semantic concepts, builds causal potential field.

Phase 4.2 Extension (Cross-Civilization Semantic Mapping):
- Multi-modal concept representation (vibration, temperature, audio, visual)
- Cross-modal linking via shared concept IDs
- Integration with GlobalConceptRegistry for civilization-scale alignment
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint

if TYPE_CHECKING:
    from cosmic_mycelium.common.config_manager import ConfigManager
    # GlobalConceptRegistry — reserved for SWARM-scale alignment.
    # Not yet integrated; SemanticMapper works standalone.
    GlobalConceptRegistry = None  # type: ignore[name-defined]


@dataclass
class SemanticConcept:
    """A learned semantic concept with multi-modal support (Phase 4.2)."""

    concept_id: str
    feature_vector: np.ndarray  # Primary modality vector (legacy field)
    frequency: int = 1
    associated_actions: list[str] = field(default_factory=list)
    # Phase 4.2: multi-modal extension
    modality_vectors: dict[str, np.ndarray] = field(default_factory=dict)
    cross_modal_links: list[str] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    @property
    def id(self) -> str:
        """Alias for concept_id (backward compatibility)."""
        return self.concept_id

    @property
    def related_concepts(self) -> list[str]:
        """Alias for cross_modal_links (test compatibility)."""
        return self.cross_modal_links

    def add_modality(self, modality: str, vector: np.ndarray) -> None:
        """
        Add or update a modality representation via EMA.

        If modality exists: vector = 0.9 * old + 0.1 * new
        If new: store vector copy directly
        """
        if modality in self.modality_vectors:
            self.modality_vectors[modality] = (
                0.9 * self.modality_vectors[modality] + 0.1 * vector
            )
        else:
            self.modality_vectors[modality] = vector.copy()
        # NOTE: frequency is incremented by the caller (SemanticMapper.map),
        # not here, to avoid double-counting.
        self.last_seen = time.time()

    def get_aligned_vector(self, modality: str, embedding_dim: int) -> np.ndarray:
        """
        Return vector aligned to the given modality.

        If the concept has that modality, return it (padded/truncated to embedding_dim).
        Otherwise fall back to the primary feature_vector.
        """
        if modality in self.modality_vectors:
            vec = self.modality_vectors[modality]
        else:
            vec = self.feature_vector

        # Ensure correct dimensionality
        if len(vec) < embedding_dim:
            vec = np.pad(vec, (0, embedding_dim - len(vec)))
        elif len(vec) > embedding_dim:
            vec = vec[:embedding_dim]
        return vec


class SemanticMapper:
    """
    Layer 2: Semantic Mapping.

    Bridges raw physical signals (vibration, temperature) with abstract concepts.
    Builds a "causal potential field" — gradients of what leads to what.

    Learning: Exponential moving average without normalization.

    Phase 4.2 Extensions:
    - Multi-modal feature extraction (vibration, temperature, audio, visual)
    - Cross-modal concept linking via GlobalConceptRegistry
    - Civilization-scale concept alignment
    """

    # Standard modality labels (Phase 4.2)
    MODALITIES = ["vibration", "temperature", "audio", "visual"]

    def __init__(
        self,
        embedding_dim: int | None = None,
        config_manager: "ConfigManager | None" = None,
        concept_registry: "GlobalConceptRegistry | None" = None,
    ):
        if embedding_dim is not None:
            self.embedding_dim = embedding_dim
        elif config_manager is not None:
            self.embedding_dim = config_manager.get(
                "semantic_mapper", "embedding_dim", 16  # Phase 1 default, Phase 4.2 overrides to 64
            )
        else:
            self.embedding_dim = 16  # legacy default — backward compatible
        self.concepts: dict[str, SemanticConcept] = {}
        self.fingerprint = PhysicalFingerprint()
        self._total_observations = 0
        self.registry = concept_registry  # Phase 4.2: global concept registry
        self._lock = RLock()  # Sprint 5: thread-safe concurrent access

    def _extract_modality_vector(
        self, physical_state: dict[str, float], modality: str, modality_dim: int
    ) -> np.ndarray:
        """
        Extract feature vector for a specific modality from physical state keys.

        Modality extraction rules:
        - vibration: keys with 'vib', 'accel', 'seism'
        - temperature: keys with 'temp', 'thermal', 'thermo'
        - audio: keys with 'audio', 'sound', 'mic'
        - visual: keys with 'light', 'lux', 'motion', 'cam', 'lumin'
        """
        values = []
        for k, v in physical_state.items():
            k_lower = k.lower()
            if modality == "vibration" and (
                "vib" in k_lower or "accel" in k_lower or "seism" in k_lower
            ):
                values.append(float(v))
            elif modality == "temperature" and (
                "temp" in k_lower or "thermal" in k_lower or "thermo" in k_lower
            ):
                values.append(float(v))
            elif modality == "audio" and (
                "audio" in k_lower or "sound" in k_lower or "mic" in k_lower
            ):
                values.append(float(v))
            elif modality == "visual" and (
                "light" in k_lower
                or "lux" in k_lower
                or "motion" in k_lower
                or "cam" in k_lower
                or "lumin" in k_lower
            ):
                values.append(float(v))

        if not values:
            return np.zeros(modality_dim)

        arr = np.array(values[:modality_dim], dtype=float)
        if len(arr) < modality_dim:
            arr = np.pad(arr, (0, modality_dim - len(arr)))
        return arr

    def map(self, physical_state: dict[str, float]) -> SemanticConcept:
        """
        Map physical state to a semantic concept with multi-modal extension.

        Legacy behavior (unchanged):
        - feature_vector = raw physical values padded/truncated to embedding_dim
        - EMA update on reuse: 0.9 * old + 0.1 * new

        Phase 4.2 extensions:
        - Extract modality-specific vectors into modality_vectors dict
        - Cross-modal linking via GlobalConceptRegistry if connected
        """
        with self._lock:
            self._total_observations += 1

            # Legacy feature vector: all values concatenated (preserves original behavior)
            values = list(physical_state.values())
            if not values:
                legacy_vec = np.zeros(self.embedding_dim)
            else:
                arr = np.array(values, dtype=float)
                if len(arr) < self.embedding_dim:
                    arr = np.pad(arr, (0, self.embedding_dim - len(arr)))
                legacy_vec = arr[: self.embedding_dim]

            # Canonical fingerprint (concept ID)
            fp = self.fingerprint.generate(physical_state)

            # Phase 4.2: Modality vectors (per-modality sub-space)
            # Each modality vector is aligned to embedding_dim for consistency
            modality_dim = self.embedding_dim

            if fp in self.concepts:
                concept = self.concepts[fp]
                concept.frequency += 1
                # Legacy EMA
                concept.feature_vector = 0.9 * concept.feature_vector + 0.1 * legacy_vec
                # Update all modalities present in this observation
                for modality in self.MODALITIES:
                    vec = self._extract_modality_vector(physical_state, modality, modality_dim)
                    if np.any(vec):
                        concept.add_modality(modality, vec)
            else:
                concept = SemanticConcept(concept_id=fp, feature_vector=legacy_vec.copy())
                # Extract modalities from first observation
                for modality in self.MODALITIES:
                    vec = self._extract_modality_vector(physical_state, modality, modality_dim)
                    if np.any(vec):
                        concept.modality_vectors[modality] = vec
                self.concepts[fp] = concept

            concept.last_seen = time.time()

            # Phase 4.2: Cross-modal linking via registry
            if self.registry is not None:
                self._link_concept_via_registry(concept)

            return concept

    # Test compatibility wrapper
    def add_modality(self, concept: SemanticConcept, modality: str, vector: np.ndarray) -> None:
        """Delegate to concept.add_modality (test compatibility)."""
        concept.add_modality(modality, vector)

    def _link_concept_via_registry(self, concept: SemanticConcept) -> None:
        """
        Query GlobalConceptRegistry for cross-modal and cross-node links.

        The registry maintains concept entries from all civilization nodes.
        This method:
        1. Pulls missing modality vectors from registry (same concept_id, different modality)
        2. Finds other concepts sharing modalities with this concept (semantic neighbors)
        3. Adds them to cross_modal_links (bidirectional semantic linking)
        """
        if self.registry is None:
            return

        try:
            # 1. Cross-modal fill-in: pull missing modality vectors from registry
            registry_entry = self.registry.get_concept(concept.concept_id)
            if registry_entry:
                reg_modalities = registry_entry.get("modalities", {})
                for modality, reg_vec in reg_modalities.items():
                    if modality not in concept.modality_vectors:
                        concept.modality_vectors[modality] = np.array(reg_vec)
                        # 为新填充的模态添加自链接（表示该概念在注册表中确认拥有此模态）
                        self_link = f"{concept.concept_id}:{modality}"
                        if self_link not in concept.cross_modal_links:
                            concept.cross_modal_links.append(self_link)

            # 2. Cross-modal linking: find other concepts sharing modalities (semantic neighbors)
            for modality in concept.modality_vectors:
                related_ids = self.registry.find_related_by_modality(concept.concept_id, modality)
                for rid in related_ids:
                    # Store raw concept ID for general linking checks
                    if rid not in concept.cross_modal_links:
                        concept.cross_modal_links.append(rid)
                    # Store "cid:modality" format for modality-specific queries
                    link = f"{rid}:{modality}"
                    if link not in concept.cross_modal_links:
                        concept.cross_modal_links.append(link)
        except (TypeError, AttributeError, ValueError) as e:
            logger.warning("SemanticMapper: cross-modal linking failed: %s", e)

    def get_potential_gradient(
        self,
        source: str,
        target: str,
    ) -> np.ndarray | None:
        """
        Compute gradient vector from source concept to target concept.

        Args:
            source: Source concept ID (origin)
            target: Target concept ID (destination)

        Returns:
            Direction vector (target_vec - source_vec), or None if either unreachable.
        """
        # Resolve source vector
        if source not in self.concepts:
            return None
        src_vec = self.concepts[source].get_aligned_vector("vibration", self.embedding_dim)

        # Resolve target vector
        if target not in self.concepts:
            # Cross-modal fallback via registry
            if self.registry is not None:
                reg_entry = self.registry.get_concept(target)
                if reg_entry:
                    reg_vec = np.array(
                        reg_entry.get("modalities", {}).get("vibration", np.zeros(self.embedding_dim))
                    )
                    return reg_vec - src_vec
            return None

        tgt_concept = self.concepts[target]
        tgt_vec = tgt_concept.get_aligned_vector("vibration", self.embedding_dim)
        return tgt_vec - src_vec

    def _current_context_vector(
        self,
        modality: str | None = None,
        default: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Get the most recent vector for the given modality.
        (Internal helper for gradient computation.)

        Args:
            modality: If provided, look in modality_vectors; otherwise return feature_vector.
            default: Fallback if no suitable vector found.

        Returns:
            Vector as ndarray. If no default provided, returns zeros of embedding_dim.
        """
        if not self.concepts:
            if default is not None:
                return default
            return np.zeros(self.embedding_dim)

        # Most recently seen concept
        most_recent = max(self.concepts.values(), key=lambda c: c.last_seen)

        if modality is None:
            # No modality specified → return primary feature vector
            return most_recent.feature_vector.copy()

        if modality in most_recent.modality_vectors:
            return most_recent.modality_vectors[modality].copy()

        if default is not None:
            return default

        return np.zeros(self.embedding_dim)

    def get_status(self) -> dict:
        """Return mapper status for monitoring."""
        total_modality_vectors = sum(
            len(c.modality_vectors) for c in self.concepts.values()
        )
        modalities_covered = list(
            {
                m
                for c in self.concepts.values()
                for m in c.modality_vectors
            }
        )
        return {
            "concept_count": len(self.concepts),
            "total_observations": self._total_observations,
            "embedding_dim": self.embedding_dim,
            "modalities_covered": modalities_covered,
            "avg_modalities_per_concept": (
                total_modality_vectors / len(self.concepts)
                if self.concepts
                else 0.0
            ),
            "registry_connected": self.registry is not None,
        }
