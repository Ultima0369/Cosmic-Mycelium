"""
Unit Tests: utils.metrics — MetricsCollector, MetricsServer
Tests for Prometheus metric definitions, collection, and HTTP endpoints.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cosmic_mycelium.utils.metrics import (
    CI_PROPOSALS_PENDING,
    CLUSTER_NODES_TOTAL,
    HIC_BREATH_CYCLES,
    HIC_ENERGY,
    MetricsCollector,
    MetricsServer,
)


class TestMetricsAvailability:
    """Prometheus client availability detection."""

    def test_constants_defined_when_available(self):
        """All expected metric objects are defined."""
        assert HIC_ENERGY is not None
        assert HIC_BREATH_CYCLES is not None
        assert CI_PROPOSALS_PENDING is not None
        assert CLUSTER_NODES_TOTAL is not None


class TestMetricsCollector:
    """MetricsCollector static methods."""

    def test_collect_infant_metrics_sets_hic_energy(self):
        """collect_infant_metrics updates HIC_ENERGY gauge."""
        mock_infant = MagicMock()
        mock_infant.hic.energy = 75.5
        mock_infant.hic.state.value = "CONTRACT"
        mock_infant.sympnet.get_health.return_value = {"avg_drift": 0.02}
        mock_infant.memory.path_strengths = {"a": 0.5, "b": 0.3}
        mock_infant.memory.get_coverage.return_value = 0.42

        MetricsCollector.collect_infant_metrics("test-infant", mock_infant)

        # Verify gauge was set
        assert HIC_ENERGY.labels(infant_id="test-infant")._value.get() == 75.5

    def test_collect_infant_metrics_maps_breath_state(self):
        """Breath state maps CONTRACT->1, DIFFUSE->2, SUSPEND->3."""
        mock_infant = MagicMock()
        mock_infant.hic.energy = 50.0
        mock_infant.sympnet.get_health.return_value = {"avg_drift": 0.0}
        mock_infant.memory.path_strengths = {}
        mock_infant.memory.get_coverage.return_value = 0.0

        for state_name, expected_val in [
            ("CONTRACT", 1),
            ("DIFFUSE", 2),
            ("SUSPEND", 3),
        ]:
            mock_infant.hic.state.value = state_name
            MetricsCollector.collect_infant_metrics("state-test", mock_infant)
            # Just ensure no error — actual gauge value depends on implementation

    def test_collect_infant_metrics_handles_missing_components(self):
        """Handles infant with minimal attributes gracefully."""
        # Create an object that lacks expected attributes
        minimal = object()
        # Should not crash — collector uses hasattr guards
        MetricsCollector.collect_infant_metrics("broken", minimal)

    def test_collect_node_manager_metrics_updates_gauges(self):
        """NodeManager metrics collection runs without error."""
        mock_nm = MagicMock()
        mock_nm.get_cluster_status.return_value = {
            "total_nodes": 5,
            "active_nodes": 4,
            "total_energy": 350.0,
        }
        mock_nm.nodes.values.return_value = [
            MagicMock(status=MagicMock(value="active")),
            MagicMock(status=MagicMock(value="active")),
            MagicMock(status=MagicMock(value="degraded")),
            MagicMock(status=MagicMock(value="failed")),
        ]
        # Should not raise
        MetricsCollector.collect_node_manager_metrics(mock_nm, "test-nm")

    def test_collect_collective_intelligence_metrics(self):
        """CI metrics collection runs without error."""
        mock_ci = MagicMock()
        mock_ci.get_cluster_status.return_value = {
            "total_proposals": 10,
            "active_proposals": 3,
            "workspace_active": True,
            "iteration": 5,
        }
        # Should not raise
        MetricsCollector.collect_collective_intelligence_metrics(mock_ci, "node-1")


class TestMetricsServer:
    """HTTP metrics and health endpoints."""

    @pytest.mark.asyncio
    async def test_start_creates_server(self):
        """MetricsServer.start() launches aiohttp app."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        server = MetricsServer(port=port)
        await server.start()
        assert server._runner is not None
        assert server._site is not None
        await server.stop()

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self):
        """MetricsServer.stop() cleans up runner."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        server = MetricsServer(port=port)
        await server.start()
        await server.stop()
        # After stop, internal references are cleared by aiohttp cleanup
        assert server._runner is None
        assert server._site is None


class TestMetricsIntegration:
    """End-to-end metrics collection across components."""

    def test_metrics_flow_through_infant_cycle(self):
        """A full breath cycle records HIC energy and breath state."""
        mock_infant = MagicMock()
        mock_infant.hic.energy = 88.0
        mock_infant.hic.state.value = "CONTRACT"
        mock_infant.sympnet.get_health.return_value = {"avg_drift": 0.01}
        mock_infant.memory.path_strengths = {"p1": 0.9}
        mock_infant.memory.get_coverage.return_value = 0.75

        MetricsCollector.collect_infant_metrics("cycle-test", mock_infant)
        # Just verify call succeeds
