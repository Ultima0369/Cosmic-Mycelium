"""
Unit Tests: cluster.node_manager — Node Manager
Tests for cluster node lifecycle and status reporting.
"""

from __future__ import annotations

import time
import pytest
from cosmic_mycelium.cluster.node_manager import NodeManager, InfantNode


class TestNodeManagerInitialization:
    """NodeManager construction and defaults."""

    def test_default_parameters(self):
        """Default min/max node limits are sensible."""
        nm = NodeManager()
        assert nm.min_nodes == 3
        assert nm.max_nodes == 100
        assert nm.nodes == {}
        assert not nm.running

    def test_custom_parameters(self):
        """Custom limits are accepted."""
        nm = NodeManager(min_nodes=1, max_nodes=10)
        assert nm.min_nodes == 1
        assert nm.max_nodes == 10


class TestNodeManagerNodeLifecycle:
    """Node spawn/remove operations."""

    def test_start_stop(self):
        """start() and stop() toggle running flag."""
        nm = NodeManager()
        assert not nm.running
        nm.start()
        assert nm.running
        nm.stop()
        assert not nm.running

    def test_spawn_node_success(self):
        """spawn_node creates new InfantNode and returns True."""
        nm = NodeManager(max_nodes=5)
        result = nm.spawn_node("node-001")
        assert result is True
        assert "node-001" in nm.nodes
        node = nm.nodes["node-001"]
        assert node.node_id == "node-001"
        assert node.address == "node-001:8000"
        assert node.energy == 100.0
        assert node.status == "active"

    def test_spawn_node_fails_at_max(self):
        """spawn_node returns False when at max_nodes limit."""
        nm = NodeManager(max_nodes=2)
        nm.spawn_node("node-001")
        nm.spawn_node("node-002")
        result = nm.spawn_node("node-003")
        assert result is False
        assert "node-003" not in nm.nodes

    def test_remove_node(self):
        """remove_node removes node from registry."""
        nm = NodeManager()
        nm.spawn_node("node-001")
        assert "node-001" in nm.nodes
        nm.remove_node("node-001")
        assert "node-001" not in nm.nodes

    def test_remove_nonexistent_node_no_error(self):
        """remove_node on missing node_id does not raise."""
        nm = NodeManager()
        nm.remove_node("does-not-exist")  # Should not raise


class TestNodeManagerClusterStatus:
    """Cluster health snapshot."""

    def test_get_cluster_status_empty(self):
        """Empty cluster returns zero counts."""
        nm = NodeManager()
        status = nm.get_cluster_status()
        assert status["total_nodes"] == 0
        assert status["active_nodes"] == 0
        assert status["total_energy"] == 0
        assert status["physics_anchor_ok"] is True

    def test_get_cluster_status_mixed_nodes(self):
        """Status aggregates node counts and energy correctly."""
        nm = NodeManager()
        nm.spawn_node("node-a")
        nm.spawn_node("node-b")
        # Manually adjust node state for test
        nm.nodes["node-a"].energy = 50.0
        nm.nodes["node-b"].energy = 30.0
        nm.nodes["node-b"].status = "inactive"

        status = nm.get_cluster_status()
        assert status["total_nodes"] == 2
        assert status["active_nodes"] == 1
        assert status["total_energy"] == 80.0
