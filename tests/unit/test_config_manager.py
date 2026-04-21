"""
ConfigManager — Configuration Scoping Tests
Tests the singleton configuration provider for infant/cluster/global scales.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.common.config_manager import ConfigManager


class TestConfigManagerScopes:
    """Tests for for_infant, for_cluster, for_global factory methods."""

    def test_for_infant_has_correct_embedding_dim(self):
        """Infant scope uses embedding_dim=16."""
        cm = ConfigManager.for_infant()
        assert cm.get("semantic_mapper", "embedding_dim") == 16

    def test_for_infant_has_correct_spores(self):
        """Infant scope uses num_spores=10."""
        cm = ConfigManager.for_infant()
        assert cm.get("slime_explorer", "num_spores") == 10

    def test_for_cluster_has_larger_embedding(self):
        """Cluster scope uses embedding_dim=64."""
        cm = ConfigManager.for_cluster()
        assert cm.get("semantic_mapper", "embedding_dim") == 64

    def test_for_global_has_largest_embedding(self):
        """Global scope uses embedding_dim=256."""
        cm = ConfigManager.for_global()
        assert cm.get("semantic_mapper", "embedding_dim") == 256

    def test_get_with_default_fallback(self):
        """get() returns default when key missing."""
        cm = ConfigManager.for_infant()
        assert cm.get("unknown", "key", 999) == 999

    def test_get_without_default_raises(self):
        """get() without default raises KeyError on missing key."""
        cm = ConfigManager.for_infant()
        with pytest.raises(KeyError):
            cm.get("nonexistent", "key")

    def test_as_dict_includes_all_layers(self):
        """as_dict() returns complete configuration snapshot."""
        cm = ConfigManager.for_infant()
        d = cm.as_dict()
        assert "infant" in d
        assert "cluster" in d
        assert "global" in d

    def test_infant_default_values_complete(self):
        """All infant defaults are present and sensible."""
        cm = ConfigManager.for_infant()
        assert cm.get("infant", "energy_max") == 100.0
        assert cm.get("infant", "contract_duration") == 0.055
        assert cm.get("infant", "suspend_duration") == 5.0
        assert cm.get("hic", "recovery_energy") == 60.0
        assert cm.get("slime_explorer", "num_spores") == 10
        assert cm.get("myelination", "max_traces") == 1000
        assert len(cm.get("superbrain", "regions")) == 5
        assert cm.get("symbiosis", "max_partners") == 10
