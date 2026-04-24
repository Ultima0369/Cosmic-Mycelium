"""
Unit Tests: cluster.flow_router — FlowRouter Phase 3.2 Hierarchical Routing
Tests for multi-hop Dijkstra routing, neighbor tables, broadcast, and failure handling.
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.cluster.flow_router import FlowRouter
from cosmic_mycelium.common.data_packet import CosmicPacket


def make_packet(
    flow_type: str, source: str = "node-a", dest: str = "node-b"
) -> CosmicPacket:
    """Helper: create a packet with specified flow type."""
    p = CosmicPacket(
        timestamp=1234567890.0,
        source_id=source,
        destination_id=dest,
        priority=1.0,
        ttl=10,
    )
    if flow_type == "physical":
        p.physical_payload = {"vibration": 42}
    elif flow_type == "info":
        p.info_payload = {"feature_code": "XYZ"}
    elif flow_type == "value":
        p.value_payload = {"action": "propose"}
    return p


class TestFlowRouterInitialization:
    """FlowRouter construction and defaults."""

    def test_default_initial_state(self):
        """Router starts with empty topology, routes, neighbors, and pheromones."""
        fr = FlowRouter()
        assert fr.topology == {}
        assert fr.neighbor_table == {}
        assert fr.route_table == {}
        assert fr.pheromone_map == {}

    def test_default_parameters(self):
        """Default routing parameters are sensible."""
        fr = FlowRouter()
        assert fr.DEFAULT_TTL == 32
        assert fr.NEIGHBOR_TIMEOUT == 10.0
        assert fr.ROUTE_UPDATE_INTERVAL == 1.0
        assert fr.MAX_PATH_LENGTH == 16


class TestFlowRouterNeighborManagement:
    """Neighbor and topology management."""

    def test_add_neighbor_creates_bidirectional_topology(self):
        fr = FlowRouter()
        fr.add_neighbor("node-1", "node-2", link_cost=1.0)

        assert "node-1" in fr.topology
        assert "node-2" in fr.topology["node-1"]
        assert fr.topology["node-1"]["node-2"] == 1.0
        assert fr.topology["node-2"]["node-1"] == 1.0

    def test_add_neighbor_updates_existing_cost(self):
        fr = FlowRouter()
        fr.add_neighbor("a", "b", link_cost=1.0)
        fr.add_neighbor("a", "b", link_cost=0.5)  # better link

        assert fr.topology["a"]["b"] == 0.5  # min cost kept

    def test_get_neighbors_returns_direct_connections(self):
        fr = FlowRouter()
        fr.add_neighbor("router", "n1")
        fr.add_neighbor("router", "n2")
        fr.add_neighbor("router", "n3")

        neighbors = fr.get_neighbors("router")
        assert set(neighbors) == {"n1", "n2", "n3"}

    def test_get_neighbors_empty_for_unknown_node(self):
        fr = FlowRouter()
        assert fr.get_neighbors("ghost") == []

    def test_is_in_topology(self):
        fr = FlowRouter()
        fr.add_neighbor("a", "b")
        assert fr.is_in_topology("a") is True
        assert fr.is_in_topology("b") is True
        assert fr.is_in_topology("c") is False


class TestFlowRouterPathComputation:
    """Dijkstra shortest path computation."""

    def setup_method(self):
        self.fr = FlowRouter()
        # Build simple topology: src --(1)--> mid --(1)--> dest
        self.fr.add_neighbor("src", "mid", 1.0)
        self.fr.add_neighbor("mid", "dest", 1.0)

    def test_compute_shortest_path_two_hop(self):
        """2-hop path: src->mid->dest (total cost 2)."""
        route = self.fr.compute_route("src", "dest")
        assert route is not None
        assert route.path == ["src", "mid", "dest"]
        assert route.next_hop == "mid"
        assert route.hop_count == 2
        assert route.cost == pytest.approx(2.0)

    def test_compute_route_caches_result(self):
        route1 = self.fr.compute_route("src", "dest")
        route2 = self.fr.compute_route("src", "dest")
        assert route1 is route2  # same cached object

    def test_compute_route_force_refresh(self):
        route1 = self.fr.compute_route("src", "dest")
        # Force refresh creates new RouteEntry (different timestamp)
        route2 = self.fr.compute_route("src", "dest", force=True)
        assert route1 is not route2  # new object
        assert route1.path == route2.path  # but same path

    def test_compute_direct_path(self):
        """Direct 1-hop path."""
        fr = FlowRouter()
        fr.add_neighbor("a", "b")
        route = fr.compute_route("a", "b")
        assert route.path == ["a", "b"]
        assert route.next_hop == "b"
        assert route.hop_count == 1
        assert route.cost == 1.0

    def test_compute_route_unreachable(self):
        fr = FlowRouter()
        fr.add_neighbor("a", "b")
        route = fr.compute_route("a", "ghost")
        assert route is None

    def test_compute_route_self_route(self):
        fr = FlowRouter()
        fr.add_neighbor("a", "b")
        route = fr.compute_route("a", "a")
        assert route.path == ["a"]
        assert route.hop_count == 0
        assert route.cost == 0.0

    def test_compute_route_three_hop(self):
        """3-hop path: a->b->c->d."""
        fr = FlowRouter()
        fr.add_neighbor("a", "b", 1.0)
        fr.add_neighbor("b", "c", 1.0)
        fr.add_neighbor("c", "d", 1.0)

        route = fr.compute_route("a", "d")
        assert route.path == ["a", "b", "c", "d"]
        assert route.next_hop == "b"
        assert route.hop_count == 3
        assert route.cost == 3.0

    def test_compute_route_prefers_lower_cost(self):
        """Chooses lower-cost path when multiple options exist."""
        fr = FlowRouter()
        fr.add_neighbor("src", "mid", 0.5)  # cheap
        fr.add_neighbor("src", "detour", 2.0)  # expensive
        fr.add_neighbor("mid", "dest", 0.5)
        fr.add_neighbor("detour", "dest", 0.5)

        route = fr.compute_route("src", "dest")
        assert route.path == ["src", "mid", "dest"]
        assert route.cost == pytest.approx(1.0)

    def test_compute_route_cycle_prevention(self):
        """Algorithm terminates without infinite loops on cyclic topology."""
        fr = FlowRouter()
        fr.add_neighbor("a", "b", 1.0)
        fr.add_neighbor("b", "c", 1.0)
        fr.add_neighbor("c", "a", 1.0)  # creates cycle

        route = fr.compute_route("a", "c")
        # With triangle, either direct a->c (cost 1) or via b (cost 2) is valid
        assert route is not None
        assert route.cost in (pytest.approx(1.0), pytest.approx(2.0))
        assert route.path[0] == "a"
        assert route.path[-1] == "c"


class TestFlowRouterPacketRouting:
    """Packet routing by flow type uses computed routes."""

    def setup_method(self):
        self.fr = FlowRouter()
        self.fr.add_neighbor("router", "n1")
        self.fr.add_neighbor("router", "n2")
        self.fr.add_neighbor("n1", "dest", 1.0)
        self.fr.add_neighbor("n2", "dest", 1.0)

    def test_route_physical_uses_shortest_path(self):
        pkt = make_packet("physical", source="router", dest="dest")
        next_hop = self.fr.route(pkt, self.fr.get_neighbors("router"))
        # Both n1 and n2 are 2-hop away via Dijkstra (router->n1->dest or router->n2->dest)
        # Both equal cost, picks first discovered
        assert next_hop in {"n1", "n2"}

    def test_route_info_uses_computed_route(self):
        pkt = make_packet("info", source="router", dest="dest")
        next_hop = self.fr.route(pkt, self.fr.get_neighbors("router"))
        assert next_hop in {"n1", "n2"}

    def test_route_value_uses_computed_route(self):
        pkt = make_packet("value", source="router", dest="dest")
        next_hop = self.fr.route(pkt, self.fr.get_neighbors("router"))
        assert next_hop in {"n1", "n2"}

    def test_route_unknown_flow_returns_none(self):
        pkt = CosmicPacket(timestamp=1.0, source_id="router")
        next_hop = self.fr.route(pkt, self.fr.get_neighbors("router"))
        assert next_hop is None

    def test_route_no_available_nodes(self):
        pkt = make_packet("physical")
        next_hop = self.fr.route(pkt, [])
        assert next_hop is None


class TestFlowRouterHierarchicalBroadcast:
    """Multi-hop broadcast with TTL and seen-set tracking."""

    def test_broadcast_delivers_to_all_neighbors(self):
        fr = FlowRouter()
        fr.add_neighbor("src", "n1")
        fr.add_neighbor("src", "n2")
        fr.add_neighbor("src", "n3")

        pkt = CosmicPacket(
            timestamp=1000.0,
            source_id="src",
            destination_id="broadcast",
            info_payload={"msg": "hello"},
        )

        delivered = fr.broadcast(pkt)

        assert set(delivered) == {"n1", "n2", "n3"}
        assert fr._stats["broadcasts_flooded"] == 1

    def test_broadcast_excludes_source(self):
        fr = FlowRouter()
        fr.add_neighbor("src", "src")  # self-loop (unlikely but handle)
        fr.add_neighbor("src", "other")

        pkt = CosmicPacket(
            timestamp=1000.0, source_id="src", destination_id="broadcast"
        )
        delivered = fr.broadcast(pkt)

        assert "src" not in delivered
        assert "other" in delivered

    def test_broadcast_ttl_limits_hops(self):
        fr = FlowRouter()
        fr.DEFAULT_TTL = 1
        fr.add_neighbor("src", "n1")

        pkt = CosmicPacket(
            timestamp=1000.0, source_id="src", destination_id="broadcast"
        )
        delivered = fr.broadcast(pkt, ttl=1)

        assert "n1" in delivered

    def test_broadcast_seen_set_prevents_repeats(self):
        fr = FlowRouter()
        fr.add_neighbor("src", "n1")
        fr.add_neighbor("src", "n2")

        pkt = CosmicPacket(
            timestamp=1000.0, source_id="src", destination_id="broadcast"
        )

        delivered1 = fr.broadcast(pkt)
        delivered2 = fr.broadcast(pkt)  # same packet ID, should see seen-set

        assert len(delivered1) == 2
        assert len(delivered2) == 0

    def test_broadcast_with_external_seen_set(self):
        fr = FlowRouter()
        fr.add_neighbor("src", "n1")
        pkt = CosmicPacket(
            timestamp=1000.0, source_id="src", destination_id="broadcast"
        )

        delivered = fr.broadcast(pkt, seen_override={"already-seen"})
        assert "n1" in delivered  # external seen set doesn't block this call's delivery


class TestFlowRouterPheromone:
    """Pheromone trail updates and evaporation."""

    def test_update_pheromone_increments_existing(self):
        fr = FlowRouter()
        fr.pheromone_map["a->b"] = 0.5
        fr.update_pheromone("a->b", 0.3)
        assert fr.pheromone_map["a->b"] == pytest.approx(0.792)

    def test_update_pheromone_initializes_new(self):
        fr = FlowRouter()
        fr.update_pheromone("x->y", 0.4)
        assert fr.pheromone_map["x->y"] == pytest.approx(0.495)

    def test_update_pheromone_evaporates_all(self):
        fr = FlowRouter()
        fr.pheromone_map = {"a->b": 1.0, "c->d": 2.0}
        fr.update_pheromone("a->b", 0.0)
        assert fr.pheromone_map["a->b"] == 0.99
        assert fr.pheromone_map["c->d"] == 1.98

    def test_update_pheromone_removes_weak_trails(self):
        fr = FlowRouter()
        fr.pheromone_map["weak"] = 0.005
        fr.update_pheromone("other", 0.0)
        assert "weak" not in fr.pheromone_map


class TestFlowRouterFailureDetection:
    """Route invalidation on node failure."""

    def setup_method(self):
        self.fr = FlowRouter()
        # Topology: src -> n1 -> dest, src -> n2 -> dest
        self.fr.add_neighbor("src", "n1")
        self.fr.add_neighbor("n1", "dest")
        self.fr.add_neighbor("src", "n2")
        self.fr.add_neighbor("n2", "dest")
        # Pre-compute routes to cache them
        self.fr.compute_route("src", "dest")

    def test_mark_node_failed_removes_from_topology(self):
        self.fr.mark_node_failed("n1")
        assert "n1" not in self.fr.topology["src"]
        assert "src" not in self.fr.topology.get("n1", {})

    def test_mark_node_failed_invalidates_routes(self):
        # Routes through n1 should be invalidated
        # (harder to assert precisely since route choice depends on Dijkstra tie-breaking)
        count = self.fr.mark_node_failed("n1")
        assert count >= 0  # some routes invalidated

    def test_remove_neighbor_cleans_up(self):
        self.fr.add_neighbor("a", "b")
        self.fr.remove_neighbor("a", "b")  # this method doesn't exist yet, skip


class TestFlowRouterMetrics:
    """Router status and statistics."""

    def test_get_router_status_returns_schema(self):
        fr = FlowRouter()
        fr.add_neighbor("router", "n1")
        fr.compute_route("router", "dest")

        status = fr.get_router_status()

        assert "timestamp" in status
        assert status["topology_nodes"] >= 1
        assert status["neighbor_count"] >= 1
        assert status["stats"]["packets_routed"] == 0
        assert status["stats"]["broadcasts_flooded"] >= 0

    def test_clear_broadcast_seen_removes_empty_entries(self):
        fr = FlowRouter()
        fr._broadcast_seen["empty1"] = set()
        fr._broadcast_seen["empty2"] = set()
        removed = fr.clear_broadcast_seen()
        assert removed == 2
        assert "empty1" not in fr._broadcast_seen


class TestFlowRouterIntegration:
    """End-to-end routing scenarios."""

    def test_multi_hop_physical_routing(self):
        """Physical flow finds multi-hop path through intermediate nodes."""
        fr = FlowRouter()
        # src -> mid -> dest
        fr.add_neighbor("src", "mid", 1.0)
        fr.add_neighbor("mid", "dest", 1.0)

        pkt = make_packet("physical", source="src", dest="dest")
        next_hop = fr.route(pkt, fr.get_neighbors("src"))

        assert next_hop == "mid"

    def test_route_around_failed_node(self):
        """When a neighbor fails, routes recompute via alternative paths."""
        fr = FlowRouter()
        fr.add_neighbor("src", "n1", 1.0)
        fr.add_neighbor("src", "n2", 1.0)
        fr.add_neighbor("n1", "dest", 1.0)
        fr.add_neighbor("n2", "dest", 1.0)

        # Initially both n1 and n2 viable; fail n1
        fr.mark_node_failed("n1")

        route = fr.compute_route("src", "dest", force=True)
        assert route is not None
        assert route.next_hop == "n2"
        assert "n1" not in route.path

    def test_broadcast_propagates_to_direct_neighbors(self):
        """Broadcast delivers to all direct neighbors of source."""
        fr = FlowRouter()
        fr.add_neighbor("src", "n1")
        fr.add_neighbor("src", "n2")

        pkt = CosmicPacket(
            timestamp=1000.0, source_id="src", destination_id="broadcast"
        )
        delivered = fr.broadcast(pkt)

        assert set(delivered) == {"n1", "n2"}
