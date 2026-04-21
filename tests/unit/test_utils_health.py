"""
Unit Tests: utils.health — Health Checker
Tests for K8s liveness/readiness probe endpoints.
"""

from __future__ import annotations

import json
import pytest
from cosmic_mycelium.utils.health import HealthChecker
from cosmic_mycelium.infant.hic import BreathState


class MockInfant:
    """Mock SiliconInfant with hic.energy and hic.breath_state."""
    class MockHIC:
        def __init__(self, energy: float, state: BreathState):
            self.energy = energy
            self.breath_state = state

    def __init__(self, energy: float = 100.0, state: BreathState = BreathState.CONTRACT):
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