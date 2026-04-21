"""
Unit Tests: cluster.flow_router — Flow Router
Tests for routing logic across physical, info, and value flows.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.cluster.flow_router import FlowRouter, Route
from cosmic_mycelium.common.data_packet import CosmicPacket


def make_packet(flow_type: str, source: str = "node-a") -> CosmicPacket:
    """Helper: create a packet with specified flow type."""
    p = CosmicPacket(
        timestamp=1234567890.0,
        source_id=source,
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
    """FlowRouter construction."""

    def test_default_initial_state(self):
        """Router starts with empty routes and pheromone map."""
        fr = FlowRouter()
        assert fr.routes == {}
        assert fr.pheromone_map == {}


class TestFlowRouterPhysicalRouting:
    """Physical flow routing (lowest latency)."""

    def test_route_physical_returns_first_node(self):
        """Physical flow picks first node (lowest-latency)."""
        fr = FlowRouter()
        packet = make_packet("physical")
        nodes = ["node-1", "node-2", "node-3"]
        result = fr.route(packet, nodes)
        assert result == "node-1"

    def test_route_physical_empty_nodes(self):
        """Physical flow returns None when no candidates."""
        fr = FlowRouter()
        packet = make_packet("physical")
        result = fr.route(packet, [])
        assert result is None


class TestFlowRouterInfoRouting:
    """Info flow routing (pheromone-weighted)."""

    def test_route_info_picks_highest_pheromone(self):
        """Info flow routes to node with strongest pheromone."""
        fr = FlowRouter()
        fr.pheromone_map = {
            "node-a->node-1": 0.5,
            "node-a->node-2": 0.9,
            "node-a->node-3": 0.3,
        }
        packet = make_packet("info", source="node-a")
        nodes = ["node-1", "node-2", "node-3"]
        assert fr.route(packet, nodes) == "node-2"

    def test_route_info_default_score_when_no_pheromone(self):
        """Info flow uses default 0.1 for paths without pheromone."""
        fr = FlowRouter()
        packet = make_packet("info", source="node-a")
        nodes = ["node-x", "node-y"]
        # Both have default 0.1 → picks first encountered
        assert fr.route(packet, nodes) == "node-x"

    def test_route_info_empty_nodes(self):
        """Info flow returns None when no candidates."""
        fr = FlowRouter()
        packet = make_packet("info")
        assert fr.route(packet, []) is None


class TestFlowRouterValueRouting:
    """Value flow routing (consensus-aware)."""

    def test_route_value_returns_first_node(self):
        """Value flow currently simplified: picks first node."""
        fr = FlowRouter()
        packet = make_packet("value")
        nodes = ["consensus-1", "consensus-2"]
        assert fr.route(packet, nodes) == "consensus-1"

    def test_route_value_empty_nodes(self):
        """Value flow returns None when no candidates."""
        fr = FlowRouter()
        packet = make_packet("value")
        assert fr.route(packet, []) is None


class TestFlowRouterUnknownFlow:
    """Unknown flow types return None."""

    def test_route_unknown_flow(self):
        """Packet with no recognized flow type returns None."""
        fr = FlowRouter()
        packet = CosmicPacket(timestamp=1.0, source_id="node-a")
        assert fr.route(packet, ["node-1"]) is None


class TestFlowRouterPheromoneUpdate:
    """Pheromone trail updates and evaporation."""

    def test_update_pheromone_increments_existing(self):
        """update_pheromone adds delta, then evaporates all trails (including updated)."""
        fr = FlowRouter()
        fr.pheromone_map["a->b"] = 0.5
        fr.update_pheromone("a->b", 0.3)
        # set to 0.8 first, then evaporate * 0.99 → 0.792
        assert fr.pheromone_map["a->b"] == pytest.approx(0.792)

    def test_update_pheromone_initializes_new(self):
        """update_pheromone initializes missing path with base 0.1 + delta, then evaporates."""
        fr = FlowRouter()
        fr.update_pheromone("x->y", 0.4)
        # 0.1 + 0.4 = 0.5, then * 0.99 = 0.495
        assert fr.pheromone_map["x->y"] == pytest.approx(0.495)

    def test_update_pheromone_evaporates_all(self):
        """Each update evaporates all pheromone trails by 0.99 factor."""
        fr = FlowRouter()
        fr.pheromone_map = {
            "a->b": 1.0,
            "c->d": 2.0,
        }
        fr.update_pheromone("a->b", 0.0)
        assert fr.pheromone_map["a->b"] == 0.99  # 1.0 * 0.99
        assert fr.pheromone_map["c->d"] == 1.98  # 2.0 * 0.99

    def test_update_pheromone_removes_weak_trails(self):
        """Trails dropping below 0.01 are removed."""
        fr = FlowRouter()
        fr.pheromone_map["weak"] = 0.005
        fr.update_pheromone("other", 0.0)
        assert "weak" not in fr.pheromone_map
