"""
Integration test for Sprint 1 Epic 1: research loop inside infant lifecycles.

Tests that with research enabled, the infant can autonomously generate
questions, execute experiments, and store knowledge entries over cycles.
"""

import pytest

from cosmic_mycelium.infant.main import SiliconInfant


class TestResearchIntegration:
    """Test research capabilities integrated into SiliconInfant."""

    def test_research_enabled_conducts_experiments(self):
        """
        With research enabled, after enough research cycles the infant should
        have generated at least 3 knowledge entries.
        """
        infant = SiliconInfant(
            infant_id="research-test",
            config={
                "embedding_dim": 8,
                "research_enabled": True,
                "energy_max": 100.0,
            },
        )
        assert infant.knowledge_store is not None, "Research components not initialized"
        assert infant._research_enabled is True, "Research not enabled"

        # Ensure energy high enough for research
        infant.hic._energy = 80.0

        # Manually invoke research multiple times (bypassing cycle timing)
        for _ in range(5):
            infant._maybe_research()

        stats = infant.knowledge_store.get_stats()
        assert stats["total_entries"] >= 3, f"Expected >=3 entries, got {stats['total_entries']}"

    def test_research_disabled_does_not_create_entries(self):
        """
        With research disabled, knowledge_store should stay empty.
        """
        infant = SiliconInfant(
            infant_id="no-research-test",
            config={
                "embedding_dim": 8,
                "research_enabled": False,
            },
        )

        for _ in range(20):
            infant.breath_cycle()

        # research_enabled=False → knowledge_store is None
        assert infant.knowledge_store is None

    def test_conduct_research_returns_entry(self):
        """
        Calling _maybe_research directly should create one entry.
        """
        infant = SiliconInfant(
            infant_id="direct-research",
            config={
                "embedding_dim": 8,
                "research_enabled": True,
                "energy_max": 100.0,
            },
        )
        # Ensure energy high enough (bypass read-only property)
        infant.hic._energy = 80.0

        initial_count = infant.knowledge_store.get_stats()["total_entries"]
        infant._maybe_research()
        new_count = infant.knowledge_store.get_stats()["total_entries"]

        assert new_count == initial_count + 1
