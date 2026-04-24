"""
Unit tests for cluster workspace subscription to SuperBrain regions (Phase 3 P2).

Tests that when cluster global workspace updates, all SuperBrain regions
are notified (not just meta and source), enabling distributed cognition.

TDD coverage:
- All regions receive cluster workspace content in working_memory
- Region activation boosts based on relevance
- Source region gets extra boost
- Meta region logs full ClusterWorkspaceState
- Iteration counter tracked correctly
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
from cosmic_mycelium.infant.core.layer_5_superbrain import SuperBrain, BrainRegion


@pytest.fixture
def superbrain_with_regions():
    """Create a SuperBrain with all 5 default regions."""
    brain = SuperBrain()
    return brain


@pytest.fixture
def collective_with_workspace():
    """Create CollectiveIntelligence with a cluster workspace state."""
    ci = CollectiveIntelligence(node_id="node-a")
    # Create a mock workspace state
    from cosmic_mycelium.cluster.collective_intelligence import ClusterWorkspaceState
    ci.workspace = ClusterWorkspaceState(
        content={"type": "proposal_outcome", "decision": "sync_breathing"},
        source_node="node-b",
        source_region="sensory",
        priority=0.8,
        timestamp=1000.0,
        iteration=5,
    )
    ci._iteration = 5
    return ci


class TestWorkspaceSubscription:
    """Tests for SuperBrain region subscription to cluster workspace updates."""

    def test_integrate_notifies_all_regions(self, superbrain_with_regions, collective_with_workspace):
        """All regions should receive cluster workspace entry in working_memory."""
        brain = superbrain_with_regions
        ci = collective_with_workspace

        initial_memories = {
            name: len(region.working_memory)
            for name, region in brain.regions.items()
        }

        ci.integrate_cluster_workspace(brain)

        # Every region should have at least one new entry
        for name, region in brain.regions.items():
            assert len(region.working_memory) > initial_memories[name], \
                f"Region {name} was not notified of cluster workspace update"

    def test_source_region_gets_extra_activation_boost(self, superbrain_with_regions, collective_with_workspace):
        """Source region (sensory) receives +0.2 activation boost."""
        brain = superbrain_with_regions
        ci = collective_with_workspace

        sensory = brain.regions["sensory"]
        initial_activation = sensory.activation

        ci.integrate_cluster_workspace(brain)

        assert sensory.activation > initial_activation
        assert sensory.activation == initial_activation + 0.2

    def test_meta_region_gets_extra_activation_boost(self, superbrain_with_regions, collective_with_workspace):
        """Meta region receives +0.3 activation boost for cluster integration."""
        brain = superbrain_with_regions
        ci = collective_with_workspace

        meta = brain.regions["meta"]
        initial_activation = meta.activation

        ci.integrate_cluster_workspace(brain)

        assert meta.activation > initial_activation
        assert meta.activation == initial_activation + 0.3

    def test_workspace_iteration_tracked(self, superbrain_with_regions, collective_with_workspace):
        """SuperBrain can track cluster workspace iteration for chaining."""
        brain = superbrain_with_regions
        ci = collective_with_workspace

        # Meta region stores full workspace state with iteration
        meta = brain.regions["meta"]
        ci.integrate_cluster_workspace(brain)

        # Check meta memory contains cluster_workspace entry with iteration
        cluster_entries = [
            m for m in meta.working_memory
            if isinstance(m, dict) and "cluster_workspace" in m
        ]
        assert len(cluster_entries) > 0
        assert cluster_entries[-1]["cluster_workspace"]["iteration"] == 5

    def test_integration_returns_true_on_success(self, superbrain_with_regions, collective_with_workspace):
        """integrate_cluster_workspace returns True when workspace exists."""
        brain = superbrain_with_regions
        ci = collective_with_workspace

        result = ci.integrate_cluster_workspace(brain)
        assert result is True

    def test_integration_returns_false_when_no_workspace(self, superbrain_with_regions):
        """Returns False if collective has no active workspace."""
        brain = superbrain_with_regions
        ci = CollectiveIntelligence(node_id="node-a")
        # ci.workspace is None by default

        result = ci.integrate_cluster_workspace(brain)
        assert result is False

    def test_region_activation_capped_at_max(self, superbrain_with_regions):
        """Region activation never exceeds 1.0 after boost."""
        brain = superbrain_with_regions
        ci = CollectiveIntelligence(node_id="node-a")

        # Set all regions near max
        for region in brain.regions.values():
            region.activation = 0.95

        from cosmic_mycelium.cluster.collective_intelligence import ClusterWorkspaceState
        ci.workspace = ClusterWorkspaceState(
            content={"test": "data"},
            source_node="node-b",
            source_region="predictor",
            priority=0.9,
            timestamp=1000.0,
            iteration=1,
        )

        ci.integrate_cluster_workspace(brain)

        for region in brain.regions.values():
            assert region.activation <= 1.0
