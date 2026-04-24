"""
Metrics Server — Prometheus Metrics Endpoint
Exposes infant metrics for Prometheus scraping.
Also collects cluster-wide metrics from NodeManager, FlowRouter, CollectiveIntelligence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aiohttp import web

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Type imports for static analysis only
if TYPE_CHECKING:
    from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
    from cosmic_mycelium.cluster.flow_router import FlowRouter
    from cosmic_mycelium.cluster.network import MyceliumNetwork
    from cosmic_mycelium.cluster.node_manager import NodeManager

# Runtime cluster availability detection (no heavy imports)
import importlib.util

_CLUSTER_MODULES = [
    "cosmic_mycelium.cluster.collective_intelligence",
    "cosmic_mycelium.cluster.flow_router",
    "cosmic_mycelium.cluster.network",
    "cosmic_mycelium.cluster.node_manager",
]
CLUSTER_AVAILABLE = all(
    importlib.util.find_spec(m) is not None for m in _CLUSTER_MODULES
)


# =============================================================================
# HIC Metrics
# =============================================================================
if PROMETHEUS_AVAILABLE:
    HIC_ENERGY = Gauge("hic_energy_total", "Current HIC energy", ["infant_id"])
    HIC_BREATH_CYCLES = Counter(
        "hic_breath_cycles_total", "Total breath cycles", ["infant_id"]
    )
    HIC_SUSPEND_COUNT = Counter(
        "hic_suspend_count_total", "Times entered suspend", ["infant_id"]
    )
    HIC_BREATH_STATE = Gauge(
        "hic_breath_state",
        "Current breath state (1=contract,2=diffuse,3=suspend)",
        ["infant_id"],
    )

    # SympNet metrics
    SYMNET_ENERGY_DRIFT = Gauge(
        "sympnet_energy_drift_ratio", "Energy drift ratio", ["infant_id"]
    )
    SYMNET_ADAPTATIONS = Counter(
        "sympnet_adaptations_total", "Number of self-adaptations", ["infant_id"]
    )

    # Packet metrics
    PACKETS_SENT = Counter(
        "cosmic_packets_sent_total", "Packets sent", ["infant_id", "flow_type"]
    )
    PACKETS_RECEIVED = Counter(
        "cosmic_packets_received_total", "Packets received", ["infant_id", "flow_type"]
    )
    PACKETS_TTL_EXPIRED = Counter(
        "cosmic_packet_ttl_expired_total", "Packets expired (TTL)", ["infant_id"]
    )
    PACKET_LATENCY = Histogram(
        "cosmic_packet_latency_seconds",
        "Packet end-to-end delivery latency (source → destination)",
        ["source_id", "destination_id"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    # Myelination metrics
    MYELINATION_PATHS = Gauge(
        "myelination_path_count", "Number of myelinated paths", ["infant_id"]
    )
    MYELINATION_COVERAGE = Gauge(
        "myelination_coverage_ratio", "Wisdom encoding coverage", ["infant_id"]
    )

    # Resonance metrics
    RESONANCE_SIMILARITY = Gauge(
        "mycelium_resonance_similarity",
        "Vector cosine similarity",
        ["source_id", "destination_id"],
    )
    RESONANCE_PAIRS = Gauge(
        "mycelium_resonance_pairs_total",
        "Number of high-resonance node pairs",
        ["network_name"],
    )

    # Cluster metrics
    CLUSTER_NODES_TOTAL = Gauge(
        "cluster_nodes_total", "Total nodes in cluster", ["node_manager_id"]
    )
    CLUSTER_NODES_ACTIVE = Gauge(
        "cluster_nodes_active", "Active (healthy) nodes", ["node_manager_id"]
    )
    CLUSTER_NODES_FAILED = Gauge(
        "cluster_nodes_failed", "Failed nodes", ["node_manager_id"]
    )
    CLUSTER_NODES_DEGRADED = Gauge(
        "cluster_nodes_degraded", "Degraded nodes", ["node_manager_id"]
    )
    CLUSTER_TOTAL_ENERGY = Gauge(
        "cluster_total_energy", "Sum energy across all nodes", ["node_manager_id"]
    )

    # FlowRouter metrics
    ROUTES_CACHED = Gauge(
        "flowrouter_routes_cached", "Number of cached routes", ["router_id"]
    )
    ROUTES_VALID = Gauge(
        "flowrouter_routes_valid", "Number of valid routes", ["router_id"]
    )
    TOPOLOGY_NODES = Gauge(
        "flowrouter_topology_nodes", "Nodes in topology graph", ["router_id"]
    )
    PACKETS_ROUTED = Counter(
        "flowrouter_packets_routed_total", "Packets routed", ["router_id"]
    )
    BROADCASTS_FLOODED = Counter(
        "flowrouter_broadcasts_total", "Broadcasts sent", ["router_id"]
    )

    # CollectiveIntelligence metrics
    CI_PROPOSALS_PENDING = Gauge(
        "ci_proposals_pending", "Pending workspace proposals", ["node_id"]
    )
    CI_PROPOSALS_ACTIVE = Gauge(
        "ci_proposals_active", "Active (non-expired) proposals", ["node_id"]
    )
    CI_WORKSPACE_ACTIVE = Gauge(
        "ci_workspace_active", "Cluster workspace active (1/0)", ["node_id"]
    )
    CI_ITERATION = Gauge(
        "ci_iteration", "Current cluster workspace iteration", ["node_id"]
    )
    CI_ATTENTION_WINNERS = Counter(
        "ci_attention_winners_total", "Times node won attention", ["node_id"]
    )

    # Knowledge Store metrics
    KNOWLEDGE_RECALL_HITS = Counter(
        "knowledge_recall_hits_total", "Successful semantic recall queries", ["infant_id"]
    )
    KNOWLEDGE_RECALL_MISSES = Counter(
        "knowledge_recall_misses_total", "Recall queries with zero results", ["infant_id"]
    )
    KNOWLEDGE_ENTRIES_TOTAL = Gauge(
        "knowledge_entries_total", "Total KnowledgeEntry count", ["infant_id"]
    )

    # Research cycle metrics
    RESEARCH_CYCLES_TOTAL = Counter(
        "research_cycles_total", "Research cycles attempted", ["infant_id"]
    )
    RESEARCH_SUCCESS_TOTAL = Counter(
        "research_success_total", "Research cycles producing an entry", ["infant_id"]
    )
    RESEARCH_ERRORS_TOTAL = Counter(
        "research_errors_total", "Research cycle exceptions", ["infant_id"]
    )


@dataclass
class MetricsServer:
    """
    HTTP server exposing /metrics endpoint for Prometheus.
    Runs alongside infant node.
    """

    port: int = 8000
    _runner: web.AppRunner | None = None
    _site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start metrics server."""
        if not PROMETHEUS_AVAILABLE:
            print("Warning: prometheus_client not installed, metrics disabled")
            return

        app = web.Application()
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/health/ready", self._handle_health_ready)
        app.router.add_get("/health/live", self._handle_health_live)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        print(f"Metrics server listening on :{self.port}")

    async def stop(self) -> None:
        """Stop metrics server."""
        if self._runner:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics request."""
        metrics = generate_latest(REGISTRY)
        # Prometheus content type is "text/plain; version=0.0.4"
        # aiohttp forbids charset in content_type string when charset param is also used
        # so we strip any charset from CONTENT_TYPE_LATEST and pass charset separately
        base_type = CONTENT_TYPE_LATEST.split(";")[0].strip()  # "text/plain"
        version = [p.strip() for p in CONTENT_TYPE_LATEST.split(";") if "version" in p]
        content_type = base_type
        if version:
            content_type += "; " + version[0]
        return web.Response(
            body=metrics,
            content_type=content_type,
            charset="utf-8",
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health request — overall health."""
        return web.json_response({"status": "ok", "service": "cosmic-infant"})

    async def _handle_health_ready(self, request: web.Request) -> web.Response:
        """Readiness probe — checks cluster connectivity."""
        return web.json_response({"status": "ready"})

    async def _handle_health_live(self, request: web.Request) -> web.Response:
        """Liveness probe — always ok if process running."""
        return web.json_response({"status": "alive"})


# =============================================================================
# Metric Collector — aggregates cluster component metrics
# =============================================================================
class MetricsCollector:
    """
    Collects and updates Prometheus metrics from cluster components.
    Call update_* methods periodically or after state changes.
    """

    @staticmethod
    def collect_infant_metrics(infant_id: str, infant_obj: Any) -> None:
        """Pull metrics from a SiliconInfant instance."""
        if not PROMETHEUS_AVAILABLE:
            return

        # HIC energy
        if hasattr(infant_obj, "hic") and hasattr(infant_obj.hic, "energy"):
            HIC_ENERGY.labels(infant_id=infant_id).set(infant_obj.hic.energy)
        if hasattr(infant_obj, "hic") and hasattr(infant_obj.hic, "state"):
            state_val = {
                "CONTRACT": 1,
                "DIFFUSE": 2,
                "SUSPEND": 3,
            }.get(infant_obj.hic.state.value, 0)
            HIC_BREATH_STATE.labels(infant_id=infant_id).set(state_val)

        # SympNet
        if hasattr(infant_obj, "sympnet") and hasattr(infant_obj.sympnet, "get_health"):
            health = infant_obj.sympnet.get_health()
            if isinstance(health, dict):
                SYMNET_ENERGY_DRIFT.labels(infant_id=infant_id).set(
                    health.get("avg_drift", 0.0)
                )

        # Myelination
        if hasattr(infant_obj, "memory"):
            MYELINATION_PATHS.labels(infant_id=infant_id).set(
                len(getattr(infant_obj.memory, "path_strengths", {}))
            )
            if hasattr(infant_obj.memory, "get_coverage"):
                coverage = infant_obj.memory.get_coverage()
                MYELINATION_COVERAGE.labels(infant_id=infant_id).set(coverage)

        # Knowledge Store
        if hasattr(infant_obj, "knowledge_store") and infant_obj.knowledge_store is not None:
            MetricsCollector.collect_knowledge_store_metrics(infant_id, infant_obj.knowledge_store)

    @staticmethod
    def collect_node_manager_metrics(nm: NodeManager, nm_id: str = "default") -> None:
        """Update NodeManager cluster health metrics."""
        if not PROMETHEUS_AVAILABLE or not CLUSTER_AVAILABLE:
            return

        status = nm.get_cluster_status()
        CLUSTER_NODES_TOTAL.labels(node_manager_id=nm_id).set(status["total_nodes"])
        CLUSTER_NODES_ACTIVE.labels(node_manager_id=nm_id).set(status["active_nodes"])
        CLUSTER_TOTAL_ENERGY.labels(node_manager_id=nm_id).set(status["total_energy"])
        failed = sum(1 for n in nm.nodes.values() if n.status.value == "failed")
        degraded = sum(1 for n in nm.nodes.values() if n.status.value == "degraded")
        CLUSTER_NODES_FAILED.labels(node_manager_id=nm_id).set(failed)
        CLUSTER_NODES_DEGRADED.labels(node_manager_id=nm_id).set(degraded)

    @staticmethod
    def collect_flow_router_metrics(
        router: FlowRouter, router_id: str = "default"
    ) -> None:
        """Update FlowRouter metrics."""
        if not PROMETHEUS_AVAILABLE or not CLUSTER_AVAILABLE:
            return

        status = router.get_router_status()
        TOPOLOGY_NODES.labels(router_id=router_id).set(status["topology_nodes"])
        ROUTES_CACHED.labels(router_id=router_id).set(status["total_routes_cached"])
        ROUTES_VALID.labels(router_id=router_id).set(status["valid_routes"])
        stats = status.get("stats", {})
        PACKETS_ROUTED.labels(router_id=router_id).inc(stats.get("packets_routed", 0))
        BROADCASTS_FLOODED.labels(router_id=router_id).inc(
            stats.get("broadcasts_flooded", 0)
        )

    @staticmethod
    def collect_collective_intelligence_metrics(
        ci: CollectiveIntelligence, node_id: str
    ) -> None:
        """Update CollectiveIntelligence metrics."""
        if not PROMETHEUS_AVAILABLE or not CLUSTER_AVAILABLE:
            return

        status = ci.get_cluster_status()
        CI_PROPOSALS_PENDING.labels(node_id=node_id).set(status["total_proposals"])
        CI_PROPOSALS_ACTIVE.labels(node_id=node_id).set(status["active_proposals"])
        CI_WORKSPACE_ACTIVE.labels(node_id=node_id).set(
            1 if status["workspace_active"] else 0
        )
        CI_ITERATION.labels(node_id=node_id).set(status["iteration"])

    @staticmethod
    def collect_network_metrics(
        network: MyceliumNetwork, network_name: str = "default"
    ) -> None:
        """Update MyceliumNetwork metrics."""
        if not PROMETHEUS_AVAILABLE or not CLUSTER_AVAILABLE:
            return

        status = network.get_status()
        RESONANCE_PAIRS.labels(network_name=network_name).set(status["resonance_pairs"])

    @staticmethod
    def collect_knowledge_store_metrics(infant_id: str, store: Any) -> None:
        """Update KnowledgeStore metrics."""
        if not PROMETHEUS_AVAILABLE:
            return

        stats = store.get_stats()
        KNOWLEDGE_ENTRIES_TOTAL.labels(infant_id=infant_id).set(stats["total_entries"])

    @staticmethod
    def record_recall_hit(infant_id: str) -> None:
        """Record a successful semantic recall (at least one result)."""
        if not PROMETHEUS_AVAILABLE:
            return
        KNOWLEDGE_RECALL_HITS.labels(infant_id=infant_id).inc()

    @staticmethod
    def record_recall_miss(infant_id: str) -> None:
        """Record a recall query that returned zero results."""
        if not PROMETHEUS_AVAILABLE:
            return
        KNOWLEDGE_RECALL_MISSES.labels(infant_id=infant_id).inc()

    @staticmethod
    def record_research_cycle(infant_id: str, success: bool = True, error: bool = False) -> None:
        """
        Record a research cycle outcome.

        Args:
            infant_id: Infant identifier
            success: True if experiment produced an entry
            error: True if exception was raised
        """
        if not PROMETHEUS_AVAILABLE:
            return
        RESEARCH_CYCLES_TOTAL.labels(infant_id=infant_id).inc()
        if error:
            RESEARCH_ERRORS_TOTAL.labels(infant_id=infant_id).inc()
        elif success:
            RESEARCH_SUCCESS_TOTAL.labels(infant_id=infant_id).inc()
