"""
Layer 2 — Semantic Mapper
Maps physical entities to semantic concepts, builds causal potential field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint
from cosmic_mycelium.common.config_manager import ConfigManager


@dataclass
class SemanticConcept:
    """A learned semantic concept."""
    id: str
    feature_vector: np.ndarray
    frequency: int = 1
    associated_actions: list[str] = field(default_factory=list)


class SemanticMapper:
    """
    Layer 2: Semantic Mapping.

    Bridges raw physical signals (vibration, temperature) with abstract concepts.
    Builds a "causal potential field" — gradients of what leads to what.
    """

    def __init__(
        self,
        embedding_dim: int | None = None,
        config_manager: ConfigManager | None = None,
    ):
        if embedding_dim is not None:
            self.embedding_dim = embedding_dim
        elif config_manager is not None:
            self.embedding_dim = config_manager.get(
                "semantic_mapper", "embedding_dim", 16
            )
        else:
            # Fallback to infant-scale default
            self.embedding_dim = 16
        self.concepts: Dict[str, SemanticConcept] = {}
        self.fingerprint = PhysicalFingerprint()

    def map(self, physical_state: Dict[str, float]) -> SemanticConcept:
        """
        Map a physical state to a semantic concept.
        Creates new concept if unknown, reinforces existing if known.
        """
        # Simple feature vector from physical state values
        values = list(physical_state.values())
        if not values:
            vec = np.zeros(self.embedding_dim)
        else:
            arr = np.array(values, dtype=float)
            if len(arr) < self.embedding_dim:
                arr = np.pad(arr, (0, self.embedding_dim - len(arr)))
            vec = arr[:self.embedding_dim]

        # Generate fingerprint-based ID
        fp = self.fingerprint.generate(physical_state)
        if fp in self.concepts:
            concept = self.concepts[fp]
            concept.frequency += 1
            # Update embedding as moving average (no normalization)
            concept.feature_vector = 0.9 * concept.feature_vector + 0.1 * vec
        else:
            concept = SemanticConcept(
                id=fp,
                feature_vector=vec,
            )
            self.concepts[fp] = concept

        return concept

    def get_potential_gradient(self, target: str) -> np.ndarray:
        """
        Get gradient toward a target concept.
        Returns a direction vector in semantic space.
        """
        if target not in self.concepts:
            return np.zeros(self.embedding_dim)
        target_vec = self.concepts[target].feature_vector
        # Simplified: return negative of target (gradient descent)
        return -target_vec
