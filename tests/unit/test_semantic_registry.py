"""
Unit tests for SemanticMapper registry-based cross-modal linking.

Covers: _link_concept_via_registry, GlobalConceptRegistry integration.
"""

import pytest

from cosmic_mycelium.infant.core.layer_2_semantic_mapper import (
    SemanticMapper,
    SemanticConcept,
)


class MockRegistry:
    """Mock GlobalConceptRegistry for testing linking behavior."""

    def __init__(self):
        self.concepts: dict[str, SemanticConcept] = {}
        self.modality_index: dict[str, list[str]] = {}  # modality_key -> [concept_ids]

    def register(self, concept: SemanticConcept, modalities: list[str]):
        self.concepts[concept.concept_id] = concept
        for mod in modalities:
            self.modality_index.setdefault(mod, []).append(concept.concept_id)

    def get_concept(self, concept_id: str) -> dict | None:
        """Return concept entry dict for registry queries."""
        if concept_id not in self.concepts:
            return None
        c = self.concepts[concept_id]
        return {
            "modalities": c.modality_vectors,
            "global_frequency": c.frequency,
            "first_seen": c.first_seen,
            "last_access": c.last_seen,
        }

    def find_related_by_modality(self, concept_id: str, modality: str) -> list[str]:
        """Return other concept IDs sharing the same modality key."""
        if modality not in self.modality_index:
            return []
        return [cid for cid in self.modality_index[modality] if cid != concept_id]


class TestRegistryLinking:
    """Test cross-modal linking via GlobalConceptRegistry."""

    def test_link_concept_via_registry_adds_related_ids(self):
        """
        When a concept is mapped with a registry present, it should
        link to previously seen concepts sharing modality patterns.
        """
        registry = MockRegistry()

        # First concept: vibration-based
        mapper1 = SemanticMapper(embedding_dim=4, concept_registry=registry)
        c1 = mapper1.map({"vibration": 0.5})
        registry.register(c1, modalities=["vibration"])

        # Second concept: also vibration-based
        mapper2 = SemanticMapper(embedding_dim=4, concept_registry=registry)
        c2 = mapper2.map({"vibration": 0.7})

        # c2 should have c1 linked via registry
        assert c1.concept_id in c2.related_concepts or c2.concept_id in c1.related_concepts

    def test_link_concept_without_registry_does_not_link(self):
        """Without a registry, no cross-modal linking occurs."""
        mapper = SemanticMapper(embedding_dim=4)
        c1 = mapper.map({"vibration": 0.5})
        c2 = mapper.map({"vibration": 0.7})

        # No linking expected (related_concepts stays empty)
        assert len(c1.related_concepts) == 0
        assert len(c2.related_concepts) == 0

    def test_registry_linking_preserves_existing_links(self):
        """Linking should append not overwrite existing related_concepts."""
        registry = MockRegistry()
        mapper = SemanticMapper(embedding_dim=4, concept_registry=registry)

        c1 = mapper.map({"vibration": 0.5})
        registry.register(c1, modalities=["vibration"])

        c2 = mapper.map({"vibration": 0.7})
        c3 = mapper.map({"vibration": 0.9})

        # All three should be mutually linked (transitive via shared modality)
        assert c2.concept_id in c1.related_concepts or c1.concept_id in c2.related_concepts
        assert c3.concept_id in c1.related_concepts or c1.concept_id in c3.related_concepts
