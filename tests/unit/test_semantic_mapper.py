"""
Layer 2 — Semantic Mapper Tests
Tests concept mapping, embedding dimension handling, gradient normalization.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import numpy as np

from cosmic_mycelium.common.config_manager import ConfigManager
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import (
    SemanticConcept,
    SemanticMapper,
)


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


# =============================================================================
# Phase 4.2: Multi-Modal & Cross-Civilization Semantic Mapping
# =============================================================================
class TestMultiModalFeatureExtraction:
    """Tests for Phase 4.2 multi-modal feature extraction."""

    def test_vibration_modality_extracted(self):
        """Keys with 'vib' or 'accel' are recognized as vibration modality."""
        mapper = SemanticMapper(embedding_dim=8)
        physical = {
            "vibration_x": 1.5,
            "vibration_y": 2.5,
            "vibration_z": 3.0,
            "temperature": 22.0,  # Different modality
        }
        concept = mapper.map(physical)

        assert "vibration" in concept.modality_vectors
        vib_vec = concept.modality_vectors["vibration"]
        assert len(vib_vec) == 8  # modality vectors use full embedding_dim
        assert np.isclose(vib_vec[0], 1.5)
        assert np.isclose(vib_vec[1], 2.5)

    def test_temperature_modality_extracted(self):
        """Keys with 'temp' are recognized as temperature modality."""
        mapper = SemanticMapper(embedding_dim=8)
        physical = {"temp_core": 37.0, "temp_skin": 32.0, "vibration": 0.1}

        concept = mapper.map(physical)

        assert "temperature" in concept.modality_vectors
        temp_vec = concept.modality_vectors["temperature"]
        assert len(temp_vec) == 8  # modality vectors use full embedding_dim
        assert np.isclose(temp_vec[0], 37.0)
        assert np.isclose(temp_vec[1], 32.0)

    def test_audio_modality_extracted(self):
        """Keys with 'audio' or 'sound' recognized as audio modality."""
        mapper = SemanticMapper(embedding_dim=8)
        physical = {"audio_level": 0.8, "sound_pressure": 0.6}

        concept = mapper.map(physical)

        assert "audio" in concept.modality_vectors
        audio_vec = concept.modality_vectors["audio"]
        assert len(audio_vec) == 8  # modality vectors use full embedding_dim
        assert np.isclose(audio_vec[0], 0.8)
        assert np.isclose(audio_vec[1], 0.6)

    def test_visual_modality_extracted(self):
        """Keys with 'light' or 'motion' recognized as visual modality."""
        mapper = SemanticMapper(embedding_dim=8)
        physical = {"light_lux": 100.0, "motion_magnitude": 0.5}

        concept = mapper.map(physical)

        assert "visual" in concept.modality_vectors
        vis_vec = concept.modality_vectors["visual"]
        assert len(vis_vec) == 8  # modality vectors use full embedding_dim
        assert np.isclose(vis_vec[0], 100.0)
        assert np.isclose(vis_vec[1], 0.5)

    def test_multiple_modalities_captured_in_one_observation(self):
        """Single physical state can contribute to multiple modality vectors."""
        mapper = SemanticMapper(embedding_dim=12)
        physical = {
            "vibration_x": 1.0,
            "temp_core": 36.5,
            "audio_level": 0.7,
            "light_lux": 50.0,
        }

        concept = mapper.map(physical)

        assert len(concept.modality_vectors) == 4
        assert "vibration" in concept.modality_vectors
        assert "temperature" in concept.modality_vectors
        assert "audio" in concept.modality_vectors
        assert "visual" in concept.modality_vectors

    def test_ema_update_on_modality_reuse(self):
        """Modality vectors update via EMA when same concept is re-observed."""
        mapper = SemanticMapper(embedding_dim=8)  # 8//4=2 dims per modality
        physical = {"vibration_x": 1.0, "vibration_y": 2.0}

        # First observation
        concept = mapper.map(physical)
        old_vec = concept.modality_vectors["vibration"].copy()
        # Second observation of same physical state — values identical, EMA still applies
        concept = mapper.map(physical)
        new_vec = concept.modality_vectors["vibration"]

        # Vector should be stable (EMA with identical input preserves value)
        assert np.allclose(new_vec, old_vec)
        assert concept.frequency == 2



