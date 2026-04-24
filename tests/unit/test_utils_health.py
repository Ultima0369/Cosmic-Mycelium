"""
Unit Tests: utils.health — Health Checker
Tests for K8s liveness/readiness probe endpoints.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from cosmic_mycelium.infant.hic import BreathState
from cosmic_mycelium.utils.health import HealthChecker


class MockInfant:
    """Mock SiliconInfant with hic.energy and hic.breath_state."""

    class MockHIC:
        def __init__(self, energy: float, state: BreathState):
            self.energy = energy
            self.breath_state = state

    def __init__(
        self, energy: float = 100.0, state: BreathState = BreathState.CONTRACT
    ):
        self.hic = self.MockHIC(energy, state)


@pytest.mark.asyncio
class TestHealthCheckerLiveness:
    """Liveness probe tests."""

    async def test_liveness_returns_200(self):
        """Liveness endpoint always returns 200 with alive status."""
        checker = HealthChecker()
        result = await checker._handle_liveness(None)
        assert result.status == 200
        body = json.loads(result.body.decode())
        assert body["status"] == "alive"

    async def test_readiness_ready_when_energy_positive(self):
        """Readiness returns 200 when infant energy > 0."""
        checker = HealthChecker(infant=MockInfant(energy=50.0))
        result = await checker._handle_readiness(None)
        assert result.status == 200
        body = json.loads(result.body.decode())
        assert body["status"] == "ready"
        assert body["energy"] == 50.0

    async def test_readiness_not_ready_when_energy_zero(self):
        """Readiness returns 503 when energy is 0."""
        checker = HealthChecker(infant=MockInfant(energy=0.0))
        result = await checker._handle_readiness(None)
        assert result.status == 503
        body = json.loads(result.body.decode())
        assert body["status"] == "not_ready"
        assert body["reason"] == "energy_depleted"

    async def test_readiness_without_infant_set(self):
        """Readiness returns 503 when infant not configured."""
        checker = HealthChecker(infant=None)
        result = await checker._handle_readiness(None)
        assert result.status == 503

    async def test_combined_endpoint_healthy(self):
        """Combined /health returns ok when ready."""
        checker = HealthChecker(infant=MockInfant(energy=50.0))
        result = await checker._handle_combined(None)
        assert result.status == 200
        body = json.loads(result.body.decode())
        assert body["status"] == "ok"
        assert body["liveness"]["status"] == "alive"
        assert body["readiness"]["status"] == "ready"

    async def test_combined_endpoint_degraded(self):
        """Combined /health returns degraded when not ready."""
        checker = HealthChecker(infant=MockInfant(energy=0.0))
        result = await checker._handle_combined(None)
        assert result.status == 503
        body = json.loads(result.body.decode())
        assert body["status"] == "degraded"


class TestHealthCheckerLifecycle:
    """Tests for start() and stop() lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_sets_up_router(self):
        """start() configures health endpoints on the app."""
        mock_runner = AsyncMock()

        with (
            patch("cosmic_mycelium.utils.health.web.Application") as mock_app_cls,
            patch(
                "cosmic_mycelium.utils.health.web.AppRunner", return_value=mock_runner
            ),
            patch("cosmic_mycelium.utils.health.web.TCPSite") as mock_site_class,
        ):
            mock_site = AsyncMock()
            mock_site_class.return_value = mock_site

            checker = HealthChecker(port=8080)
            await checker.start()

            mock_app_cls.assert_called_once()
            mock_runner.setup.assert_awaited_once()
            mock_site_class.assert_called_once()
            mock_site.start.assert_awaited_once()
            assert checker._runner is mock_runner

    @pytest.mark.asyncio
    async def test_stop_cleans_up_when_started(self):
        """stop() cleans up the runner if it exists."""
        checker = HealthChecker()
        mock_runner = AsyncMock()
        checker._runner = mock_runner

        await checker.stop()

        mock_runner.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_does_nothing_when_not_started(self):
        """stop() is safe to call even if start() was never called."""
        checker = HealthChecker()

        # Should not raise
        await checker.stop()

        assert checker._runner is None
