"""
Metrics Server — Prometheus Metrics Endpoint
Exposes infant metrics for Prometheus scraping.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from aiohttp import web

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# Define metrics
if PROMETHEUS_AVAILABLE:
    # HIC metrics
    HIC_ENERGY = Gauge("hic_energy_total", "Current HIC energy", ["infant_id"])
    HIC_BREATH_CYCLES = Counter("hic_breath_cycles_total", "Total breath cycles", ["infant_id"])
    HIC_SUSPEND_COUNT = Counter("hic_suspend_count_total", "Times entered suspend", ["infant_id"])

    # SympNet metrics
    SYMNET_ENERGY_DRIFT = Gauge("sympnet_energy_drift_ratio", "Energy drift ratio", ["infant_id"])
    SYMNET_ADAPTATIONS = Counter("sympnet_adaptations_total", "Number of self-adaptations", ["infant_id"])

    # Packet metrics
    PACKETS_SENT = Counter("cosmic_packets_sent_total", "Packets sent", ["infant_id", "flow_type"])
    PACKETS_RECEIVED = Counter("cosmic_packets_received_total", "Packets received", ["infant_id", "flow_type"])
    PACKETS_TTL_EXPIRED = Counter("cosmic_packet_ttl_expired_total", "Packets expired (TTL)", ["infant_id"])

    # Myelination metrics
    MYELINATION_PATHS = Gauge("myelination_path_count", "Number of myelinated paths", ["infant_id"])
    MYELINATION_COVERAGE = Gauge("myelination_coverage_ratio", "Wisdom encoding coverage", ["infant_id"])

    # Resonance metrics
    RESONANCE_SIMILARITY = Gauge("mycelium_resonance_similarity", "Vector cosine similarity", ["source_id", "destination_id"])

    # Breath state
    BREATH_STATE = Gauge("breath_state", "Current breath state (1=contract,2=diffuse,3=suspend)", ["infant_id", "state"])


@dataclass
class MetricsServer:
    """
    HTTP server exposing /metrics endpoint for Prometheus.
    Runs alongside infant node.
    """
    port: int = 8000
    _runner: Optional[web.AppRunner] = None
    _site: Optional[web.TCPSite] = None

    async def start(self) -> None:
        """Start metrics server."""
        if not PROMETHEUS_AVAILABLE:
            print("Warning: prometheus_client not installed, metrics disabled")
            return

        app = web.Application()
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        print(f"Metrics server listening on :{self.port}")

    async def stop(self) -> None:
        """Stop metrics server."""
        if self._runner:
            await self._runner.cleanup()

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics request."""
        metrics = generate_latest()
        return web.Response(
            body=metrics,
            content_type="text/plain",
            charset="utf-8",
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health request."""
        return web.json_response({"status": "ok"})
