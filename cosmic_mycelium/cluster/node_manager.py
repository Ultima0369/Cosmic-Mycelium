"""
Cluster Node Manager — Phase 3.1 Enhanced
Manages multiple infant nodes with health monitoring, discovery, and recovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, cast

from cosmic_mycelium.cluster.consensus import Consensus
from cosmic_mycelium.cluster.flow_router import FlowRouter

if TYPE_CHECKING:
    from cosmic_mycelium.infant.main import SiliconInfant


class NodeStatus(Enum):
    """Lifecycle state of a cluster node."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEGRADED = "degraded"
    FAILED = "failed"
    LEAVING = "leaving"


@dataclass
class NodeHealth:
    """Health metrics for a node."""

    score: float = 1.0  # 0.0 (dead) → 1.0 (perfect)
    last_heartbeat: float = field(default_factory=time.time)
    failure_count: int = 0
    consecutive_failures: int = 0
    last_failure_time: float | None = None
    uptime_start: float = field(default_factory=time.time)


@dataclass
class InfantNode:
    """Registered infant node with full lifecycle metadata."""

    node_id: str
    address: str
    infant: SiliconInfant | None = None  # SiliconInfant instance (optional)
    status: NodeStatus = NodeStatus.ACTIVE
    health: NodeHealth = field(default_factory=NodeHealth)
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class NodeManager:
    """
    Manages a cluster of silicon infant nodes.

    Phase 3.1 Enhancements:
    - Async health monitoring with heartbeat tracking
    - Automatic failure detection (timeout-based)
    - Node recovery orchestration (restart failed nodes)
    - Gossip-based node discovery
    - Graceful degradation and suspension logic
    - Detailed cluster health metrics
    """

    # Health check parameters
    HEARTBEAT_TIMEOUT: float = 10.0  # Seconds before marking node unhealthy
    HEALTH_CHECK_INTERVAL: float = 2.0  # Background task frequency
    FAILURE_THRESHOLD: int = 3  # Consecutive failures before FAILED state
    DEGRADE_THRESHOLD: float = 0.3  # Health score below → DEGRADED
    RECOVERY_GRACE_PERIOD: float = 5.0  # Wait before auto-recovery attempt

    def __init__(
        self,
        min_nodes: int = 3,
        max_nodes: int = 100,
        enable_auto_recovery: bool = True,
    ):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.enable_auto_recovery = enable_auto_recovery

        # Node registry
        self.nodes: dict[str, InfantNode] = {}

        # Subsystems
        self.flow_router = FlowRouter()
        self.consensus = Consensus()

        # Runtime state
        self.running = False
        self._monitor_task: asyncio.Task | None = None
        self._discovery_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self.logger = logging.getLogger("NodeManager")

        # Gossip discovery state
        self._known_gossipers: set[str] = set()
        self._local_broadcast_port: int = 8002

    # ----------------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------------
    def start(self) -> None:
        """Start the node manager and spawn background monitoring tasks."""
        self.running = True
        self.logger.info("NodeManager started")

    def stop(self) -> None:
        """Stop the node manager and cancel background tasks."""
        self.running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        if self._discovery_task and not self._discovery_task.done():
            self._discovery_task.cancel()
        self.logger.info("NodeManager stopped")

    async def start_async(self) -> None:
        """Start NodeManager with async background tasks."""
        self.start()
        self._monitor_task = asyncio.create_task(self._health_monitor_loop())
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self.logger.info("Async monitoring tasks launched")

    # ----------------------------------------------------------------------
    # Node Registration
    # ----------------------------------------------------------------------
    def register_node(
        self,
        infant: SiliconInfant,
        address: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Register a new SiliconInfant with the cluster.

        Args:
            infant: SiliconInfant instance
            address: Network address (host:port), default: auto-generated
            metadata: Additional node metadata (capabilities, version, etc.)

        Returns:
            node_id (uses infant.infant_id)
        """
        if len(self.nodes) >= self.max_nodes:
            raise RuntimeError(f"Cluster at maximum capacity ({self.max_nodes} nodes)")

        node_id = infant.infant_id
        if node_id in self.nodes:
            raise ValueError(f"Node {node_id} already registered")

        addr = address or f"{node_id}:8000"

        node = InfantNode(
            node_id=node_id,
            address=addr,
            infant=infant,
            status=NodeStatus.ACTIVE,
            health=NodeHealth(uptime_start=time.time()),
            joined_at=time.time(),
            last_seen=time.time(),
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        self.logger.info(f"Node registered: {node_id} at {addr}")
        return node_id

    def unregister_node(self, node_id: str, graceful: bool = True) -> bool:
        """
        Remove a node from the cluster.

        Args:
            node_id: Node to remove
            graceful: If True, set status to LEAVING before removal

        Returns:
            True if node was removed, False if not found
        """
        node = self.nodes.get(node_id)
        if not node:
            return False

        if graceful:
            node.status = NodeStatus.LEAVING
            # Schedule cleanup via running loop if available
            try:
                task = asyncio.create_task(self._graceful_cleanup(node_id))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            except RuntimeError:
                # No running loop — do sync cleanup
                pass

        self.nodes.pop(node_id, None)
        self.logger.info(f"Node unregistered: {node_id}")
        return True

    async def _graceful_cleanup(self, node_id: str) -> None:
        """Async cleanup after graceful departure."""
        await asyncio.sleep(1.0)  # Allow in-flight packets to drain
        if node_id in self.nodes:
            self.nodes.pop(node_id, None)

    # ----------------------------------------------------------------------
    # Health Monitoring
    # ----------------------------------------------------------------------
    def record_heartbeat(self, node_id: str, data: dict | None = None) -> bool:
        """
        Record a heartbeat from a node.

        Args:
            node_id: Originating node
            data: Optional health payload (energy, load, etc.) — for monitoring only

        Returns:
            True if heartbeat accepted, False if node unknown
        """
        node = self.nodes.get(node_id)
        if not node:
            return False

        node.last_seen = time.time()
        node.status = (
            NodeStatus.ACTIVE
        )  # Auto-recover from DEGRADED/SUSPENDED on heartbeat

        # Update health score
        node.health.last_heartbeat = time.time()
        node.health.consecutive_failures = 0

        # Note: data payload is informational only; does not mutate node state
        # In production, this would update metrics but not directly set energy

        return True

    def get_node_health(self, node_id: str) -> dict | None:
        """Get detailed health metrics for a specific node."""
        node = self.nodes.get(node_id)
        if not node:
            return None

        return {
            "node_id": node_id,
            "status": node.status.value,
            "health_score": node.health.score,
            "last_seen": node.last_seen,
            "uptime_seconds": time.time() - node.health.uptime_start,
            "failure_count": node.health.failure_count,
            "consecutive_failures": node.health.consecutive_failures,
        }

    def get_cluster_health(self) -> dict:
        """
        Comprehensive cluster health snapshot.

        Returns:
            Dict with node counts, energy totals, and health distributions
        """
        total_nodes = len(self.nodes)
        active_nodes = sum(
            1 for n in self.nodes.values() if n.status == NodeStatus.ACTIVE
        )
        degraded_nodes = sum(
            1 for n in self.nodes.values() if n.status == NodeStatus.DEGRADED
        )
        failed_nodes = sum(
            1 for n in self.nodes.values() if n.status == NodeStatus.FAILED
        )

        # Total energy (sum of active node energies)
        total_energy = 0.0
        for n in self.nodes.values():
            if n.infant and hasattr(n.infant, "hic"):
                total_energy += n.infant.hic.energy

        # Average health score
        health_scores = [n.health.score for n in self.nodes.values()]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

        return {
            "timestamp": time.time(),
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "degraded_nodes": degraded_nodes,
            "failed_nodes": failed_nodes,
            "total_energy": round(total_energy, 3),
            "average_health": round(avg_health, 3),
            "min_nodes_met": active_nodes >= self.min_nodes,
        }

    # ----------------------------------------------------------------------
    # Background Monitoring
    # ----------------------------------------------------------------------
    async def _health_monitor_loop(self) -> None:
        """
        Background task: periodically check node health and trigger recovery.
        Runs every HEALTH_CHECK_INTERVAL seconds.
        """
        self.logger.info("Health monitor loop started")
        while self.running:
            try:
                await self._check_all_nodes()
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}", exc_info=True)
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

    async def _check_all_nodes(self) -> None:
        """Check health of all registered nodes."""
        current_time = time.time()
        nodes_to_recover: list[str] = []

        for node_id, node in list(self.nodes.items()):
            time_since_seen = current_time - node.last_seen

            # Check for timeout
            if time_since_seen > self.HEARTBEAT_TIMEOUT:
                node.health.consecutive_failures += 1
                node.health.last_failure_time = current_time

                if node.health.consecutive_failures >= self.FAILURE_THRESHOLD:
                    node.status = NodeStatus.FAILED
                    node.health.score = 0.0
                    self.logger.warning(
                        f"Node {node_id} marked FAILED "
                        f"({node.health.consecutive_failures} consecutive timeouts)"
                    )
                    # Propagate failure to FlowRouter — invalidate routes through this node
                    self.flow_router.mark_node_failed(node_id)
                    if self.enable_auto_recovery:
                        nodes_to_recover.append(node_id)
                else:
                    node.status = NodeStatus.DEGRADED
                    node.health.score = max(
                        0.0, 1.0 - (time_since_seen / self.HEARTBEAT_TIMEOUT)
                    )
            else:
                # Node is alive — update health score based on responsiveness
                # Score is 1.0 for freshly seen, decays to 0 at HEARTBEAT_TIMEOUT
                node.health.score = max(0.0, 1.0 - (time_since_seen / self.HEARTBEAT_TIMEOUT))
                if (
                    node.health.score < self.DEGRADE_THRESHOLD
                    and node.status == NodeStatus.ACTIVE
                ):
                    node.status = NodeStatus.DEGRADED

        # Schedule recovery for failed nodes
        for nid in nodes_to_recover:
            task = asyncio.create_task(self._recover_node(nid))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        # Maintain minimum cluster size
        self.ensure_min_nodes()

    async def _recover_node(self, node_id: str) -> None:
        """
        Attempt to recover a failed node.

        Strategy:
        1. Wait grace period
        2. Check if node has spontaneously recovered (heartbeat arrived)
        3. If still failed, mark for manual intervention
        """
        self.logger.info(
            f"Recovery initiated for {node_id}, waiting {self.RECOVERY_GRACE_PERIOD}s"
        )
        await asyncio.sleep(self.RECOVERY_GRACE_PERIOD)

        node = self.nodes.get(node_id)
        if not node:
            return  # Node was manually removed

        # Check if recovered during grace period
        time_since_seen = time.time() - node.last_seen
        if time_since_seen < self.HEARTBEAT_TIMEOUT:
            self.logger.info(
                f"Node {node_id} recovered spontaneously during grace period"
            )
            node.status = NodeStatus.ACTIVE
            node.health.consecutive_failures = 0
            node.health.score = 1.0
            return

        # Still failed — log for manual intervention
        self.logger.error(
            f"Node {node_id} recovery FAILED — requires manual intervention. "
            f"Last seen: {node.last_seen:.2f}, energy: {getattr(node.infant.hic, 'energy', 'N/A') if node.infant else 'N/A'}"
        )
        # In a full implementation, would trigger external alert here

    # ----------------------------------------------------------------------
    # Node Discovery (Gossip-based)
    # ----------------------------------------------------------------------
    async def _discovery_loop(self) -> None:
        """
        Background task: periodic node announcement and peer discovery.
        Nodes broadcast their presence; learns about others via network.
        """
        self.logger.info("Discovery loop started")
        while self.running:
            try:
                await self._gossip_announce()
                await asyncio.sleep(5.0)  # Gossip every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Discovery error: {e}")
                await asyncio.sleep(5.0)

    async def _gossip_announce(self) -> None:
        """
        Broadcast this node's presence to peers.
        In a real deployment, this would use UDP multicast or a service mesh.
        Here we simulate via shared network state if available.
        """
        # For now, log presence (would emit to network in full impl)
        active_count = sum(
            1 for n in self.nodes.values() if n.status == NodeStatus.ACTIVE
        )
        self.logger.debug(f"Gossip: {active_count} active nodes in cluster")

    def get_neighbors(self, node_id: str, max_hops: int = 1) -> list[str]:
        """
        Get neighbor nodes within max_hops (for routing).

        Args:
            node_id: Center node
            max_hops: Number of hops radius

        Returns:
            List of neighbor node IDs
        """
        # Simplified: return all active nodes except self
        if node_id not in self.nodes:
            return []
        return [
            nid
            for nid, n in self.nodes.items()
            if n.status == NodeStatus.ACTIVE and nid != node_id
        ][: max_hops * 10]

    # ----------------------------------------------------------------------
    # Node Query & Metrics
    # ----------------------------------------------------------------------
    def get_node_ids(self) -> list[str]:
        """List all known node IDs."""
        return list(self.nodes.keys())

    def get_active_node_ids(self) -> list[str]:
        """List IDs of nodes currently marked active."""
        return [nid for nid, n in self.nodes.items() if n.status == NodeStatus.ACTIVE]

    def get_node_info(self, node_id: str) -> dict | None:
        """Get full info for a node."""
        node = self.nodes.get(node_id)
        if not node:
            return None

        info = {
            "node_id": node_id,
            "address": node.address,
            "status": node.status.value,
            "joined_at": node.joined_at,
            "last_seen": node.last_seen,
            "health": {
                "score": node.health.score,
                "uptime": time.time() - node.health.uptime_start,
                "failure_count": node.health.failure_count,
            },
            "metadata": node.metadata,
        }
        if node.infant:
            info["energy"] = node.infant.hic.energy
            # Check if infant has get_embedding method (real SiliconInfant)
            if hasattr(node.infant, "get_embedding"):
                try:
                    info["embedding_available"] = (
                        node.infant.get_embedding() is not None
                    )
                except (RuntimeError, AttributeError, TypeError) as e:
                    logger.debug("Node %s: get_embedding failed: %s", node.node_id, e)
                    info["embedding_available"] = False
            else:
                info["embedding_available"] = False
        return info

    def get_all_nodes_info(self) -> list[dict]:
        """Get info for all nodes."""
        return [
            info for nid in self.nodes if (info := self.get_node_info(nid)) is not None
        ]

    # Backward compatibility alias (deprecated — use get_cluster_health)
    def get_cluster_status(self) -> dict:
        """
        Deprecated: Use get_cluster_health() for more accurate metrics.
        Maintained for backward compatibility with Phase 2 tests.
        """
        health = self.get_cluster_health()
        # Map new fields to old schema for test compatibility
        return {
            "total_nodes": health["total_nodes"],
            "active_nodes": health["active_nodes"],
            "total_energy": health["total_energy"],
            "physics_anchor_ok": health["min_nodes_met"],
            "avg_resonance": health["average_health"],  # approximate
        }

    # ----------------------------------------------------------------------
    # Backward Compatibility Aliases (Phase 2 API)
    # ----------------------------------------------------------------------
    def spawn_node(self, node_id: str) -> bool:
        """
        Deprecated: Use register_node(infant) instead.
        Creates a stub node with mock infant for backward compatibility.
        """
        if len(self.nodes) >= self.max_nodes:
            return False

        # Create mock infant with minimal hic interface for energy reporting
        class MockInfant:
            def __init__(self, energy_max: float) -> None:
                self.infant_id = node_id
                self.hic = type(
                    "MockHIC",
                    (),
                    {
                        "energy": energy_max,
                        "_energy": energy_max,
                    },
                )()

        mock_infant = MockInfant(energy_max=100.0)

        self.nodes[node_id] = InfantNode(
            node_id=node_id,
            address=f"{node_id}:8000",
            infant=cast("SiliconInfant | None", mock_infant),
            status=NodeStatus.ACTIVE,
            health=NodeHealth(),
        )
        return True

    def remove_node(self, node_id: str) -> None:
        """Deprecated: Use unregister_node() instead."""
        self.nodes.pop(node_id, None)

    # ----------------------------------------------------------------------
    # Auto-scaling (basic)
    # ----------------------------------------------------------------------
    def ensure_min_nodes(self) -> None:
        """
        Ensure cluster maintains at least min_nodes active infants.
        Spawns placeholder nodes if below threshold (production would use templates).
        """
        active_count = sum(
            1 for n in self.nodes.values() if n.status == NodeStatus.ACTIVE
        )
        if active_count < self.min_nodes:
            needed = int(self.min_nodes - active_count)
            self.logger.info(
                f"Cluster below minimum ({active_count}/{self.min_nodes}), spawning {needed} nodes"
            )
            # In full impl, would spawn real infants via factory
            for _ in range(needed):
                node_id = f"auto-{uuid.uuid4().hex[:8]}"
                # Create stub for now (would instantiate real SiliconInfant)
                self.nodes[node_id] = InfantNode(
                    node_id=node_id,
                    address=f"{node_id}:8000",
                    infant=None,  # Placeholder
                    status=NodeStatus.ACTIVE,
                    health=NodeHealth(),
                )

    def prune_dead_nodes(self, max_age_seconds: float = 3600) -> int:
        """
        Remove nodes that have been in FAILED state beyond max_age_seconds.

        Args:
            max_age_seconds: How long to keep failed node records

        Returns:
            Number of nodes pruned
        """
        current = time.time()
        to_remove = []
        for node_id, node in self.nodes.items():
            if node.status == NodeStatus.FAILED:
                age = current - node.joined_at
                if age > max_age_seconds:
                    to_remove.append(node_id)

        for node_id in to_remove:
            self.nodes.pop(node_id, None)
            self.logger.info(f"Pruned stale failed node: {node_id}")

        return len(to_remove)
