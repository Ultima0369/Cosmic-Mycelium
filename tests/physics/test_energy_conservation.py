"""
Cosmic Mycelium — Physics Validation Tests
These tests verify the "Physical Anchor" — energy conservation < 0.1%.
FAILING THESE TESTS MEANS THE FOUNDATION IS COMPROMISED.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

# Add project root
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))


@pytest.mark.physics
class TestEnergyConservation:
    """Energy conservation is the sacred threshold."""

    TOLERANCE = 0.001  # 0.1%

    def test_sho_energy_conservation_10k_steps(self):
        """Simple Harmonic Oscillator: energy drift < 0.1% over 10k steps."""
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
        q, p = 1.0, 0.0
        dt = 0.01
        steps = 10_000

        initial = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
        final = engine.compute_energy(q, p)

        drift = abs(final - initial) / max(initial, 1e-9)
        assert drift < self.TOLERANCE, (
            f"Energy drift {drift:.6%} exceeds threshold {self.TOLERANCE:.6%}"
        )

    @pytest.mark.parametrize("steps", [1_000, 10_000, 100_000, 1_000_000])
    def test_energy_conservation_scales(self, steps):
        """Drift stays bounded even over 1M steps."""
        engine = SympNetEngine()
        q, p = 1.0, 0.5
        dt = 0.01

        initial = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
        final = engine.compute_energy(q, p)

        drift = abs(final - initial) / max(initial, 1e-9)
        assert drift < self.TOLERANCE

    @pytest.mark.parametrize("dt", [0.001, 0.01, 0.05, 0.1])
    def test_energy_conservation_various_dt(self, dt):
        """Anchor holds across reasonable timestep choices."""
        engine = SympNetEngine()
        q, p = 1.0, 0.0
        steps = int(1.0 / dt) * 1000  # 1000 periods

        initial = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
        final = engine.compute_energy(q, p)

        drift = abs(final - initial) / max(initial, 1e-9)
        assert drift < self.TOLERANCE


@pytest.mark.physics
class TestSymplecticStructure:
    """Symplectic integrators preserve phase space volume."""

    def test_reversibility(self):
        """Forward-backward returns to start (reversibility)."""
        engine = SympNetEngine()
        q, p = 1.234, -0.567
        dt = 0.01

        q1, p1 = engine.step(q, p, dt)
        q_back, p_back = engine.step(q1, -p1, -dt)

        assert abs(q_back - q) < 1e-10
        assert abs(p_back - p) < 1e-10

    def test_phase_space_area_preservation(self):
        """Parallelogram area in phase space is preserved."""
        engine = SympNetEngine()
        q0, p0 = 1.0, 0.0
        eps = 1e-6
        steps = 1000
        dt = 0.01

        # Initial triangle area
        p1 = p0 + eps
        points0 = [(q0, p0), (q0, p1), (q0 + eps, p0)]
        area0 = abs(
            (points0[1][0] - points0[0][0]) * (points0[2][1] - points0[0][1])
            - (points0[2][0] - points0[0][0]) * (points0[1][1] - points0[0][1])
        )

        # Evolve all points
        points1 = []
        for q, p in points0:
            for _ in range(steps):
                q, p = engine.step(q, p, dt)
            points1.append((q, p))

        area1 = abs(
            (points1[1][0] - points1[0][0]) * (points1[2][1] - points1[0][1])
            - (points1[2][0] - points1[0][0]) * (points1[1][1] - points1[0][1])
        )

        ratio = area1 / area0
        assert 0.99 < ratio < 1.01, f"Area ratio {ratio:.6f} out of bounds"


@pytest.mark.physics
class TestDampedDynamics:
    """Damped oscillator should lose energy monotonically."""

    def test_energy_monotonic_decrease(self):
        """With damping > 0, energy never increases."""
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.1)
        q, p = 1.0, 0.0
        dt = 0.01
        steps = 1000

        energies = []
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
            energies.append(engine.compute_energy(q, p))

        # Non-increasing sequence
        assert all(energies[i] >= energies[i+1] for i in range(len(energies)-1))

    def test_energy_eventually_approaches_zero(self):
        """Damped oscillator approaches rest."""
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.5)
        q, p = 10.0, 0.0
        dt = 0.01
        steps = 10_000

        for _ in range(steps):
            q, p = engine.step(q, p, dt)

        energy = engine.compute_energy(q, p)
        assert energy < 1e-6  # Essentially at rest


if __name__ == "__main__":
    # Run physics tests standalone
    pytest.main([__file__, "-v", "-m", "physics"])
