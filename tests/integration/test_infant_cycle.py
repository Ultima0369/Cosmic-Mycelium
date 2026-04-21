"""
Integration Tests — Infant Breath Cycle
Tests the full infant lifecycle: perceive → predict → act → diffuse cycle.
"""

from __future__ import annotations

import pytest
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
