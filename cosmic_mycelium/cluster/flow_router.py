"""
Flow Router — Phase 3.2 Hierarchical Routing
Routes packets through multi-hop paths, maintains neighbor tables,
and handles hierarchical broadcast with failure detection.
"""

from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass, field

from cosmic_mycelium.common.data_packet import CosmicPacket  # noqa: TC001


@dataclass
class RouteMetrics:
    """Performance metrics for a route."""

    hop_count: int = 1
    latency_estimate: float = 0.0
    success_rate: float = 1.0
    last_used: float = field(default_factory=time.time)
    use_count: int = 0


@dataclass
class NeighborEntry:
    """A directly-connected neighbor node with health metadata."""

    node_id: str
    address: str
    last_seen: float = field(default_factory=time.time)
    health_score: float = 1.0
    link_cost: float = 1.0
    metrics: RouteMetrics = field(default_factory=RouteMetrics)


@dataclass
class RouteEntry:
    """A computed route to a destination."""

    destination: str
    next_hop: str
    cost: float
    hop_count: int
    path: list[str]
    last_updated: float = field(default_factory=time.time)
    is_valid: bool = True


class FlowRouter:
    """
    Routes packets through the mycelium network with hierarchical awareness.

    Phase 3.2 Enhancements:
    - Neighbor tables with health tracking
    - Multi-hop routing via Dijkstra shortest path
    - Hierarchical broadcast with TTL and seen-set tracking
    - Failure detection integration (route invalidation)
    - Route metrics collection and cost-based selection
    - Path repair via recomputation
    """

    # Routing parameters
    DEFAULT_TTL: int = 32
    NEIGHBOR_TIMEOUT: float = 10.0
    ROUTE_UPDATE_INTERVAL: float = 1.0
    MAX_PATH_LENGTH: int = 16
    HEALTH_DECAY_RATE: float = 0.95

    def __init__(self) -> None:
        # Direct neighbors from THIS router's perspective
        self.neighbor_table: dict[str, NeighborEntry] = {}

        # Network topology graph: node_id -> {neighbor_id: cost}
        self.topology: dict[str, dict[str, float]] = {}
        self._broadcast_seen: dict[str, set[str]] = {}
        self._broadcast_cleanup_counter: int = 0

        # Computed routes: source -> dest -> RouteEntry
        self.route_table: dict[str, dict[str, RouteEntry]] = {}

        # Broadcast seen-set: packet_id -> seen_node_set
        self._broadcast_seen: dict[str, set[str]] = {}
        self._broadcast_window: float = 60.0

        # Pheromone trails for info routing preference
        self.pheromone_map: dict[str, float] = {}

        # Metrics
        self._stats = {
            "packets_routed": 0,
            "broadcasts_flooded": 0,
            "route_recomputations": 0,
            "failed_routes": 0,
        }

        self.logger = logging.getLogger("FlowRouter")

    # ----------------------------------------------------------------------
    # Neighbor & Topology Management
    # ----------------------------------------------------------------------
    def add_neighbor(
        self,
        local_node: str,
        neighbor_node: str,
        link_cost: float = 1.0,
        address: str | None = None,
    ) -> None:
        """
        Record that local_node has a direct link to neighbor_node.

        For a single-router view, local_node is typically the router's own ID.
        """
        addr = address or f"{neighbor_node}:8000"

        # Record in neighbor table (for local_node's perspective)
        if local_node not in self.neighbor_table:
            self.neighbor_table[local_node] = NeighborEntry(
                node_id=local_node,
                address=addr,
                health_score=1.0,
                link_cost=link_cost,
            )
        else:
            entry = self.neighbor_table[local_node]
            entry.last_seen = time.time()
            entry.link_cost = min(entry.link_cost, link_cost)

        # Record in topology (bidirectional)
        if local_node not in self.topology:
            self.topology[local_node] = {}
        self.topology[local_node][neighbor_node] = link_cost

        if neighbor_node not in self.topology:
            self.topology[neighbor_node] = {}
        self.topology[neighbor_node][local_node] = link_cost

        self.logger.debug(
            f"Neighbor added: {local_node} <-> {neighbor_node} (cost={link_cost})"
        )

    def remove_neighbor(self, local_node: str, neighbor_node: str) -> None:
        """Remove bidirectional link between two nodes."""
        # Remove from topology
        if local_node in self.topology and neighbor_node in self.topology[local_node]:
            del self.topology[local_node][neighbor_node]
        if (
            neighbor_node in self.topology
            and local_node in self.topology[neighbor_node]
        ):
            del self.topology[neighbor_node][local_node]
        # Clean up empty entries
        if local_node in self.topology and not self.topology[local_node]:
            del self.topology[local_node]
        if neighbor_node in self.topology and not self.topology[neighbor_node]:
            del self.topology[neighbor_node]
        self.logger.debug(f"Neighbor removed: {local_node} <-> {neighbor_node}")

    def get_neighbors(self, node_id: str) -> list[str]:
        """Get direct neighbor list for a node from topology."""
        return list(self.topology.get(node_id, {}).keys())

    def is_in_topology(self, node_id: str) -> bool:
        """Check if node exists in topology."""
        return node_id in self.topology

    # ----------------------------------------------------------------------
    # Route Computation — Dijkstra
    # ----------------------------------------------------------------------
    def compute_route(
        self,
        source: str,
        destination: str,
        force: bool = False,
    ) -> RouteEntry | None:
        """
        Compute shortest path from source to destination using Dijkstra.

        Args:
            source: Originating node ID
            destination: Target node ID
            force: If True, recompute even if cached route exists

        Returns:
            RouteEntry if route found, None if unreachable
        """
        # Check cache first
        if (
            not force
            and source in self.route_table
            and destination in self.route_table[source]
        ):
            cached = self.route_table[source][destination]
            if cached.is_valid:
                return cached

        # Validate nodes exist in topology
        if source not in self.topology or destination not in self.topology:
            return None

        if source == destination:
            route = RouteEntry(
                destination=destination,
                next_hop=source,
                cost=0.0,
                hop_count=0,
                path=[source],
                is_valid=True,
            )
            self._cache_route(source, destination, route)
            return route

        # Dijkstra
        distances: dict[str, float] = {source: 0.0}
        predecessors: dict[str, str | None] = {source: None}
        visited: set[str] = set()
        heap: list[tuple[float, str]] = [(0.0, source)]

        while heap:
            current_dist, current = heapq.heappop(heap)

            if current in visited:
                continue
            visited.add(current)

            if current == destination:
                break

            for neighbor, edge_cost in self.topology.get(current, {}).items():
                if neighbor in visited:
                    continue
                new_dist = current_dist + edge_cost
                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    predecessors[neighbor] = current
                    heapq.heappush(heap, (new_dist, neighbor))

        # Reconstruct path
        if destination not in distances:
            return None

        path: list[str] = []
        node: str | None = destination
        while node is not None:
            path.insert(0, node)
            node = predecessors.get(node)

        route = RouteEntry(
            destination=destination,
            next_hop=path[1] if len(path) > 1 else destination,
            cost=distances[destination],
            hop_count=len(path) - 1,
            path=path,
            is_valid=True,
        )

        self._cache_route(source, destination, route)
        self._stats["route_recomputations"] += 1
        self.logger.debug(
            f"Route computed: {source} -> {destination} via {route.next_hop} ({route.hop_count} hops)"
        )
        return route

    def _cache_route(self, source: str, destination: str, route: RouteEntry) -> None:
        """Store route in cache."""
        if source not in self.route_table:
            self.route_table[source] = {}
        self.route_table[source][destination] = route

    # ----------------------------------------------------------------------
    # Packet Routing
    # ----------------------------------------------------------------------
    def route(
        self,
        packet: CosmicPacket,
        available_nodes: list[str],
    ) -> str | None:
        """
        Select next hop for a packet.

        Args:
            packet: Packet to route
            available_nodes: Candidate node IDs (typically this router's neighbors)

        Returns:
            Next hop node ID or None if no route
        """
        source = packet.source_id
        dest = packet.destination_id
        flow_type = packet.get_flow_type()

        # Anycast: no specific destination — pick one from available
        if not dest:
            if not available_nodes:
                return None
            if flow_type == "info":
                # Pheromone-weighted anycast
                best = None
                best_score = -1.0
                for candidate in available_nodes:
                    score = self.pheromone_map.get(f"{source}->{candidate}", 0.1)
                    if score > best_score:
                        best_score = score
                        best = candidate
                return best
            elif flow_type in ("physical", "value"):
                return available_nodes[0]
            else:
                return None  # unknown flow type

        # Unicast: compute route to specific destination
        if flow_type == "physical":
            return self._route_physical(source, dest, available_nodes)
        elif flow_type == "info":
            return self._route_info(source, dest, available_nodes)
        elif flow_type == "value":
            return self._route_value(source, dest, available_nodes)
        return None

    def _route_physical(self, source: str, dest: str, nodes: list[str]) -> str | None:
        """Physical flow: lowest-latency shortest path."""
        route = self.compute_route(source, dest)
        if route and route.next_hop in nodes:
            return route.next_hop
        # Fallback: pick first available node if route not computed yet
        return nodes[0] if nodes else None

    def _route_info(self, source: str, dest: str, nodes: list[str]) -> str | None:
        """Info flow: pheromone-weighted with diversity."""
        route = self.compute_route(source, dest)
        if route and route.next_hop in nodes:
            return route.next_hop
        # Fallback: use pheromone scores
        best = None
        best_score = -1.0
        for candidate in nodes:
            score = self.pheromone_map.get(f"{source}->{candidate}", 0.1)
            if score > best_score:
                best_score = score
                best = candidate
        return best

    def _route_value(self, source: str, dest: str, nodes: list[str]) -> str | None:
        """Value flow: most reliable route."""
        route = self.compute_route(source, dest)
        if route and route.next_hop in nodes:
            return route.next_hop
        return nodes[0] if nodes else None

    # ----------------------------------------------------------------------
    # Hierarchical Broadcast (Multi-Hop)
    # ----------------------------------------------------------------------
    def broadcast(
        self,
        packet: CosmicPacket,
        ttl: int | None = None,
        seen_override: set[str] | None = None,
        _current: str | None = None,  # internal: current node for recursion
    ) -> list[str]:
        """
        Flood packet through network with TTL and loop prevention.

        Args:
            packet: Broadcast packet
            ttl: Time-to-live (max hops)
            seen_override: External seen-set for multi-hop coordination
            _current: Internal use — current node for recursion (default = packet.source_id)

        Returns:
            List of node IDs the packet was delivered to (excluding source)
        """
        if ttl is None:
            ttl = packet.ttl if packet.ttl > 0 else self.DEFAULT_TTL
        if ttl <= 0:
            return []

        source = packet.source_id
        current = _current or source
        packet_id = f"{packet.timestamp}:{source}"

        # Count broadcast event only on top-level call
        if _current is None:
            self._stats["broadcasts_flooded"] += 1

        # Get or create seen set for this packet (shared across recursion)
        if seen_override is not None:
            seen = seen_override
        else:
            seen = self._broadcast_seen.get(packet_id, set())
            if not seen:
                self._broadcast_seen[packet_id] = seen

        if current in seen:
            return []
        seen.add(current)

        delivered: list[str] = []

        # Deliver to all direct neighbors of current node
        neighbors = self.get_neighbors(current)
        for neighbor_id in neighbors:
            if neighbor_id not in seen:
                delivered.append(neighbor_id)
                # Recursive multi-hop: decrement TTL, current becomes neighbor
                sub_delivered = self.broadcast(packet, ttl - 1, seen, _current=neighbor_id)
                delivered.extend(sub_delivered)

        self.logger.debug(
            f"Broadcast from {source} via {current}: delivered {len(delivered)} (TTL={ttl})"
        )
        # deduplicate
        return list(set(delivered))

    def clear_broadcast_seen(self, older_than: float = 300.0) -> int:
        """Clean up old broadcast seen entries."""
        removed = 0
        for packet_id, seen in list(self._broadcast_seen.items()):
            # We don't store timestamp per packet currently; simplified
            # In full impl would store (timestamp, seen_set) tuples
            # For now, just clear empty seen sets occasionally
            if len(seen) == 0:
                del self._broadcast_seen[packet_id]
                removed += 1
        return removed

    # ----------------------------------------------------------------------
    # Pheromone Trail Management
    # ----------------------------------------------------------------------
    def update_pheromone(self, path: str, delta: float) -> None:
        """Update pheromone strength for a path."""
        self.pheromone_map[path] = self.pheromone_map.get(path, 0.1) + delta
        # Evaporate all trails
        for k in list(self.pheromone_map.keys()):
            self.pheromone_map[k] *= 0.99
            if self.pheromone_map[k] < 0.01:
                del self.pheromone_map[k]

    # ----------------------------------------------------------------------
    # Failure Detection & Recovery
    # ----------------------------------------------------------------------
    def mark_node_failed(self, node_id: str) -> int:
        """
        Called when a node is detected as failed.
        Removes from topology and invalidates affected routes.
        """
        self.logger.warning(f"Node failure detected: {node_id}")

        # Remove all edges to/from failed node
        if node_id in self.topology:
            # Remove references from neighbors
            for neighbor in self.topology[node_id]:
                if neighbor in self.topology and node_id in self.topology[neighbor]:
                    del self.topology[neighbor][node_id]
            del self.topology[node_id]

        # Remove from neighbor table
        self.neighbor_table.pop(node_id, None)

        # Invalidate routes through this node
        count = 0
        for src_routes in self.route_table.values():
            for _dest, route in list(src_routes.items()):
                if route and node_id in route.path:
                    route.is_valid = False
                    count += 1

        self._stats["failed_routes"] += count
        self.logger.info(f"Invalidated {count} routes via failed node {node_id}")
        return count

    def refresh_routes(self) -> None:
        """Recompute all cached routes (called after topology changes)."""
        for src_routes in self.route_table.values():
            for dest, route in list(src_routes.items()):
                if not route.is_valid:
                    src_routes.pop(dest, None)
        self._stats["route_recomputations"] += 1

    def get_route_to(self, source: str, destination: str) -> RouteEntry | None:
        """Get cached route if valid, else None."""
        if source in self.route_table and destination in self.route_table[source]:
            route = self.route_table[source][destination]
            if route.is_valid:
                return route
        return None

    # ----------------------------------------------------------------------
    # Metrics & Monitoring
    # ----------------------------------------------------------------------
    def get_router_status(self) -> dict:
        """Router health and statistics snapshot."""
        total_routes = sum(len(routes) for routes in self.route_table.values())
        valid_routes = sum(
            1
            for routes in self.route_table.values()
            for r in routes.values()
            if r.is_valid
        )

        return {
            "timestamp": time.time(),
            "topology_nodes": len(self.topology),
            "neighbor_count": len(self.neighbor_table),
            "total_routes_cached": total_routes,
            "valid_routes": valid_routes,
            "stats": self._stats.copy(),
            "top_nexthops": self._get_top_nexthops(5),
        }

    def _get_top_nexthops(self, n: int) -> list[tuple[str, int]]:
        """Get most frequently used next-hop nodes."""
        usage: dict[str, int] = {}
        for routes in self.route_table.values():
            for route in routes.values():
                if route.is_valid:
                    usage[route.next_hop] = usage.get(route.next_hop, 0) + 1
        sorted_hops = sorted(usage.items(), key=lambda x: -x[1])
        return sorted_hops[:n]
