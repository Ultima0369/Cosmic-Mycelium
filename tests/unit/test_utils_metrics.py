"""
Unit Tests: utils.metrics — Prometheus Metrics Server
Tests for MetricsServer HTTP endpoints and Prometheus integration.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cosmic_mycelium.utils.metrics import (
    CLUSTER_AVAILABLE,
    MetricsCollector,
    MetricsServer,
    PACKET_LATENCY,
    PROMETHEUS_AVAILABLE,
)


class TestMetricsServer:
    """Tests for the Prometheus metrics HTTP server."""

    @pytest.mark.asyncio
    async def test_start_without_prometheus(self):
        """When prometheus_client not installed, start prints warning and returns."""
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            server = MetricsServer(port=9090)
            # Should not raise; just print warning
            await server.start()
            # No runner/site created
            assert server._runner is None

    @pytest.mark.asyncio
    async def test_start_creates_http_app(self):
        """start() sets up aiohttp app with /metrics and /health routes."""
        with (
            patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True),
            patch("aiohttp.web.AppRunner") as mock_runner_cls,
            patch("aiohttp.web.TCPSite") as mock_site_cls,
        ):

            mock_runner = AsyncMock()
            mock_runner_cls.return_value = mock_runner
            mock_site = AsyncMock()
            mock_site_cls.return_value = mock_site

            server = MetricsServer(port=9091)
            await server.start()

            # App created and routes registered
            assert mock_runner.setup.called
            assert mock_site.start.called
            assert server._runner is mock_runner
            assert server._site is mock_site

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self):
        """stop() cleans up runner if started."""
        with (
            patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True),
            patch("aiohttp.web.AppRunner") as mock_runner_cls,
            patch("aiohttp.web.TCPSite") as mock_site_cls,
        ):

            mock_runner = AsyncMock()
            mock_runner_cls.return_value = mock_runner
            mock_site = AsyncMock()
            mock_site_cls.return_value = mock_site

            server = MetricsServer()
            await server.start()
            await server.stop()

            mock_runner.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_metrics_returns_prometheus_format(self):
        """_handle_metrics returns text/plain with Prometheus exposition format."""
        with (
            patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True),
            patch("aiohttp.web.AppRunner"),
            patch("aiohttp.web.TCPSite"),
            patch("cosmic_mycelium.utils.metrics.generate_latest") as mock_gen,
        ):

            mock_gen.return_value = (
                b"# HELP hic_energy_total\n# TYPE hic_energy_total gauge\n"
            )

            server = MetricsServer()
            mock_request = MagicMock()
            response = await server._handle_metrics(mock_request)

            # Content type includes text/plain with charset
            assert "text/plain" in response.content_type
            body = response.body.decode()
            assert "hic_energy_total" in body

    @pytest.mark.asyncio
    async def test_handle_health_returns_ok(self):
        """_handle_health returns simple JSON {status: ok}."""
        with (
            patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True),
            patch("aiohttp.web.AppRunner"),
            patch("aiohttp.web.TCPSite"),
        ):

            server = MetricsServer()
            mock_request = MagicMock()
            response = await server._handle_health(mock_request)

            assert response.content_type == "application/json"
            body = json.loads(response.body.decode())
            assert body["status"] == "ok"
            # May include additional fields like 'service'

    @pytest.mark.asyncio
    async def test_start_when_prometheus_disabled_graceful(self):
        """start() with PROMETHEUS_AVAILABLE=False is a no-op."""
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            server = MetricsServer()
            await server.start()
            # Should not have created any aiohttp resources
            assert server._runner is None
            assert server._site is None


class TestMetricsCollector:
    """Tests for MetricsCollector static methods."""

    def test_collect_infant_metrics_missing_hic(self):
        """collect_infant_metrics handles infant without hic gracefully."""
        infant = MagicMock(spec=[])  # No hic attribute
        # Should not raise
        MetricsCollector.collect_infant_metrics("test-infant", infant)

    def test_collect_infant_metrics_missing_energy(self):
        """collect_infant_metrics handles hic without energy."""
        infant = MagicMock()
        infant.hic = MagicMock(spec=[])  # No energy attribute
        MetricsCollector.collect_infant_metrics("test-infant", infant)

    def test_collect_infant_metrics_missing_state(self):
        """collect_infant_metrics handles hic without state."""
        infant = MagicMock()
        infant.hic = MagicMock()
        infant.hic.energy = 50.0
        infant.hic.state = MagicMock()
        infant.hic.state.value = "UNKNOWN"
        # Should not raise; sets state to 0
        MetricsCollector.collect_infant_metrics("test-infant", infant)

    def test_collect_infant_metrics_sympnet_health_not_dict(self):
        """collect_infant_metrics handles non-dict sympnet health."""
        infant = MagicMock()
        infant.hic = MagicMock(energy=50.0, state=MagicMock(value="CONTRACT"))
        infant.sympnet = MagicMock()
        infant.sympnet.get_health.return_value = "not-a-dict"
        # Should not raise
        MetricsCollector.collect_infant_metrics("test-infant", infant)

    def test_collect_infant_metrics_memory_without_coverage(self):
        """collect_infant_metrics handles memory without get_coverage method."""
        infant = MagicMock()
        infant.hic = MagicMock(energy=50.0, state=MagicMock(value="CONTRACT"))
        infant.sympnet = MagicMock(get_health=lambda: {})
        infant.memory = MagicMock(spec=[])  # No get_coverage
        infant.memory.path_strengths = {}
        # Should not raise
        MetricsCollector.collect_infant_metrics("test-infant", infant)

    @patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False)
    def test_collect_infant_metrics_prometheus_disabled(self):
        """collect_infant_metrics no-ops when Prometheus unavailable."""
        infant = MagicMock()
        MetricsCollector.collect_infant_metrics("test", infant)
        # No exception = pass

    def test_collect_node_manager_metrics_prometheus_disabled(self):
        """collect_node_manager_metrics no-ops when Prometheus unavailable."""
        nm = MagicMock()
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            MetricsCollector.collect_node_manager_metrics(nm, "test")

    def test_collect_flow_router_metrics_prometheus_disabled(self):
        """collect_flow_router_metrics no-ops when Prometheus unavailable."""
        router = MagicMock()
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            MetricsCollector.collect_flow_router_metrics(router, "test")

    def test_collect_collective_intelligence_metrics_prometheus_disabled(self):
        """collect_collective_intelligence_metrics no-ops when Prometheus unavailable."""
        ci = MagicMock()
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            MetricsCollector.collect_collective_intelligence_metrics(ci, "test")

    def test_collect_network_metrics_prometheus_disabled(self):
        """collect_network_metrics no-ops when Prometheus unavailable."""
        network = MagicMock()
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            MetricsCollector.collect_network_metrics(network, "test")

    def test_packet_latency_histogram_buckets(self):
        """PACKET_LATENCY histogram has appropriate buckets for P99 < 100ms."""
        # Buckets should include 0.1s (100ms) boundary
        buckets = PACKET_LATENCY._kwargs.get("buckets", ())
        assert 0.1 in buckets or any(b <= 0.1 for b in buckets)
        # Should have finer buckets too (for P50, P95 tracking)
        assert len(buckets) >= 8

    @patch("cosmic_mycelium.utils.metrics.CLUSTER_AVAILABLE", False)
    def test_collect_node_manager_metrics_cluster_unavailable(self):
        """collect_node_manager_metrics no-ops when cluster modules unavailable."""
        nm = MagicMock()
        MetricsCollector.collect_node_manager_metrics(nm, "test")

    @patch("cosmic_mycelium.utils.metrics.CLUSTER_AVAILABLE", False)
    def test_collect_flow_router_metrics_cluster_unavailable(self):
        """collect_flow_router_metrics no-ops when cluster modules unavailable."""
        router = MagicMock()
        MetricsCollector.collect_flow_router_metrics(router, "test")

    @patch("cosmic_mycelium.utils.metrics.CLUSTER_AVAILABLE", False)
    def test_collect_collective_intelligence_metrics_cluster_unavailable(self):
        """collect_collective_intelligence_metrics no-ops when cluster unavailable."""
        ci = MagicMock()
        MetricsCollector.collect_collective_intelligence_metrics(ci, "test")

    @patch("cosmic_mycelium.utils.metrics.CLUSTER_AVAILABLE", False)
    def test_collect_network_metrics_cluster_unavailable(self):
        """collect_network_metrics no-ops when cluster modules unavailable."""
        network = MagicMock()
        MetricsCollector.collect_network_metrics(network, "test")
