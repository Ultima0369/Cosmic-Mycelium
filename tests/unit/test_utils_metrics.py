"""
Unit Tests: utils.metrics — Prometheus Metrics Server
Tests for MetricsServer HTTP endpoints and Prometheus integration.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from aiohttp import web

from cosmic_mycelium.utils.metrics import MetricsServer, PROMETHEUS_AVAILABLE


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
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True), \
             patch("aiohttp.web.AppRunner") as mock_runner_cls, \
             patch("aiohttp.web.TCPSite") as mock_site_cls:

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
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True), \
             patch("aiohttp.web.AppRunner") as mock_runner_cls, \
             patch("aiohttp.web.TCPSite") as mock_site_cls:

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
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True), \
             patch("aiohttp.web.AppRunner"), \
             patch("aiohttp.web.TCPSite"), \
             patch("cosmic_mycelium.utils.metrics.generate_latest") as mock_gen:

            mock_gen.return_value = b"# HELP hic_energy_total\n# TYPE hic_energy_total gauge\n"

            server = MetricsServer()
            mock_request = MagicMock()
            response = await server._handle_metrics(mock_request)

            assert "text/plain" in response.content_type
            body = response.body.decode()
            assert "hic_energy_total" in body

    @pytest.mark.asyncio
    async def test_handle_health_returns_ok(self):
        """_handle_health returns simple JSON {status: ok}."""
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", True), \
             patch("aiohttp.web.AppRunner"), \
             patch("aiohttp.web.TCPSite"):

            server = MetricsServer()
            mock_request = MagicMock()
            response = await server._handle_health(mock_request)

            assert response.content_type == "application/json"
            body = json.loads(response.body.decode())
            assert body == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_start_when_prometheus_disabled_graceful(self):
        """start() with PROMETHEUS_AVAILABLE=False is a no-op."""
        with patch("cosmic_mycelium.utils.metrics.PROMETHEUS_AVAILABLE", False):
            server = MetricsServer()
            await server.start()
            # Should not have created any aiohttp resources
            assert server._runner is None
            assert server._site is None
