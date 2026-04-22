"""
Mycelium Network — Multi-Infant Cluster
Manages a network of SiliconInfant nodes with message routing,
node discovery, and resonance learning coordination.
"""

from __future__ import annotations

import time
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from collections import deque

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.infant.sensors import SensorArray


@dataclass
class NodeInfo:
    """Metadata about a node in the network."""
    node_id: str
    infant: SiliconInfant
    address: str
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    is_alive: bool = True


class MyceliumNetwork:
    """
    The fungal network connecting silicon infants.

    Responsibilities:
    - Node lifecycle (join, leave, crash detection)
    - Packet routing between infants
    - Physical fingerprint verification
    - Resonance learning coordination
    """

    def __init__(self, name: str = "mycelium"):
        self.name = name
        self.nodes: Dict[str, NodeInfo] = {}
        self._packet_queue: deque[CosmicPacket] = deque()
        self._resonance_history: List[Dict] = []
        self._running = False

    # ----------------------------------------------------------------------
    # Node lifecycle
    # ----------------------------------------------------------------------
    def join(self, infant: SiliconInfant, address: Optional[str] = None) -> str:
        """
        A new infant joins the network.
        Returns the node_id assigned.
        """
        node_id = infant.infant_id
        if address is None:
            address = f"{node_id}:8000"
        self.nodes[node_id] = NodeInfo(
            node_id=node_id,
            infant=infant,
            address=address,
        )
        # Give infant a reference to network for sending
        infant.network = self  # type: ignore[attr-defined]
        return node_id

    def leave(self, node_id: str) -> None:
        """Node gracefully leaves the network."""
        if node_id in self.nodes:
            self.nodes[node_id].is_alive = False
            # Keep for a while for cleanup

    def get_node_ids(self) -> List[str]:
        """List all known node IDs."""
        return list(self.nodes.keys())

    def get_alive_nodes(self) -> List[str]:
        """List nodes currently marked alive."""
        return [nid for nid, info in self.nodes.items() if info.is_alive]

    # ----------------------------------------------------------------------
    # Packet routing
    # ----------------------------------------------------------------------
    def send(self, packet: CosmicPacket) -> None:
        """
        Route a packet to its destination.
        If destination is "broadcast", deliver to all alive nodes.
        """
        dest = packet.destination_id
        if dest == "broadcast":
            for nid in self.get_alive_nodes():
                if nid != packet.source_id:
                    target = self.nodes.get(nid)
                    if target:
                        target.infant.inbox.append(packet)
        else:
            target = self.nodes.get(dest)
            if target and target.is_alive:
                target.infant.inbox.append(packet)
            else:
                # Destination unknown or dead — drop (could queue for later)
                pass

    def deliver_all(self) -> None:
        """Flush queued packets to their destinations."""
        while self._packet_queue:
            pkt = self._packet_queue.popleft()
            self.send(pkt)

    def broadcast(self, source_id: str, value_payload: Dict) -> CosmicPacket:
        """Convenience: create and queue a broadcast packet."""
        pkt = CosmicPacket(
            timestamp=time.time(),
            source_id=source_id,
            destination_id="broadcast",
            value_payload=value_payload,
        )
        self._packet_queue.append(pkt)
        return pkt

    # ----------------------------------------------------------------------
    # Physical fingerprint verification
    # ----------------------------------------------------------------------
    def verify_physical_fingerprint(
        self,
        claimant_id: str,
        fingerprint: str,
        tolerance: float = 1e-6,
    ) -> bool:
        """
        Verify that a node's claimed physical fingerprint is well-formed.
        Full cryptographic verification would require the node's signed state,
        but here we check format and plausibility.
        """
        claimant = self.nodes.get(claimant_id)
        if not claimant:
            return False
        # Basic format: 16 hex characters
        if len(fingerprint) != 16:
            return False
        if not all(c in "0123456789abcdef" for c in fingerprint):
            return False
        # In production, would also cross-check with claimant's published state
        return True

    # ----------------------------------------------------------------------
    # Resonance learning
    # ----------------------------------------------------------------------
    def compute_resonance(
        self,
        node_a_id: str,
        node_b_id: str,
    ) -> Optional[float]:
        """
        Compute cosine similarity between two nodes' semantic embeddings.
        Returns None if either node lacks an embedding.
        """
        node_a = self.nodes.get(node_a_id)
        node_b = self.nodes.get(node_b_id)
        if not node_a or not node_b:
            return None

        # Get latest embeddings directly from infants
        emb_a = node_a.infant.get_embedding()
        emb_b = node_b.infant.get_embedding()
        if emb_a is None or emb_b is None:
            return None

        # Cosine similarity
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        norm_a = sum(a * a for a in emb_a) ** 0.5
        norm_b = sum(b * b for b in emb_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def record_resonance(self, node_a: str, node_b: str, similarity: float) -> None:
        """Log a resonance measurement for analysis."""
        self._resonance_history.append({
            "ts": time.time(),
            "a": node_a,
            "b": node_b,
            "similarity": similarity,
        })

    def get_resonance_network(self, threshold: float = 0.7) -> List[Dict]:
        """Return all node pairs with resonance above threshold."""
        pairs = []
        ids = self.get_alive_nodes()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = self.compute_resonance(ids[i], ids[j])
                if sim is not None and sim >= threshold:
                    pairs.append({
                        "a": ids[i],
                        "b": ids[j],
                        "similarity": sim,
                    })
        return pairs

    # ----------------------------------------------------------------------
    # Network status
    # ----------------------------------------------------------------------
    def get_status(self) -> Dict:
        """Network-wide health snapshot."""
        alive = self.get_alive_nodes()
        total_energy = sum(self.nodes[nid].infant.hic.energy for nid in alive)
        resonance_pairs = self.get_resonance_network(threshold=0.6)
        return {
            "network_name": self.name,
            "total_nodes": len(self.nodes),
            "alive_nodes": len(alive),
            "total_energy": total_energy,
            "resonance_pairs": len(resonance_pairs),
            "queued_packets": len(self._packet_queue),
        }

    # ----------------------------------------------------------------------
    # Simulation loop (for in-process testing)
    # ----------------------------------------------------------------------
    def step_all(self, *,
                 max_cycles_per_node: int = 1,
                 sleep_func=lambda: None) -> None:
        """
        Advance each infant by one breath cycle (or up to max_cycles).
        Collect outboxes and route internally. Then compute resonance bonuses.
        """
        for nid, info in list(self.nodes.items()):
            if not info.is_alive:
                continue
            infant = info.infant
            for _ in range(max_cycles_per_node):
                if infant.hic.energy <= 0:
                    break
                packet = infant.breath_cycle()
                if packet:
                    infant.outbox.append(packet)
            # Flush infant's outbox into network queue
            while infant.outbox:
                pkt = infant.outbox.pop(0)
                self._packet_queue.append(pkt)
            # Mark last seen
            info.last_seen = time.time()
        # Deliver all queued packets
        self.deliver_all()
        # Post-step: compute cross-node resonance and apply synergy bonuses
        self._apply_resonance()

    def _apply_resonance(self) -> None:
        """Compute pairwise resonance and apply energy bonuses (1+1>2)."""
        import numpy as np
        alive_ids = self.get_alive_nodes()
        for i in range(len(alive_ids)):
            for j in range(i + 1, len(alive_ids)):
                a_id, b_id = alive_ids[i], alive_ids[j]
                a_info = self.nodes[a_id]
                b_info = self.nodes[b_id]
                emb_a = a_info.infant.get_embedding()
                emb_b = b_info.infant.get_embedding()
                if emb_a is None or emb_b is None:
                    continue
                # Compute cosine similarity
                dot = float(np.dot(emb_a, emb_b))
                norm_a = float(np.linalg.norm(emb_a))
                norm_b = float(np.linalg.norm(emb_b))
                if norm_a < 1e-9 or norm_b < 1e-9:
                    similarity = 0.0
                else:
                    similarity = dot / (norm_a * norm_b)
                # Record
                self.record_resonance(a_id, b_id, similarity)
                # Apply reciprocal bonus if above threshold
                if similarity >= 0.6:
                    a_info.infant.apply_resonance_bonus(b_id, similarity)
                    b_info.infant.apply_resonance_bonus(a_id, similarity)
