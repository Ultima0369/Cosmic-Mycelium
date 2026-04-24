"""
Unit tests for SemanticMapper modality extraction and multi-modal extensions.

Covers: _extract_modality_vector, modality padding, EMA update, cross-modal linking.
"""

import numpy as np
import pytest

from cosmic_mycelium.infant.core.layer_2_semantic_mapper import (
    SemanticMapper,
    SemanticConcept,
)


class TestModalityExtraction:
    """Test modality vector extraction from physical state keys."""

    def test_extract_vibration_modality(self):
        mapper = SemanticMapper(embedding_dim=16)
        state = {
            "vibration": 0.5,
            "accel_x": 0.1,
            "seism_noise": 0.05,
            "temperature": 22.0,  # not vibration
        }
        vib_vec = mapper._extract_modality_vector(state, "vibration", modality_dim=4)
        assert vib_vec.shape == (4,)
        # Should include vib, accel_x, seism_noise (order as they appear)
        assert np.isclose(vib_vec[0], 0.5)
        assert np.isclose(vib_vec[1], 0.1)
        assert np.isclose(vib_vec[2], 0.05)
        # fourth slot zero-padded
        assert np.isclose(vib_vec[3], 0.0)

    def test_extract_temperature_modality(self):
        mapper = SemanticMapper(embedding_dim=16)
        state = {
            "temp_core": 37.0,
            "thermal_exterior": 25.5,
            "vibration": 0.2,
        }
        temp_vec = mapper._extract_modality_vector(state, "temperature", modality_dim=4)
        assert temp_vec.shape == (4,)
        assert np.isclose(temp_vec[0], 37.0)
        assert np.isclose(temp_vec[1], 25.5)
        assert np.isclose(temp_vec[2], 0.0)  # padding
        assert np.isclose(temp_vec[3], 0.0)

    def test_extract_audio_modality_case_insensitive(self):
        mapper = SemanticMapper(embedding_dim=16)
        state = {
            "Audio_Input": 0.8,
            "SOUND_LEVEL": 0.6,
            "mic_1": 0.9,
        }
        audio_vec = mapper._extract_modality_vector(state, "audio", modality_dim=5)
        assert len(audio_vec) == 5
        assert np.isclose(audio_vec[0], 0.8)
        assert np.isclose(audio_vec[1], 0.6)
        assert np.isclose(audio_vec[2], 0.9)

    def test_extract_visual_modality(self):
        mapper = SemanticMapper(embedding_dim=16)
        state = {
            "light_lux": 100.0,
            "motion_detected": 0.3,
            "cam_brightness": 0.7,
            "luminance": 50.0,
        }
        vis_vec = mapper._extract_modality_vector(state, "visual", modality_dim=5)
        assert vis_vec.shape == (5,)
        # light_lux, motion_detected, cam_brightness, luminance (order depends on dict iteration)
        values = {100.0, 0.3, 0.7, 50.0}
        for v in values:
            assert any(np.isclose(vis_vec[i], v) for i in range(4))

    def test_extract_modality_unknown_returns_zeros(self):
        mapper = SemanticMapper(embedding_dim=16)
        state = {"random_metric": 1.0}
        vec = mapper._extract_modality_vector(state, "vibration", modality_dim=4)
        assert np.allclose(vec, np.zeros(4))

    def test_extract_modality_truncates_to_dim(self):
        """If more values than dim, truncate."""
        mapper = SemanticMapper(embedding_dim=16)
        state = {f"vib_{i}": float(i) for i in range(10)}
        vec = mapper._extract_modality_vector(state, "vibration", modality_dim=3)
        assert vec.shape == (3,)
        assert np.isclose(vec[0], 0.0)
        assert np.isclose(vec[1], 1.0)
        assert np.isclose(vec[2], 2.0)

    def test_extract_modality_pads_partial(self):
        """Shorter vector should be zero-padded to modality_dim."""
        mapper = SemanticMapper(embedding_dim=16)
        state = {"vibration": 0.5}
        vec = mapper._extract_modality_vector(state, "vibration", modality_dim=5)
        assert vec.shape == (5,)
        assert np.isclose(vec[0], 0.5)
        assert np.allclose(vec[1:], 0.0)


class TestModalityEMA:
    """Test exponential moving average for modality vectors."""

    def test_add_modality_ema_updates_existing(self):
        """EMA: new = 0.9*old + 0.1*incoming."""
        mapper = SemanticMapper(embedding_dim=4)
        concept = SemanticConcept(concept_id="test", feature_vector=np.zeros(4))

        # First addition
        mapper.add_modality(concept, "vibration", np.array([1.0, 0.0, 0.0, 0.0]))
        assert np.isclose(concept.modality_vectors["vibration"][0], 1.0)

        # Second addition (EMA)
        mapper.add_modality(concept, "vibration", np.array([1.0, 0.0, 0.0, 0.0]))
        # 0.9*1.0 + 0.1*1.0 = 1.0 (same)
        assert np.isclose(concept.modality_vectors["vibration"][0], 1.0)

        # Third: change incoming value
        mapper.add_modality(concept, "vibration", np.array([0.0, 0.0, 0.0, 0.0]))
        # 0.9*1.0 + 0.1*0.0 = 0.9
        assert np.isclose(concept.modality_vectors["vibration"][0], 0.9, atol=1e-6)

    def test_add_modality_creates_new_entry(self):
        mapper = SemanticMapper(embedding_dim=4)
        concept = SemanticConcept(concept_id="test", feature_vector=np.zeros(4))
        vec = np.array([0.5, 0.5, 0.5, 0.5])
        mapper.add_modality(concept, "temperature", vec)
        assert "temperature" in concept.modality_vectors
        assert np.allclose(concept.modality_vectors["temperature"], vec)


class TestModalityInMap:
    """Test that map() populates modality_vectors when registry is connected."""

    def test_map_extracts_modalities_if_registry_present(self):
        """When concept_registry is set, map should extract modality vectors."""
        mapper = SemanticMapper(embedding_dim=16)
        state = {
            "vibration": 0.3,
            "temperature": 22.5,
        }
        concept = mapper.map(state)
        # modality_vectors should be populated (even if empty vectors)
        assert isinstance(concept.modality_vectors, dict)
        # Vibration key present
        assert "vibration" in concept.modality_vectors
        assert concept.modality_vectors["vibration"].shape == (16,)

    def test_map_legacy_feature_vector_unchanged(self):
        """Legacy feature_vector should still contain all raw values."""
        mapper = SemanticMapper(embedding_dim=8)
        state = {"vibration": 0.1, "temperature": 22.0}
        concept = mapper.map(state)
        assert concept.feature_vector.shape == (8,)
        # First two elements should be the state values
        assert np.isclose(concept.feature_vector[0], 0.1)
        assert np.isclose(concept.feature_vector[1], 22.0)
