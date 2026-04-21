"""
Layer 2 — Semantic Mapper Tests
Tests concept mapping, embedding dimension handling, gradient normalization.
"""

from __future__ import annotations

import numpy as np
import pytest
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import (
    SemanticMapper,
    SemanticConcept,
)
from cosmic_mycelium.common.config_manager import ConfigManager


class TestSemanticMapperInitialization:
    """Tests for mapper construction and config handling."""

    def test_default_embedding_dim(self):
        """Default embedding_dim is 16."""
        mapper = SemanticMapper()
        assert mapper.embedding_dim == 16

    def test_explicit_embedding_dim_overrides_config(self):
        """Explicit embedding_dim takes precedence over ConfigManager."""
        cm = ConfigManager.for_infant()
        # Infant default is 16, we override to 32
        mapper = SemanticMapper(embedding_dim=32, config_manager=cm)
        assert mapper.embedding_dim == 32

    def test_config_manager_used_when_no_explicit_dim(self):
        """When embedding_dim not provided, reads from ConfigManager."""
        cm = ConfigManager.for_cluster()  # cluster default is 64
        mapper = SemanticMapper(config_manager=cm)
        assert mapper.embedding_dim == 64

    def test_concept_storage_starts_empty(self):
        """New mapper has no concepts."""
        mapper = SemanticMapper()
        assert len(mapper.concepts) == 0


class TestConceptMapping:
    """Tests for map() behavior."""

    def test_map_creates_new_concept_for_unknown_state(self):
        """Unknown physical state creates a new SemanticConcept."""
        mapper = SemanticMapper(embedding_dim=4)
        physical = {"temp": 25.0, "vibration": 0.5}

        concept = mapper.map(physical)

        assert isinstance(concept, SemanticConcept)
        assert concept.id in mapper.concepts
        assert len(mapper.concepts) == 1

    def test_map_returns_same_concept_for_same_state(self):
        """Idempotent: same physical state maps to same concept."""
        mapper = SemanticMapper(embedding_dim=4)
        physical = {"temp": 25.0, "vibration": 0.5}

        c1 = mapper.map(physical)
        c2 = mapper.map(physical)

        assert c1.id == c2.id
        assert len(mapper.concepts) == 1

    def test_map_increments_frequency_on_reuse(self):
        """Frequency increments on each mapping of same concept."""
        mapper = SemanticMapper(embedding_dim=4)
        physical = {"temp": 25.0}

        mapper.map(physical)
        freq1 = mapper.concepts[mapper.map(physical).id].frequency
        mapper.map(physical)
        freq2 = mapper.concepts[mapper.map(physical).id].frequency

        assert freq2 > freq1

    def test_embedding_vector_shape_matches_embedding_dim(self):
        """Feature vector length equals embedding_dim."""
        mapper = SemanticMapper(embedding_dim=16)
        physical = {"a": 1.0, "b": 2.0, "c": 3.0}

        concept = mapper.map(physical)

        assert len(concept.feature_vector) == 16

    def test_feature_vector_from_physical_values(self):
        """Feature vector derived from physical state values."""
        mapper = SemanticMapper(embedding_dim=3)
        physical = {"x": 1.0, "y": 2.0}

        concept = mapper.map(physical)

        # First 2 dims should match the values
        assert np.isclose(concept.feature_vector[0], 1.0)
        assert np.isclose(concept.feature_vector[1], 2.0)

    def test_empty_physical_state_yields_zero_vector(self):
        """Empty physical dict yields zero embedding."""
        mapper = SemanticMapper(embedding_dim=8)
        concept = mapper.map({})

        assert np.allclose(concept.feature_vector, 0.0)

    def test_physical_state_padded_or_truncated(self):
        """Vector is padded with zeros or truncated to embedding_dim."""
        mapper = SemanticMapper(embedding_dim=5)
        physical = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0, "f": 6.0}

        concept = mapper.map(physical)

        # First 5 values present, f is dropped
        assert len(concept.feature_vector) == 5
        assert np.isclose(concept.feature_vector[0], 1.0)
        assert np.isclose(concept.feature_vector[4], 5.0)


class TestAssociatedActions:
    """Tests for action association."""

    def test_associated_actions_starts_empty(self):
        """New concepts have empty action list."""
        mapper = SemanticMapper()
        concept = mapper.map({"x": 1.0})
        assert concept.associated_actions == []

    def test_actions_can_be_added_after_creation(self):
        """Actions can be appended to concept after creation."""
        mapper = SemanticMapper()
        concept = mapper.map({"x": 1.0})
        concept.associated_actions.append("move_forward")
        assert "move_forward" in concept.associated_actions


class TestNormalization:
    """Tests for feature vector scale (non-normalized by default)."""

    def test_feature_vector_not_normalized_by_default(self):
        """Feature vector L2 norm is NOT forced to 1.0 (raw values preserved)."""
        mapper = SemanticMapper(embedding_dim=8)
        physical = {"a": 3.0, "b": 4.0}  # norm = 5.0
        concept = mapper.map(physical)

        norm = np.linalg.norm(concept.feature_vector)
        # Raw values are preserved, so norm should be 5.0 (or close due to padding zeros)
        assert np.isclose(norm, 5.0, atol=1e-6)
