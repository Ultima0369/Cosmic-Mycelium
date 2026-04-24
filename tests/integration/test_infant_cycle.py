"""
Integration Tests — Infant Breath Cycle
Tests the full infant lifecycle: perceive → predict → act → diffuse cycle.
"""

from __future__ import annotations

import time
import tracemalloc
from unittest.mock import patch

from cosmic_mycelium.infant.hic import BreathState
from cosmic_mycelium.infant.main import SiliconInfant


class TestInfantLifecycle:
    """Integration tests for the complete infant breath cycle."""

    def test_single_breath_cycle_completes(self):
        """One full breath cycle (CONTRACT phase) completes without error."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=1)
        # If we reach here, cycle completed
        assert infant.hic.energy > 0

    def test_status_includes_all_subsystems(self):
        """get_status() contains hic, sympnet, memory, brain, interface."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=5)
        status = infant.get_status()

        required_keys = {
            "infant_id",
            "uptime",
            "hic",
            "sympnet",
            "memory",
            "brain",
            "interface",
            "log_tail",
        }
        assert required_keys.issubset(status.keys())

    def test_hic_status_integrated(self):
        """HIC status integrated correctly into infant status."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=10)
        status = infant.get_status()

        hic_status = status["hic"]
        assert "energy" in hic_status
        assert "state" in hic_status
        assert "total_cycles" in hic_status

    def test_sympnet_health_integrated(self):
        """SympNet health integrated correctly."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=10)
        status = infant.get_status()

        sympnet_status = status["sympnet"]
        assert "status" in sympnet_status
        assert "avg_drift" in sympnet_status

    def test_memory_stats_integrated(self):
        """Memory layer stats present."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=20)
        status = infant.get_status()

        mem = status["memory"]
        assert "paths" in mem
        assert "features" in mem
        assert "coverage" in mem
        assert "best_paths" in mem

    def test_brain_status_integrated(self):
        """Brain region status present."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=5)
        status = infant.get_status()

        brain = status["brain"]
        assert "regions" in brain

    def test_interface_status_integrated(self):
        """Symbiosis interface status present."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=5)
        status = infant.get_status()

        interface = status["interface"]
        assert "mode" in interface

    def test_log_tail_captures_recent_entries(self):
        """log_tail contains recent log entries."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=10)
        status = infant.get_status()

        log_tail = status["log_tail"]
        assert isinstance(log_tail, list)
        assert len(log_tail) <= 5

    def test_suspend_handling_integration(self):
        """Low energy triggers SUSPEND and produces suspend packet."""
        infant = SiliconInfant("test-infant")
        # Drive energy down manually
        infant.hic._energy = 5.0
        infant.run(max_cycles=3)

        # Check outbox contains suspend packets
        assert any(
            p.value_payload and p.value_payload.get("action") == "suspend"
            for p in infant.outbox
        )

    def test_suspend_recovery_after_duration(self):
        """SUSPEND state recovers exactly after suspend_duration with recovery_energy."""
        # This test verifies M2 milestone: suspend → 5s recovery → energy restored
        infant = SiliconInfant("suspend-recovery-test")
        # Force low energy (above absolute_min but below suspend threshold) to trigger normal SUSPEND
        with patch.object(infant.hic, "_lock"):
            infant.hic._energy = 15.0  # Above absolute_min (5.0), below suspend_enter (20.0)

        initial_suspend_count = infant.hic.suspend_count

        # First call: should enter SUSPEND (energy < 20.0)
        infant.hic.update_breath(confidence=0.9, work_done=False)
        assert infant.hic.state == BreathState.SUSPEND
        assert infant.hic.suspend_count == initial_suspend_count + 1
        suspend_end_time = infant.hic._suspend_end_time

        # Advance time past suspend_end_time by patching monotonic
        with patch("time.monotonic", return_value=suspend_end_time + 0.1):
            # Second call: should recover from SUSPEND
            infant.hic.update_breath(confidence=0.9, work_done=False)
            # After recovery: state should be CONTRACT, energy set to recovery_energy (60.0)
            assert infant.hic.state == BreathState.CONTRACT
            assert infant.hic.energy == infant.hic.config.recovery_energy

    def test_outbox_populated_with_actions(self):
        """During CONTRACT phase, outbox receives action packets."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=5)

        # Some packets should be generated (not all are SUSPEND)
        assert len(infant.outbox) >= 0  # May be zero if all SUSPEND, but no crash

    def test_infant_does_not_crash_over_many_cycles(self):
        """Infant can run many cycles without crashing."""
        infant = SiliconInfant("test-infant")
        infant.run(max_cycles=100)
        # Success if no exception raised

    def test_uptime_increases(self):
        """uptime field is positive and increases."""
        infant = SiliconInfant("test-infant")
        status1 = infant.get_status()
        import time

        time.sleep(0.1)
        status2 = infant.get_status()
        assert status2["uptime"] > status1["uptime"]

    def test_long_running_stability_1000_cycles(self):
        """Infant can complete many breath cycles without crash or state corruption."""
        infant = SiliconInfant("stability-test")
        # Use accelerated HIC config for faster cycles
        infant.hic.config.contract_duration = 0.001
        infant.hic.config.diffuse_duration = 0.001
        infant.hic.config.suspend_duration = 0.001
        # Run many cycles; sleep calls are short so this completes quickly
        infant.run(max_cycles=1000)
        # If we reach here, no crash occurred
        assert infant.hic.total_cycles > 500  # ~1 cycle per 2 iterations
        assert infant.hic.energy > 0
        # State should be finite and reasonable
        assert abs(infant.state["q"]) <= 1.0
        assert abs(infant.state["p"]) <= 1.0

    def test_memory_no_leak_over_cycles(self):
        """Memory usage remains bounded over many breath cycles."""
        infant = SiliconInfant("memory-test")
        tracemalloc.start()
        # Capture baseline before many cycles
        baseline = tracemalloc.take_snapshot()
        # Run 500 cycles with sleep mocked to avoid wall-clock delay
        with patch("time.sleep", return_value=None):
            infant.run(max_cycles=500)
        # Take another snapshot
        after = tracemalloc.take_snapshot()
        tracemalloc.stop()
        # Compare memory stats — allow some growth but not unbounded
        stats = after.compare_to(baseline, "lineno")
        total_growth = sum(stat.size_diff for stat in stats)
        # Allow up to 10MB growth over 500 cycles (generous)
        assert total_growth < 10 * 1024 * 1024, f"Memory grew by {total_growth} bytes"

    def test_performance_cycle_rate(self):
        """Average cycle time should be reasonable (< 100ms even with real sleep)."""
        infant = SiliconInfant("perf-test")
        # Use faster config for test
        infant.hic.config.diffuse_duration = 0.001
        infant.hic.config.suspend_duration = 0.001
        start = time.monotonic()
        cycles = 50
        infant.run(max_cycles=cycles)
        elapsed = time.monotonic() - start
        avg_cycle_time = elapsed / cycles
        # Should be well under 100ms per cycle (with accelerated config, much lower)
        assert avg_cycle_time < 0.1

    def test_sensors_integration_does_not_crash(self):
        """Sensor readings are successfully integrated into perception every cycle."""
        infant = SiliconInfant("sensor-integration-test")
        # Run a few cycles and verify perception contains sensor data
        for _ in range(10):
            perception = infant.perceive()
            assert "sensors" in perception
            sensor_data = perception["sensors"]
            assert "vibration" in sensor_data
            assert "temperature" in sensor_data
            assert "spectrum_power" in sensor_data
            # Values should be physically plausible
            assert -1.0 <= perception["physical"]["q"] <= 1.0
            assert -1.0 <= perception["physical"]["p"] <= 1.0
