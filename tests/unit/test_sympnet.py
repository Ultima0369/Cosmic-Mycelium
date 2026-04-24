"""
Cosmic Mycelium — Unit Tests: SympNet Engine
Tests the "物理为锚" — energy conservation, symplectic integration, adaptation.
"""

from __future__ import annotations

import numpy as np
import pytest

from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine


class TestSympNetInitialization:
    """Tests for SympNet engine initialization."""

    def test_default_parameters(self):
        """Default parameters are physically reasonable."""
        engine = SympNetEngine()
        assert engine.mass == 1.0
        assert engine.spring_constant == 1.0
        assert engine.damping == 0.0

    def test_custom_parameters(self):
        """Custom parameters are accepted."""
        engine = SympNetEngine(mass=2.0, spring_constant=0.5, damping=0.1)
        assert engine.mass == 2.0
        assert engine.spring_constant == 0.5
        assert engine.damping == 0.1


class TestSympNetEnergyComputation:
    """Tests for Hamiltonian energy calculation."""

    def test_energy_formula(self, sympnet_config):
        """H = p²/(2m) + ½kq²"""
        engine = SympNetEngine(**sympnet_config)
        q, p = 2.0, 3.0
        energy = engine.compute_energy(q, p)
        expected = (p**2) / (2 * engine.mass) + 0.5 * engine.spring_constant * q**2
        assert np.isclose(energy, expected)

    def test_energy_at_rest(self, sympnet_config):
        """At rest (q=0, p=0), energy is zero."""
        engine = SympNetEngine(**sympnet_config)
        assert engine.compute_energy(0, 0) == 0.0

    def test_energy_positive_definite(self, sympnet_config):
        """Energy is always non-negative."""
        engine = SympNetEngine(**sympnet_config)
        for _ in range(100):
            q = np.random.uniform(-10, 10)
            p = np.random.uniform(-10, 10)
            assert engine.compute_energy(q, p) >= 0


class TestSympNetSymplecticIntegration:
    """Tests for symplectic (leapfrog) integration."""

    @pytest.mark.physics
    def test_single_step_reversibility(self, sympnet_config):
        """One forward + one backward step returns to start."""
        engine = SympNetEngine(**sympnet_config)
        q, p = 1.0, 1.0
        dt = 0.01

        # Forward
        q_fwd, p_fwd = engine.step(q, p, dt)
        # Backward (use same momentum, negative dt for true reversibility)
        q_back, p_back = engine.step(q_fwd, p_fwd, -dt)

        assert np.isclose(q_back, q, atol=1e-10)
        assert np.isclose(p_back, p, atol=1e-10)

    def test_energy_conservation_undamped(self, sympnet_config, physics_tolerance):
        """Undamped SHO conserves energy within tolerance over many steps."""
        engine = SympNetEngine(**sympnet_config)
        q, p = 1.0, 0.0
        dt = 0.01
        steps = 10000

        initial_energy = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p, dt)

        final_energy = engine.compute_energy(q, p)
        drift = abs(final_energy - initial_energy) / max(initial_energy, 1e-9)

        assert (
            drift < physics_tolerance
        ), f"Energy drift {drift:.6e} exceeds tolerance {physics_tolerance:.6e}"

    def test_predict_consistency_with_step(self, sympnet_config):
        """predict() should give same result as repeated step()."""
        engine = SympNetEngine(**sympnet_config)
        q, p = 1.5, -0.5
        steps = 100

        # Predict
        q_pred, p_pred = engine.predict(q, p, steps=steps)

        # Manual
        q_manual, p_manual = q, p
        for _ in range(steps):
            q_manual, p_manual = engine.step(q_manual, p_manual)

        assert np.isclose(q_pred, q_manual, atol=1e-10)
        assert np.isclose(p_pred, p_manual, atol=1e-10)

    def test_energy_monotonic_with_damping(self, sympnet_config):
        """With damping, energy strictly decreases (within floating-point tolerance)."""
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.1)
        q, p = 1.0, 0.0
        dt = 0.01
        steps = 1000

        energies = []
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
            energies.append(engine.compute_energy(q, p))

        # Allow tiny floating-point tolerance for monotonic decrease
        # (tiny increases of order 1e-10 are acceptable noise)
        assert all(
            energies[i] >= energies[i + 1] - 1e-9 for i in range(len(energies) - 1)
        )


class TestSympNetAdaptation:
    """Tests for self-adaptation (being rewritten by physics)."""

    def test_adapt_increases_damping_on_high_drift(self, sympnet_config):
        """High energy drift triggers damping increase."""
        engine = SympNetEngine(**sympnet_config)
        # Simulate high drift in history
        for _ in range(20):
            engine.history.append(
                {
                    "q": 1.0,
                    "p": 0.0,
                    "energy": 0.5,
                    "drift": 0.005,  # 0.5% drift (above 0.1% threshold)
                }
            )

        initial_damping = engine.damping
        engine.adapt()
        assert engine.damping > initial_damping

    def test_adapt_decreases_damping_on_low_drift(self, sympnet_config):
        """Low drift causes damping to decay."""
        engine = SympNetEngine(damping=0.1)
        # Simulate low drift (well below 0.00001 threshold)
        for _ in range(20):
            engine.history.append(
                {
                    "q": 1.0,
                    "p": 0.0,
                    "energy": 0.5,
                    "drift": 0.000001,  # 1e-6, clearly below threshold
                }
            )

        engine.adapt()
        assert engine.damping < 0.1

    def test_adapt_no_change_on_insufficient_history(self, sympnet_config):
        """Adapt does nothing with < 10 history entries."""
        engine = SympNetEngine()
        initial_damping = engine.damping
        for _ in range(5):
            engine.history.append({"drift": 0.01})
        engine.adapt()
        assert engine.damping == initial_damping


class TestSympNetHealth:
    """Tests for health reporting."""

    def test_health_status_healthy(self, sympnet_config):
        """Health returns 'healthy' when drift is low."""
        engine = SympNetEngine(**sympnet_config)
        # Run some steps to populate history
        q, p = 1.0, 0.0
        for _ in range(50):
            q, p = engine.step(q, p)

        health = engine.get_health()
        assert health["status"] == "healthy"
        assert health["avg_drift"] < 0.001

    def test_health_status_adapting(self, sympnet_config):
        """Health returns 'adapting' when drift is high."""
        engine = SympNetEngine(**sympnet_config)
        # Inject high drift history with required fields
        for _ in range(10):
            engine.history.append({"q": 0.0, "p": 0.0, "energy": 1.0, "drift": 0.01})

        health = engine.get_health()
        assert health["status"] == "adapting"

    def test_health_contains_required_fields(self, sympnet_config):
        """Health dict contains all expected keys."""
        engine = SympNetEngine(**sympnet_config)
        health = engine.get_health()
        required = {"status", "avg_drift", "damping", "total_energy"}
        assert required.issubset(health.keys())


class TestSympNetPhysicalAnchor:
    """The ultimate test: the physical anchor must hold."""

    @pytest.mark.physics
    def test_sacred_threshold_energy_drift(self, sympnet_config, physics_tolerance):
        """
        The sacred test: energy drift rate must be < 0.1%.
        This is the non-negotiable physical anchor.
        """
        engine = SympNetEngine(**sympnet_config)
        q, p = 1.0, 0.5  # Generic initial conditions
        dt = 0.01
        steps = 100000  # Long enough to accumulate error

        initial_energy = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p, dt)

        final_energy = engine.compute_energy(q, p)
        drift = abs(final_energy - initial_energy) / max(initial_energy, 1e-9)

        assert drift < physics_tolerance, (
            f"⚛️  PHYSICAL ANCHOR BROKEN! Energy drift {drift:.6%} "
            f"exceeds sacred threshold {physics_tolerance:.6%} (0.1%)."
        )

    @pytest.mark.physics
    @pytest.mark.parametrize(
        ("mass", "spring_k"),
        [
            (0.5, 2.0),
            (2.0, 0.5),
            (1.5, 1.5),
        ],
    )
    def test_anchor_holds_various_parameters(self, mass, spring_k, physics_tolerance):
        """Anchor holds across different physical parameters."""
        engine = SympNetEngine(mass=mass, spring_constant=spring_k)
        q, p = 1.0, 0.0
        steps = 50000

        initial = engine.compute_energy(q, p)
        for _ in range(steps):
            q, p = engine.step(q, p)

        final = engine.compute_energy(q, p)
        drift = abs(final - initial) / max(initial, 1e-9)
        assert drift < physics_tolerance


class TestSympNetCheckpointRollback:
    """Tests for Phase 5.0 checkpoint/rollback physical red line protection."""

    def test_checkpoint_saves_parameters(self):
        """Checkpoint captures current physical parameters."""
        engine = SympNetEngine(mass=2.0, spring_constant=1.5, damping=0.1)
        engine.save_checkpoint()
        assert engine._checkpoint_weights is not None
        assert engine._checkpoint_weights["mass"] == 2.0
        assert engine._checkpoint_weights["spring_constant"] == 1.5
        assert engine._checkpoint_weights["damping"] == 0.1

    def test_restore_checkpoint_returns_false_when_none(self):
        """Restore fails gracefully if no checkpoint exists."""
        engine = SympNetEngine()
        engine._checkpoint_weights = None
        result = engine.restore_checkpoint()
        assert result is False

    def test_restore_checkpoint_restores_parameters(self):
        """Restore successfully rolls back to saved parameters."""
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
        engine.mass = 2.5
        engine.spring_constant = 0.8
        engine.damping = 0.05
        engine.save_checkpoint()

        # Modify parameters away from checkpoint
        engine.mass = 3.0
        engine.spring_constant = 1.2
        engine.damping = 0.2

        # Restore
        success = engine.restore_checkpoint()
        assert success is True
        assert engine.mass == 2.5
        assert engine.spring_constant == 0.8
        assert engine.damping == 0.05

    def test_rollback_triggered_on_sustained_high_drift(self):
        """Rollback occurs after CRITICAL_DRIFT_STREAK consecutive high-drift steps."""
        engine = SympNetEngine()
        q, p = 1.0, 0.0
        # Disable sub-stepping to amplify drift per step
        engine._BASE_DT = 10.0  # Any dt < BASE_DT will use direct _apply_step
        large_dt = 1.0  # single large integration step

        # Checkpoint already saved at init with original parameters
        initial_mass = engine.mass

        # Corrupt parameters to induce high drift
        engine.mass = 0.1  # Very low mass → large velocities → high drift

        # Run exactly CRITICAL_DRIFT_STREAK steps; rollback occurs on the last
        for _ in range(engine.CRITICAL_DRIFT_STREAK):
            q, p = engine.step(q, p, dt=large_dt)

        # After CRITICAL_DRIFT_STREAK consecutive high-drift steps, rollback occurs
        assert engine.mass == initial_mass, (
            f"Expected rollback to restore mass to {initial_mass}, got {engine.mass}"
        )
        assert engine._high_drift_streak == 0

    def test_high_drift_streak_increments_and_decays(self):
        """Streak increments on high drift, decays on low drift."""
        engine = SympNetEngine()
        # Disable sub-stepping so a single large dt produces measurable drift
        engine._BASE_DT = 10.0
        q, p = 0.0, 1.0

        # One large step → high drift
        q, p = engine.step(q, p, dt=1.0)
        assert engine._high_drift_streak >= 1, (
            f"Expected high drift streak >= 1, got {engine._high_drift_streak}, "
            f"drift={engine.history[-1]['drift']}"
        )

        # Several tiny steps → low drift, streak should decay to 0
        for _ in range(5):
            q, p = engine.step(q, p, dt=0.001)
        assert engine._high_drift_streak == 0

    def test_checkpoint_saved_periodically_when_stable(self):
        """Checkpoint is saved every 100 steps when drift is stable."""
        engine = SympNetEngine()
        q, p = 0.1, 0.1

        # Run 150 steps with small dt (low drift)
        for i in range(150):
            q, p = engine.step(q, p, dt=0.01)
            if i > 0 and i % 100 == 0:
                # At step 100, checkpoint should be saved
                assert engine._checkpoint_weights is not None

        # At least one checkpoint should have been saved
        assert engine._checkpoint_weights is not None


class TestSurpriseAndCaution:
    """Tests for world model distillation — surprise detection (IMP-05)."""

    def test_compute_surprise_identical_states_returns_zero(self):
        """No surprise when predicted equals actual."""
        engine = SympNetEngine()
        state = {"q": 1.0, "p": 0.5}
        surprise = engine.compute_surprise(state, state)
        assert surprise == 0.0

    def test_compute_surprise_high_energy_drift_returns_one(self):
        """10% energy drift saturates surprise at 1.0."""
        engine = SympNetEngine()
        # predicted: q=1, p=0 → H = 0.5
        predicted = {"q": 1.0, "p": 0.0}
        # actual: q such that H = 1.05 (10% higher). For m=k=1, H=0.5*q^2 => q = sqrt(2.1) ≈ 1.449
        actual_q = (2.0 * 1.05) ** 0.5  # sqrt(2*H) = sqrt(2.1) ≈ 1.449
        actual = {"q": actual_q, "p": 0.0}
        surprise = engine.compute_surprise(predicted, actual)
        assert surprise == pytest.approx(1.0, abs=0.02)

    def test_compute_surprise_partial_drift_scales_linearly(self):
        """5% drift → surprise ≈ 0.5."""
        engine = SympNetEngine()
        predicted = {"q": 1.0, "p": 0.0}  # H = 0.5
        # 5% drift → actual energy = 0.525 → q = sqrt(1.05) ≈ 1.025
        actual_q = (2.0 * 0.525) ** 0.5
        actual = {"q": actual_q, "p": 0.0}
        surprise = engine.compute_surprise(predicted, actual)
        assert surprise == pytest.approx(0.5, abs=0.05)

    def test_adapt_caution_increases_damping_on_high_surprise(self):
        """High surprise (>0.3) increases damping."""
        engine = SympNetEngine(damping=0.1)
        initial_damping = engine.damping
        engine.adapt_caution(surprise=0.6, adaptation_rate=0.1)
        assert engine.damping > initial_damping
        # Expected: 0.1 + 0.6*0.1 = 0.16 (capped at 0.5)
        assert engine.damping == pytest.approx(0.16, abs=0.01)

    def test_adapt_caution_decreases_damping_on_low_surprise(self):
        """Very low surprise slowly decays damping."""
        engine = SympNetEngine(damping=0.2)
        engine.adapt_caution(surprise=0.01, adaptation_rate=0.1)
        assert engine.damping < 0.2
        assert engine.damping == pytest.approx(0.2 * 0.99, abs=1e-3)

    def test_adapt_caution_respects_max_cap(self):
        """Damping never exceeds 0.5."""
        engine = SympNetEngine(damping=0.45)
        engine.adapt_caution(surprise=1.0, adaptation_rate=0.2)
        assert engine.damping <= 0.5

    def test_adapt_caution_respects_min_floor(self):
        """Damping never goes below 0.01."""
        engine = SympNetEngine(damping=0.01)
        engine.adapt_caution(surprise=0.0, adaptation_rate=0.1)
        assert engine.damping >= 0.01

