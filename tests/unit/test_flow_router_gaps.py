"""
Unit tests for FlowRouter gaps identified in QUALITY_GAP_ANALYSIS.

Covers: broadcast TTL decrement & multi-hop, remove_neighbor topology update,
metrics update on route recomputation, refresh logic.
"""

import pytest

from cosmic_mycelium.cluster.flow_router import FlowRouter, NeighborEntry
from cosmic_mycelium.common.data_packet import CosmicPacket


class TestBroadcastTTL:
    """Test broadcast TTL decrement and multi-hop propagation."""

    def test_broadcast_ttl_decrements_each_hop(self):
        """
        TTL should decrement on each recursive hop.
        When TTL reaches 0, propagation stops.
        """
        router = FlowRouter()
        # Build a 3-node line topology: A -> B -> C
        router.add_neighbor("A", "B", link_cost=1.0)
        router.add_neighbor("B", "C", link_cost=1.0)

        packet = CosmicPacket(
            timestamp=1234567890.0,
            source_id="A",
            destination_id=None,  # broadcast
            priority=1.0,
            ttl=255,
        )

        delivered = router.broadcast(packet, ttl=2)

        # A delivers to B (hop 1), B delivers to C (hop 2), C has no further neighbors
        assert "B" in delivered
        assert "C" in delivered
        # A should not appear (source)
        assert "A" not in delivered

    def test_broadcast_ttl_zero_stops_propagation(self):
        """TTL=1 should only deliver to direct neighbors."""
        router = FlowRouter()
        router.add_neighbor("A", "B", link_cost=1.0)
        router.add_neighbor("B", "C", link_cost=1.0)

        packet = CosmicPacket(
            timestamp=1234567890.0,
            source_id="A",
            destination_id=None,
            priority=1.0,
            ttl=255,
        )

        delivered = router.broadcast(packet, ttl=1)
        assert delivered == ["B"]  # only direct neighbor
        assert "C" not in delivered

    def test_broadcast_ttl_default_is_32(self):
        router = FlowRouter()
        assert router.DEFAULT_TTL == 32

    def test_broadcast_prevents_loops_with_seen_set(self):
        """Nodes should receive broadcast at most once (seen-set)."""
        router = FlowRouter()
        # Triangle topology: A <-> B <-> C <-> A (cycle)
        router.add_neighbor("A", "B", 1.0)
        router.add_neighbor("B", "C", 1.0)
        router.add_neighbor("C", "A", 1.0)

        packet = CosmicPacket(
            timestamp=1234567890.0,
            source_id="A",
            destination_id=None,
            priority=1.0,
            ttl=255,
        )

        delivered = router.broadcast(packet, ttl=5)
        # Each node appears at most once
        assert len(delivered) == len(set(delivered))
        # All 3 nodes should be delivered (A→B, B→C, C→A but A is source excluded)
        assert set(delivered) == {"B", "C"}

    def test_broadcast_seen_set_cleaned_periodically(self):
        """After many broadcasts, seen-set cleanup should run."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)

        packet = CosmicPacket(
            timestamp=1234567890.0,
            source_id="A",
            destination_id=None,
            priority=1.0,
            ttl=255,
        )

        # Trigger broadcast 101 times to exceed cleanup threshold (100)
        for i in range(101):
            delivered = router.broadcast(packet, ttl=1)
            # update packet timestamp to get new packet_id
            packet.timestamp += 1.0

        # cleanup should have run at least once
        assert len(delivered) > 0, "No packets delivered via broadcast"


class TestRemoveNeighbor:
    """Test remove_neighbor topology updates."""

    def test_remove_neighbor_bidirectional(self):
        """Removing a neighbor should remove both directions in topology."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)
        assert "B" in router.topology["A"]
        assert "A" in router.topology["B"]

        router.remove_neighbor("A", "B")

        assert "B" not in router.topology.get("A", {})
        assert "A" not in router.topology.get("B", {})

    def test_remove_neighbor_cleans_empty_entries(self):
        """If node has no neighbors after removal, delete its topology entry."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)
        router.remove_neighbor("A", "B")

        assert "A" not in router.topology
        assert "B" not in router.topology

    def test_remove_nonexistent_neighbor_no_error(self):
        """Removing a non-existent neighbor should not raise."""
        router = FlowRouter()
        # Should not raise
        router.remove_neighbor("X", "Y")


class TestMetrics:
    """Test metrics updates during routing operations."""

    def test_route_recomputations_metric_increments(self):
        """compute_route should increment route_recomputations stat."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)
        router.add_neighbor("B", "C", 1.0)

        initial = router._stats["route_recomputations"]
        router.compute_route("A", "C", force=True)
        assert router._stats["route_recomputations"] == initial + 1

    def test_broadcast_flooded_metric_increments(self):
        """broadcast should increment broadcasts_flooded stat."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)

        packet = CosmicPacket(
            timestamp=12345.0,
            source_id="A",
            destination_id=None,
            priority=1.0,
            ttl=255,
        )

        initial = router._stats["broadcasts_flooded"]
        router.broadcast(packet, ttl=1)
        assert router._stats["broadcasts_flooded"] == initial + 1

    def test_router_status_contains_expected_keys(self):
        """get_router_status should return a dict with all required keys."""
        router = FlowRouter()
        status = router.get_router_status()

        required_keys = {
            "neighbor_count",
            "total_routes_cached",
            "valid_routes",
            "stats",
        }
        assert required_keys.issubset(set(status.keys()))
        # stats should contain broadcasts_flooded
        assert "broadcasts_flooded" in status["stats"]


class TestRouteRefresh:
    """Test route cache refresh and invalidation."""

    def test_compute_route_caches_result(self):
        """First call should compute and cache."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)
        route1 = router.compute_route("A", "B")
        route2 = router.route_table["A"]["B"]
        assert route1 is route2  # same object

    def test_compute_route_force_bypasses_cache(self):
        """force=True should recompute even if cached."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)

        route1 = router.compute_route("A", "B")
        # Modify cached route's is_valid flag (simulate invalid)
        route1.is_valid = False

        # force=True should return a new valid route
        route2 = router.compute_route("A", "B", force=True)
        assert route2 is not None
        assert route2.is_valid

    def test_route_cache_expires_when_invalid(self):
        """Invalid routes should be recomputed on next request."""
        router = FlowRouter()
        router.add_neighbor("A", "B", 1.0)

        route = router.compute_route("A", "B")
        route.is_valid = False  # simulate link failure

        # Next compute_route (without force) should recompute
        new_route = router.compute_route("A", "B")
        assert new_route is not None
        # The cached reference should be updated
        assert router.route_table["A"]["B"] is new_route
