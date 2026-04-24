"""
HIC Breath Rhythm Stability Test — Phase 1.1
Validates: 55ms contract precision, zero-energy protection, suspend recovery.
"""

from __future__ import annotations

from cosmic_mycelium.infant.hic import HIC, BreathState, HICConfig


class TestBreathRhythmStability:
    """Breath cycle timing must be precise."""

    def test_contract_duration_increment(self):
        """
        A single CONTRACT→DIFFUSE transition must advance _last_switch
        by exactly contract_duration (55ms ± 1e-6 tolerance).
        """
        config = HICConfig(
            energy_max=100.0,
            contract_duration=0.055,
            diffuse_duration=0.005,
            suspend_duration=5.0,
            recovery_energy=60.0,
            recovery_rate=0.5,
        )
        hic = HIC(config=config, name="test-hic")
        hic._last_switch = 0.0
        hic._state = BreathState.CONTRACT

        # Time just large enough to trigger ONE CONTRACT→DIFFUSE transition
        # but not enough to also trigger DIFFUSE→CONTRACT:
        # Need: now ≥ contract_duration  (to fire first transition)
        #  AND: now - contract_duration < diffuse_duration  (to prevent second)
        # => 0.055 ≤ now < 0.060
        now = 0.056
        prev_switch = hic._last_switch

        hic._tick(now, max_transitions=1)

        assert hic.state == BreathState.DIFFUSE
        delta = hic._last_switch - prev_switch
        assert (
            abs(delta - config.contract_duration) < 1e-6
        ), f"Contract duration delta {delta:.9f} != {config.contract_duration}"

    def test_diffuse_duration_increment(self):
        """
        A single DIFFUSE→CONTRACT transition must advance _last_switch
        by exactly diffuse_duration (5ms ± 1e-6 tolerance).
        """
        config = HICConfig(
            energy_max=100.0,
            contract_duration=0.055,
            diffuse_duration=0.005,
            suspend_duration=5.0,
            recovery_energy=60.0,
            recovery_rate=0.5,
        )
        hic = HIC(config=config, name="test-hic")
        hic._last_switch = 0.0
        hic._state = BreathState.DIFFUSE

        # Time just large enough to trigger ONE DIFFUSE→CONTRACT transition
        # (0.005 < now < 0.055 to avoid triggering reverse transition)
        now = 0.006
        prev_switch = hic._last_switch

        hic._tick(now, max_transitions=1)

        assert hic.state == BreathState.CONTRACT
        delta = hic._last_switch - prev_switch
        assert abs(delta - config.diffuse_duration) < 1e-6

    def test_energy_never_negative(self):
        """HIC energy must never drop below zero (zero-bug protection)."""
        config = HICConfig(
            energy_max=1000.0,
            contract_duration=0.001,
            diffuse_duration=0.001,
            suspend_duration=1.0,
            recovery_energy=60.0,
            recovery_rate=0.5,
        )
        hic = HIC(config=config, name="zero-test")
        hic._last_switch = 0.0

        fake_time = 0.0
        step = 0.001  # Small step to advance time gradually
        for _ in range(10_000):
            fake_time += step
            # Step exactly one transition per tick to avoid multi-cycle accumulation
            hic._tick(fake_time, max_transitions=1)

        assert hic._energy >= 0.0, "Energy dropped below zero"

    def test_suspend_recovery_energy_jump(self):
        """After SUSPEND, energy should recover to recovery_energy."""
        config = HICConfig(
            energy_max=100.0,
            contract_duration=0.001,
            diffuse_duration=0.001,
            suspend_duration=0.1,
            recovery_energy=60.0,
            recovery_rate=0.5,
        )
        hic = HIC(config=config, name="suspend-test")
        hic._last_switch = 0.0
        hic._energy = 15.0  # Below suspend threshold

        # Step 1: Enter SUSPEND via CONTRACT→DIFFUSE transition (energy check fires)
        hic._tick(
            now=0.002, max_transitions=1
        )  # > contract_duration triggers transition
        assert hic.state == BreathState.SUSPEND, f"Expected SUSPEND, got {hic.state}"

        # Step 2: Recovery — advance past suspend_end_time
        recover_time = 0.2  # Well past suspend_end_time (0.0 + 0.1)
        hic._tick(now=recover_time, max_transitions=1)
        assert hic.state == BreathState.CONTRACT
        assert hic._energy == config.recovery_energy

    def test_full_cycle_alternation(self):
        """CONTRACT → DIFFUSE → CONTRACT sequence completes correctly."""
        config = HICConfig(
            energy_max=100.0,
            contract_duration=0.055,
            diffuse_duration=0.005,
            suspend_duration=5.0,
            recovery_energy=60.0,
            recovery_rate=0.5,
        )
        hic = HIC(config=config, name="cycle-test")
        hic._last_switch = 0.0
        hic._state = BreathState.CONTRACT
        energy_start = hic._energy

        # Step 1: CONTRACT → DIFFUSE (one transition)
        hic._tick(now=0.056, max_transitions=1)
        assert hic.state == BreathState.DIFFUSE
        assert hic._energy == energy_start - 0.1

        # Step 2: DIFFUSE → CONTRACT
        # now must be ≥ last_switch + diffuse_duration but < next contract threshold
        hic._tick(now=0.061, max_transitions=1)
        assert hic.state == BreathState.CONTRACT
        # Energy should have increased by recovery_rate (capped at max)
        expected = min(config.energy_max, energy_start - 0.1 + config.recovery_rate)
        assert hic._energy == expected
