"""
Integration Tests: Cluster Scale — Multi-Node Symbiosis
Tests node lifecycle, consensus across nodes, and cluster health aggregation.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.cluster.node_manager import NodeManager, InfantNode
from cosmic_mycelium.cluster.consensus import Consensus, Proposal
from cosmic_mycelium.cluster.flow_router import FlowRouter


@pytest.mark.asyncio
class TestClusterMultiNodeLifecycle:
    """Multi-node cluster operations."""

    async def test_cluster_spawn_and_status(self):
        """Spawn multiple nodes and verify cluster status aggregates correctly."""
        nm = NodeManager(min_nodes=3, max_nodes=10)
        assert nm.get_cluster_status()["total_nodes"] == 0

        # Spawn 3 nodes
        for i in range(3):
            nm.spawn_node(f"node-{i:03d}")

        status = nm.get_cluster_status()
        assert status["total_nodes"] == 3
        assert status["active_nodes"] == 3
        assert status["total_energy"] == 300.0  # 3 * 100.0

    async def test_node_join_and_leave(self):
        """Node can join cluster and be removed cleanly."""
        nm = NodeManager()
        nm.spawn_node("join-1")
        assert "join-1" in nm.nodes

        nm.remove_node("join-1")
        assert "join-1" not in nm.nodes
        status = nm.get_cluster_status()
        assert status["total_nodes"] == 0

    async def test_cluster_enforces_max_nodes(self):
        """Cluster respects max_nodes limit."""
        nm = NodeManager(max_nodes=3)
        assert nm.spawn_node("n1")
        assert nm.spawn_node("n2")
        assert nm.spawn_node("n3")
        assert not nm.spawn_node("n4")  # Rejected


class TestClusterConsensusAcrossNodes:
    """Consensus protocol across multiple nodes."""

    def test_proposal_reaches_consensus_when_threshold_met(self):
        """Consensus returns True once enough votes are in favor."""
        consensus = Consensus(threshold=0.6)  # 60% of votes cast
        prop = Proposal("p1", "node-a", "symbiosis", {})
        consensus.propose(prop)

        # First yes vote: 1/1 = 100% >= 60% → consensus
        assert consensus.vote("p1", "v1", True) is True

        # Add a no vote: 1/2 = 50% < 60% → no consensus now
        assert consensus.vote("p1", "v2", False) is False

        # Add another yes: 2/3 = 67% >= 60% → consensus again
        assert consensus.vote("p1", "v3", True) is True

    def test_symbiotic_relationship_between_two_nodes(self):
        """Two nodes record symbiosis and recognize each other bidirectionally."""
        consensus = Consensus()
        consensus.record_symbiosis("node-a", "node-b")
        assert consensus.is_symbiotic("node-a", "node-b")
        assert consensus.is_symbiotic("node-b", "node-a")

    def test_consensus_rejects_unknown_proposal(self):
        """Voting on non-existent proposal returns False."""
        consensus = Consensus()
        assert consensus.vote("fake-id", "voter", True) is False


class TestClusterRoutingAcrossNodes:
    """Flow routing across cluster nodes."""

    def test_physical_routing_consistency(self):
        """Physical flow always picks first node (deterministic)."""
        fr = FlowRouter()
        from cosmic_mycelium.common.data_packet import CosmicPacket
        pkt = CosmicPacket(timestamp=1.0, source_id="node-a", physical_payload={})
        nodes = ["n1", "n2", "n3"]
        assert fr.route(pkt, nodes) == "n1"

    def test_info_routing_uses_pheromone_weights(self):
        """Info flow selects highest-pheromone neighbor."""
        fr = FlowRouter()
        fr.pheromone_map = {
            "node-a->n1": 0.3,
            "node-a->n2": 0.8,
            "node-a->n3": 0.5,
        }
        from cosmic_mycelium.common.data_packet import CosmicPacket
        pkt = CosmicPacket(timestamp=1.0, source_id="node-a", info_payload={})
        assert fr.route(pkt, ["n1", "n2", "n3"]) == "n2"


class TestClusterResilience:
    """Cluster resilience patterns."""

    def test_node_failure_does_not_cascade(self):
        """Removing a node doesn't break cluster status computation."""
        nm = NodeManager(max_nodes=5)
        for i in range(5):
            nm.spawn_node(f"node-{i}")

        # Kill one node
        nm.remove_node("node-2")
        status = nm.get_cluster_status()
        assert status["total_nodes"] == 4
        assert status["active_nodes"] == 4
        assert status["total_energy"] == 400.0

    def test_cluster_status_always_returns_valid_numbers(self):
        """Cluster status is always a valid dict with expected keys and types."""
        nm = NodeManager()
        status = nm.get_cluster_status()
        required_keys = {"total_nodes", "active_nodes", "total_energy", "physics_anchor_ok", "avg_resonance"}
        assert required_keys.issubset(status.keys())
        assert isinstance(status["total_nodes"], int)
        # total_energy can be int or float depending on sum
        assert isinstance(status["total_energy"], (int, float))
        assert status["physics_anchor_ok"] is True
        assert isinstance(status["avg_resonance"], float)
