"""
Flow Router — Routes the Three Flows
Physical flow, info flow, value flow between nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from cosmic_mycelium.common.data_packet import CosmicPacket


@dataclass
class Route:
    """A routing entry."""
    source: str
    destination: str
    flow_type: str
    weight: float = 1.0
    last_used: float = 0.0


class FlowRouter:
    """
    Routes packets through the mycelium network.

    Three flow types are handled differently:
      - PHYSICAL: Shortest path, low latency
      - INFO: Broadcast, pheromone-weighted
      - VALUE: Consensus-aware, reliable
    """

    def __init__(self):
        self.routes: Dict[str, Route] = {}
        self.pheromone_map: Dict[str, float] = {}  # path -> strength

    def route(
        self,
        packet: CosmicPacket,
        nodes: List[str],
    ) -> Optional[str]:
        """
        Select next hop for a packet.
        Returns node ID or None if no route.
        """
        flow_type = packet.get_flow_type()

        if flow_type == "physical":
            # Lowest latency route
            return self._route_physical(packet, nodes)
        elif flow_type == "info":
            # Pheromone-weighted broadcast
            return self._route_info(packet, nodes)
        elif flow_type == "value":
            # Consensus-aware routing
            return self._route_value(packet, nodes)
        return None

    def _route_physical(self, packet: CosmicPacket, nodes: List[str]) -> Optional[str]:
        """Physical flow: pick lowest-latency hop."""
        if not nodes:
            return None
        return nodes[0]  # Simplified: first node

    def _route_info(self, packet: CosmicPacket, nodes: List[str]) -> Optional[str]:
        """Info flow: use pheromone trails."""
        if not nodes:
            return None
        # Pick node with strongest pheromone connection
        best_node = None
        best_score = -1
        for node in nodes:
            path = f"{packet.source_id}->{node}"
            score = self.pheromone_map.get(path, 0.1)
            if score > best_score:
                best_score = score
                best_node = node
        return best_node

    def _route_value(self, packet: CosmicPacket, nodes: List[str]) -> Optional[str]:
        """Value flow: route to consensus participants."""
        if not nodes:
            return None
        # In full impl, would consult consensus layer
        return nodes[0]

    def update_pheromone(self, path: str, delta: float) -> None:
        """Update pheromone strength for a path."""
        self.pheromone_map[path] = self.pheromone_map.get(path, 0.1) + delta
        # Evaporate all
        for k in list(self.pheromone_map.keys()):
            self.pheromone_map[k] *= 0.99
            if self.pheromone_map[k] < 0.01:
                del self.pheromone_map[k]
