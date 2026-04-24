"""
Layer 2 — Semantic Mapper Tests
Tests concept mapping, embedding dimension handling, gradient normalization.
"""

from __future__ import annotations

import importlib
import time
from unittest.mock import MagicMock

import numpy as np

from cosmic_mycelium.common.config_manager import ConfigManager
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import (
    SemanticConcept,
    SemanticMapper,
)


def _import_global_module():
    """Dynamic import to avoid 'global' keyword in module path."""
    return importlib.import_module("cosmic_mycelium.global.access_protocol")


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


class TestCrossModalLinking:
    """Tests for Phase 4.2 cross-modal linking via registry."""

    def setup_method(self):
        mod = _import_global_module()
        self.GlobalConceptRegistry = mod.GlobalConceptRegistry

    def test_cross_modal_link_registered_via_registry(self):
        """Registry entry adds cross-modal link when new modality discovered."""
        registry = self.GlobalConceptRegistry(embedding_dim=8)
        mapper = SemanticMapper(embedding_dim=8, concept_registry=registry)

        # Node 1 observes concept via vibration only
        phys_vib = {"vibration_x": 1.0, "vibration_y": 2.0}
        c1 = mapper.map(phys_vib)
        cid = c1.id

        # Node 2 observes same concept (same fingerprint) via temperature
        # First register the temperature modality in the registry
        registry.register_concept(
            cid,
            "temperature",
            np.array([36.5, 37.0]),
            frequency=1,
        )

        # Now Node 1 observes again — should link temperature modality
        mapper.map(phys_vib)  # Re-observation triggers registry link check

        concept = mapper.concepts[cid]
        assert "temperature" in concept.modality_vectors
        assert any(link.endswith(":temperature") for link in concept.cross_modal_links)

    def test_concept_registry_integration(self):
        """Full round-trip: register → retrieve → align."""
        registry = self.GlobalConceptRegistry(embedding_dim=8)
        mapper = SemanticMapper(embedding_dim=8, concept_registry=registry)

        # Register a vibration-based concept in registry
        test_concept_id = "abcd1234" * 8  # 32-char fake fingerprint
        vib_vec = np.array([1.0, 2.0, 3.0, 4.0])
        registry.register_concept(test_concept_id, "vibration", vib_vec, frequency=5)

        # Query from mapper perspective
        entry = registry.get_concept(test_concept_id)
        assert entry is not None
        assert "vibration" in entry["modalities"]
        assert np.allclose(entry["modalities"]["vibration"], vib_vec)

    def test_find_similar_concepts_by_modality(self):
        """Registry similarity search works within a modality."""
        registry = self.GlobalConceptRegistry(embedding_dim=4)
        ref_id = "ref123"
        ref_vec = np.array([1.0, 0.0, 0.0, 0.0])
        registry.register_concept(ref_id, "vibration", ref_vec, frequency=10)

        # Query with similar vector
        query_vec = np.array([0.9, 0.1, 0.0, 0.0])
        results = registry.find_similar_concepts(query_vec, "vibration", threshold=0.8)

        assert len(results) == 1
        assert results[0][0] == ref_id
        assert results[0][1] > 0.9  # similarity should be high

    def test_cross_modal_links_recorded(self):
        """When registry provides new modality, cross_modal_links list updated."""
        registry = self.GlobalConceptRegistry(embedding_dim=8)
        mapper = SemanticMapper(embedding_dim=8, concept_registry=registry)

        # Concept known only for vibration
        phys = {"vibration_x": 1.0, "vibration_y": 2.0}
        concept = mapper.map(phys)
        cid = concept.id
        assert len(concept.cross_modal_links) == 0

        # Registry adds audio modality for same concept
        audio_vec = np.array([0.5, 0.5])
        registry.register_concept(cid, "audio", audio_vec, frequency=1)

        # Re-map triggers link discovery
        mapper.map(phys)
        concept = mapper.concepts[cid]
        assert "audio" in concept.modality_vectors
        assert any("audio" in link for link in concept.cross_modal_links)


class TestGlobalConceptRegistry:
    """Tests for GlobalConceptRegistry standalone behavior."""

    def setup_method(self):
        mod = _import_global_module()
        self.GlobalConceptRegistry = mod.GlobalConceptRegistry

    def test_register_new_concept_returns_true(self):
        """Registering a previously unknown concept returns True."""
        registry = self.GlobalConceptRegistry()
        result = registry.register_concept("cid1", "vibration", np.array([1.0, 2.0]))
        assert result is True

    def test_register_duplicate_concept_returns_false(self):
        """Registering an existing concept returns False and merges."""
        registry = self.GlobalConceptRegistry()
        registry.register_concept("cid1", "vibration", np.array([1.0, 2.0]))
        result = registry.register_concept("cid1", "vibration", np.array([3.0, 4.0]))
        assert result is False

    def test_ema_merge_on_duplicate_registration(self):
        """Duplicate registration applies EMA (0.9 old + 0.1 new)."""
        registry = self.GlobalConceptRegistry()
        v1 = np.array([10.0, 10.0])
        registry.register_concept("cid1", "vibration", v1, frequency=1)
        v2 = np.array([20.0, 20.0])
        registry.register_concept("cid1", "vibration", v2, frequency=1)

        entry = registry.get_concept("cid1")
        merged = entry["modalities"]["vibration"]
        assert np.allclose(merged, [11.0, 11.0])  # 0.9*10 + 0.1*20

    def test_get_nonexistent_returns_none(self):
        """get_concept returns None for unknown ID."""
        registry = self.GlobalConceptRegistry()
        assert registry.get_concept("unknown") is None

    def test_get_updates_last_access(self):
        """get_concept refreshes last_access timestamp."""
        registry = self.GlobalConceptRegistry()
        registry.register_concept("cid1", "vibration", np.array([1.0]))
        entry1 = registry.get_concept("cid1")
        access1 = entry1["last_access"]
        # Small delay
        time.sleep(0.01)
        entry2 = registry.get_concept("cid1")
        access2 = entry2["last_access"]
        assert access2 > access1

    def test_find_similar_concepts_threshold_filter(self):
        """Only concepts meeting similarity threshold are returned."""
        registry = self.GlobalConceptRegistry(embedding_dim=3)
        registry.register_concept("c1", "vibration", np.array([1.0, 0.0, 0.0]))
        registry.register_concept("c2", "vibration", np.array([0.0, 1.0, 0.0]))

        query = np.array([0.95, 0.0, 0.0])
        results = registry.find_similar_concepts(query, "vibration", threshold=0.9)
        assert len(results) == 1
        assert results[0][0] == "c1"

    def test_get_concepts_by_modality_filters_correctly(self):
        """get_concepts_by_modality returns only matching concept IDs."""
        registry = self.GlobalConceptRegistry()
        registry.register_concept("c1", "vibration", np.array([1.0]))
        registry.register_concept("c2", "temperature", np.array([2.0]))
        registry.register_concept("c3", "vibration", np.array([3.0]))

        vib_ids = registry.get_concepts_by_modality("vibration")
        assert set(vib_ids) == {"c1", "c3"}

    def test_eviction_when_at_capacity(self):
        """LRU eviction triggers when max_concepts reached."""
        registry = self.GlobalConceptRegistry(max_concepts=2)
        registry.register_concept("c1", "vibration", np.array([1.0]))
        time.sleep(0.01)
        registry.register_concept("c2", "temperature", np.array([2.0]))
        time.sleep(0.01)
        registry.register_concept("c3", "audio", np.array([3.0]))  # Should evict c1

        assert registry.get_concept("c1") is None
        assert registry.get_concept("c2") is not None
        assert registry.get_concept("c3") is not None

    def test_get_stats_returns_reasonable_values(self):
        """get_stats provides total concepts, modality distribution, age."""
        registry = self.GlobalConceptRegistry()
        registry.register_concept("c1", "vibration", np.array([1.0]))
        registry.register_concept("c2", "temperature", np.array([2.0]))

        stats = registry.get_stats()
        assert stats["total_concepts"] == 2
        assert stats["modality_distribution"]["vibration"] == 1
        assert stats["modality_distribution"]["temperature"] == 1
        assert stats["capacity"] == 1_000_000
        assert stats["oldest_concept_age_seconds"] >= 0

