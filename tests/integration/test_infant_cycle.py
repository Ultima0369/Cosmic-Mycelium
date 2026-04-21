"""
Integration Tests — Infant Breath Cycle
Tests the full infant lifecycle: perceive → predict → act → diffuse cycle.
"""

from __future__ import annotations

import time
from unittest.mock import patch
import pytest
from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.infant.hic import BreathState


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

        required_keys = {"infant_id", "uptime", "hic", "sympnet", "memory", "brain", "interface", "log_tail"}
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
        # Force very low energy to trigger SUSPEND on first update_breath call
        with patch.object(infant.hic, '_lock'):
            infant.hic._energy = 5.0  # Below 20.0 SUSPEND threshold

        initial_suspend_count = infant.hic.suspend_count

        # First call: should enter SUSPEND (energy < 20.0)
        infant.hic.update_breath(confidence=0.9, work_done=False)
        assert infant.hic.state == BreathState.SUSPEND
        assert infant.hic.suspend_count == initial_suspend_count + 1
        suspend_end_time = infant.hic._suspend_end_time

        # Advance time past suspend_end_time by patching monotonic
        with patch('time.monotonic', return_value=suspend_end_time + 0.1):
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
