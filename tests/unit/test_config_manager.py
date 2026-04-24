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
        cm = ConfigManager.for_infant()
        assert cm.get("semantic_mapper", "embedding_dim") == 16

    def test_for_infant_has_correct_spores(self):
        cm = ConfigManager.for_infant()
        assert cm.get("slime_explorer", "num_spores") == 10

    def test_for_cluster_has_larger_embedding(self):
        cm = ConfigManager.for_cluster()
        assert cm.get("semantic_mapper", "embedding_dim") == 64

    def test_for_global_has_largest_embedding(self):
        cm = ConfigManager.for_global()
        assert cm.get("semantic_mapper", "embedding_dim") == 256

    def test_get_with_default_fallback(self):
        cm = ConfigManager.for_infant()
        assert cm.get("unknown", "key", 999) == 999

    def test_get_without_default_raises(self):
        cm = ConfigManager.for_infant()
        with pytest.raises(KeyError):
            cm.get("nonexistent", "key")

    def test_as_dict_includes_all_scales(self):
        cm = ConfigManager.for_infant()
        d = cm.as_dict()
        assert set(d.keys()) == {"infant", "cluster", "global"}

    def test_infant_default_values_complete(self):
        cm = ConfigManager.for_infant()
        assert cm.get("infant", "energy_max") == 100.0
        assert cm.get("infant", "contract_duration") == 0.055
        assert cm.get("infant", "suspend_duration") == 5.0
        assert cm.get("hic", "recovery_energy") == 60.0
        assert cm.get("slime_explorer", "num_spores") == 10
        assert cm.get("myelination", "max_traces") == 1000
        assert len(cm.get("superbrain", "regions")) == 5
        assert cm.get("symbiosis", "max_partners") == 10

    # Branch coverage tests for get() error paths

    def test_get_unknown_layer_returns_default(self):
        cm = ConfigManager.for_infant()
        assert cm.get("not_a_layer", "param", default="default_val") == "default_val"

    def test_get_unknown_layer_raises_keyerror_without_default(self):
        cm = ConfigManager.for_infant()
        with pytest.raises(KeyError) as exc:
            cm.get("not_a_layer", "param")
        assert "Unknown layer" in str(exc.value)

    def test_get_known_layer_missing_param_returns_default(self):
        cm = ConfigManager.for_infant()
        assert cm.get("semantic_mapper", "missing_param_xyz", default=12345) == 12345

    def test_get_known_layer_missing_param_raises_keyerror(self):
        cm = ConfigManager.for_infant()
        with pytest.raises(KeyError) as exc:
            cm.get("semantic_mapper", "missing_param_xyz")
        assert "not found" in str(exc.value).lower()

    def test_get_abstract_segmenter_params(self):
        cm = ConfigManager.for_infant()
        assert cm.get("abstract_segmenter", "windows") == 6

    def test_get_hic_params(self):
        cm = ConfigManager.for_infant()
        assert cm.get("hic", "recovery_rate") == 0.5

    def test_get_invalid_scale_with_default_fallback(self):
        cm = ConfigManager()
        assert cm.get("invalid_scale", "anything", default="fallback") == "fallback"

    def test_get_valid_layer_zero_value_allowed(self):
        cm = ConfigManager.for_infant()
        cm.config.params["test_zero"] = 0.0
        assert cm.get("infant", "test_zero") == 0.0

    def test_as_dict_structure_matches_expected_layers(self):
        cm = ConfigManager.for_infant()
        d = cm.as_dict()
        infant_cfg = d["infant"]
        expected = {
            "params",
            "abstract_segmenter",
            "semantic_mapper",
            "slime_explorer",
            "myelination",
            "superbrain",
            "symbiosis",
        }
        assert expected.issubset(infant_cfg.keys())

    def test_cluster_superbrain_has_consensus_region(self):
        cm = ConfigManager.for_cluster()
        regions = cm.get("superbrain", "regions")
        assert "consensus" in regions
        assert len(regions) == 6

    def test_global_superbrain_has_orchestrator(self):
        cm = ConfigManager.for_global()
        regions = cm.get("superbrain", "regions")
        assert "orchestrator" in regions
        assert len(regions) == 7

    def test_myelination_max_traces_scales_correctly(self):
        assert ConfigManager.for_infant().get("myelination", "max_traces") == 1000
        assert ConfigManager.for_cluster().get("myelination", "max_traces") == 10000
        assert ConfigManager.for_global().get("myelination", "max_traces") == 100000
