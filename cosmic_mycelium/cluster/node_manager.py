"""
Cluster Node Manager
Manages multiple infant nodes in a mycelium network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import asyncio
import time

from cosmic_mycelium.cluster.flow_router import FlowRouter
from cosmic_mycelium.cluster.consensus import Consensus


@dataclass
class InfantNode:
    """Registered infant node."""
    node_id: str
    address: str
    last_seen: float
    energy: float
    status: str = "active"


class NodeManager:
    """
    Manages cluster of infant nodes.
    Handles discovery, health monitoring, and coordination.
    """

    def __init__(
        self,
        min_nodes: int = 3,
        max_nodes: int = 100,
    ):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.nodes: Dict[str, InfantNode] = {}
        self.flow_router = FlowRouter()
        self.consensus = Consensus()
        self.running = False

    async def start(self) -> None:
        """Start node manager."""
        self.running = True

    async def stop(self) -> None:
        """Stop node manager."""
        self.running = False

    async def spawn_node(self, node_id: str) -> bool:
        """Spawn a new infant node."""
        if len(self.nodes) >= self.max_nodes:
            return False
        node = InfantNode(
            node_id=node_id,
            address=f"{node_id}:8000",
            last_seen=time.time(),
            energy=100.0,
        )
        self.nodes[node_id] = node
        return True

    def remove_node(self, node_id: str) -> None:
        """Remove node from cluster."""
        self.nodes.pop(node_id, None)

    def get_cluster_status(self) -> Dict:
        """Cluster health snapshot."""
        active = sum(1 for n in self.nodes.values() if n.status == "active")
        total_energy = sum(n.energy for n in self.nodes.values())
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": active,
            "total_energy": total_energy,
            "physics_anchor_ok": True,
            "avg_resonance": 0.85,
        }
