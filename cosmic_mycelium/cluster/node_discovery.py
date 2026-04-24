"""
Node Discovery — Phase 2.1
Gossip-based node discovery and presence broadcasting.

Infants broadcast their HIC state; receive peer announcements;
track online/offline status with timeout-based eviction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cosmic_mycelium.infant.main import SiliconInfant


@dataclass
class PeerInfo:
    """Metadata for a discovered peer infant."""

    node_id: str
    last_seen: float
    hic_state: str
    energy: float
    address: str | None = None  # Optional network address


class NodeDiscovery:
    """
    Gossip-based node discovery for infant cluster.

    Phase 2.1 Features:
    - Periodic HIC state broadcast (every 5s)
    - Peer announcement reception and cache update
    - Automatic timeout-based eviction (10s unseen → offline)
    - Cluster membership snapshot for routing
    """

    # Configuration
    BROADCAST_INTERVAL: float = 5.0  # How often to announce self
    PEER_TIMEOUT: float = 10.0  # Evict unseen peers after 10s
    MAX_PEERS: int = 1000  # Hard cap for memory safety

    def __init__(self, infant: SiliconInfant):
        """
        Args:
            infant: Parent SiliconInfant instance
        """
        self.infant = infant
        self.logger = logging.getLogger(f"NodeDiscovery[{infant.infant_id}]")

        # Local peer cache: node_id → PeerInfo
        self.peers: dict[str, PeerInfo] = {}

        # Background task handle
        self._task: asyncio.Task | None = None
        self._running = False

    # ─── Lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        """Start discovery background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        self.logger.info("Node discovery started")

    async def stop(self) -> None:
        """Stop discovery task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self.logger.info("Node discovery stopped")

    # ─── Broadcast (outbound) ────────────────────────────────────────────────
    async def _broadcast_loop(self) -> None:
        """Periodically broadcast own presence to cluster."""
        while self._running:
            try:
                await self._broadcast_announcement()
                await asyncio.sleep(self.BROADCAST_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Broadcast error: {e}", exc_info=True)
                await asyncio.sleep(self.BROADCAST_INTERVAL)

    async def _broadcast_announcement(self) -> None:
        """
        Emit own HIC state to cluster.

        In full deployment, this goes via:
        - Redis Pub/Sub channel: `cosmic:discovery`
        - Or Kafka topic: `infant-presence`
        Here we call the network's broadcast method if available.
        """
        hic_status = self.infant.hic.get_status()
        announcement = {
            "type": "node_announce",
            "node_id": self.infant.infant_id,
            "timestamp": time.time(),
            "hic": {
                "state": hic_status["state"],
                "energy": hic_status["energy"],
                "total_cycles": hic_status["total_cycles"],
            },
        }

        # Route through network if attached
        if self.infant.network is not None:
            try:
                self.infant.network.broadcast(
                    source_id=self.infant.infant_id,
                    value_payload=announcement,
                )
            except Exception as e:
                self.logger.warning(f"Failed to broadcast via network: {e}")

        # Also directly inform node manager if accessible
        # (in cluster mode, infant may have ref to node_manager)
        if hasattr(self.infant, "node_manager") and self.infant.node_manager:
            # Direct registration for health tracking
            self.infant.node_manager.record_heartbeat(self.infant.infant_id)

    # ─── Inbound processing ──────────────────────────────────────────────────
    def process_announcement(self, payload: dict) -> None:
        """
        Handle received node_announce packet.

        Args:
            payload: Announcement dict from network
        """
        node_id = payload.get("node_id")
        if not node_id or node_id == self.infant.infant_id:
            return  # Ignore self or malformed

        hic = payload.get("hic", {})
        peer = PeerInfo(
            node_id=node_id,
            last_seen=payload.get("timestamp", time.time()),
            hic_state=hic.get("state", "unknown"),
            energy=hic.get("energy", 0.0),
        )
        self.peers[node_id] = peer
        self.logger.debug(f"Peer discovered: {node_id} (state={peer.hic_state})")

        # Enforce max peers limit (evict oldest if needed)
        if len(self.peers) > self.MAX_PEERS:
            oldest = min(self.peers.items(), key=lambda kv: kv[1].last_seen)[0]
            del self.peers[oldest]

    # ─── Peer queries ────────────────────────────────────────────────────────
    def get_online_peers(self) -> list[str]:
        """List node IDs of peers seen within PEER_TIMEOUT."""
        now = time.time()
        return [
            nid
            for nid, info in self.peers.items()
            if now - info.last_seen < self.PEER_TIMEOUT
        ]

    def get_peer_info(self, node_id: str) -> PeerInfo | None:
        """Get info for a specific peer if known."""
        return self.peers.get(node_id)

    def get_all_peers(self) -> dict[str, PeerInfo]:
        """Snapshot of all cached peer info."""
        return dict(self.peers)

    # ─── Maintenance ─────────────────────────────────────────────────────────
    def evict_stale_peers(self) -> int:
        """
        Remove peers not seen within PEER_TIMEOUT.

        Returns:
            Number of peers evicted
        """
        now = time.time()
        to_remove = [
            nid
            for nid, info in self.peers.items()
            if now - info.last_seen > self.PEER_TIMEOUT
        ]
        for nid in to_remove:
            del self.peers[nid]
            self.logger.info(f"Peer evicted (stale): {nid}")
        return len(to_remove)
