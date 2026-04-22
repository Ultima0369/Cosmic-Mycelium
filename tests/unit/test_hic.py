"""
HIC (Homeostasis & Invariant Core) — Comprehensive Test Suite
Tests the "人格底线" — energy management, breath cycles, and suspend logic.
Covers: P1-P10 (initialization, breath cycle, suspend, value vector, thread safety, edge cases)
"""

from __future__ import annotations

import time
import threading
import pytest
from cosmic_mycelium.infant.hic import HIC, HICConfig, BreathState


# =============================================================================
# P1: Initialization & Construction
# =============================================================================

class TestHICInitialization:
    """Tests for HIC construction and initial state."""

    def test_default_config_creates_valid_state(self):
        """Default HIC starts at full energy, CONTRACT state."""
        h = HIC()
        assert h.energy == 100.0
        assert h.state == BreathState.CONTRACT
        assert h.is_suspended is False
        assert h.total_cycles == 0

    def test_custom_config_applied(self):
        """Custom HICConfig overrides defaults."""
        config = HICConfig(
            energy_max=150.0,
            contract_duration=0.1,
            diffuse_duration=0.01,
            suspend_duration=10.0,
            recovery_energy=80.0,
            recovery_rate=1.0,
        )
        h = HIC(config=config, name="custom-hic")
        assert h.energy == 150.0
        assert h.config.contract_duration == 0.1
        assert h.config.recovery_energy == 80.0

    def test_energy_starts_at_max(self):
        """Energy always initializes to energy_max."""
        for energy_max in [50.0, 100.0, 200.0]:
            h = HIC(config=HICConfig(energy_max=energy_max))
            assert h.energy == energy_max

    def test_value_vector_has_required_keys(self):
        """Initial value vector contains all four core values."""
        h = HIC()
        vv = h.value_vector_snapshot
        assert "self_preservation" in vv
        assert "mutual_benefit" in vv
        assert "curiosity" in vv
        assert "caution" in vv


# =============================================================================
# P2: Breath Cycle & State Transitions
# =============================================================================

class TestBreathCycle:
    """Tests for CONTRACT ↔ DIFFUSE ↔ SUSPEND transitions."""

    def test_contract_to_diffuse_after_duration(self, mock_time):
        """CONTRACT transitions to DIFFUSE after contract_duration elapses."""
        config = HICConfig(
            contract_duration=0.001,
            diffuse_duration=0.001,
            suspend_duration=0.1,
        )
        h = HIC(config=config)
        assert h.state == BreathState.CONTRACT

        mock_time.advance(0.002)  # Past contract duration
        h.update_breath(confidence=0.7, work_done=False)

        assert h.state == BreathState.DIFFUSE

    def test_diffuse_to_contract_after_duration(self, mock_time):
        """DIFFUSE transitions back to CONTRACT after diffuse_duration."""
        config = HICConfig(
            contract_duration=0.001,
            diffuse_duration=0.001,
            suspend_duration=0.1,
        )
        h = HIC(config=config)
        h._state = BreathState.DIFFUSE
        # Set elapsed time to just enough for one D->C transition but not a second C->D:
        # Need diffuse_duration <= elapsed < diffuse_duration + contract_duration
        h._last_switch = mock_time.now() - 0.0015

        h.update_breath(confidence=0.7, work_done=False)

        assert h.state == BreathState.CONTRACT

    def test_energy_consumed_during_contract(self, mock_time):
        """Energy decreases by 0.1 per CONTRACT→DIFFUSE transition."""
        config = HICConfig(contract_duration=0.001)
        h = HIC(config=config)
        start_energy = h.energy

        mock_time.advance(0.002)
        h.update_breath(confidence=0.7, work_done=False)

        assert h.energy == start_energy - 0.1

    def test_energy_recovers_during_diffuse(self, mock_time):
        """Energy increases by recovery_rate per DIFFUSE→CONTRACT transition."""
        config = HICConfig(
            contract_duration=0.001,
            diffuse_duration=0.001,
            recovery_rate=0.5,
        )
        h = HIC(config=config)
        h._state = BreathState.DIFFUSE
        # Elapsed time: enough for one D->C but not a subsequent C->D
        h._last_switch = mock_time.now() - 0.0015
        h._energy = 50.0
        start_energy = h.energy

        h.update_breath(confidence=0.7, work_done=False)

        assert h.energy == start_energy + 0.5

    def test_energy_capped_at_max(self, mock_time):
        """Recovery never exceeds energy_max."""
        config = HICConfig(
            contract_duration=0.001,
            diffuse_duration=0.001,
            recovery_rate=5.0,  # Large recovery
        )
        h = HIC(config=config)
        h._state = BreathState.DIFFUSE
        h._last_switch = mock_time.now() - 0.003
        h._energy = 99.0

        h.update_breath(confidence=0.7, work_done=False)

        assert h.energy <= 100.0


# =============================================================================
# P3: SUSPEND Logic & Recovery
# =============================================================================

class TestSuspendLogic:
    """Tests for SUSPEND entry, hold, and recovery."""

    def test_suspend_on_low_energy(self):
        """Energy < 20 triggers SUSPEND."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 19.5

        h.update_breath(confidence=0.7, work_done=False)

        assert h.state == BreathState.SUSPEND
        assert h.is_suspended is True

    def test_suspend_on_low_confidence(self):
        """Confidence < 0.3 triggers SUSPEND."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)

        h.update_breath(confidence=0.25, work_done=False)

        assert h.state == BreathState.SUSPEND

    def test_suspend_count_increments_on_entry(self):
        """Each SUSPEND entry increments counter."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 19.0
        h.update_breath(confidence=0.7, work_done=False)
        first_count = h.suspend_count

        # Recover
        h._energy = 100.0
        h._state = BreathState.CONTRACT
        h._last_switch = time.monotonic() - 6.0
        h.update_breath(confidence=0.7, work_done=False)

        # Trigger again
        h._energy = 15.0
        h.update_breath(confidence=0.7, work_done=False)
        second_count = h.suspend_count

        assert second_count == first_count + 1

    def test_suspend_idempotent_while_already_suspended(self):
        """Calling update_breath while SUSPENDED does not increment count."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 10.0
        h.update_breath(confidence=0.7, work_done=False)
        first_count = h.suspend_count

        # Call again while still suspended
        h.update_breath(confidence=0.7, work_done=False)

        assert h.suspend_count == first_count

    def test_suspend_remaining_decreases(self, mock_time):
        """suspend_remaining counts down to zero."""
        config = HICConfig(suspend_duration=5.0)
        h = HIC(config=config)
        h._energy = 10.0
        h.update_breath(confidence=0.7, work_done=False)

        assert h.is_suspended
        remaining_initial = h.suspend_remaining
        assert remaining_initial > 0

        mock_time.advance(2.5)
        remaining_later = h.suspend_remaining
        assert remaining_later < remaining_initial
        assert remaining_later > 0

    def test_suspend_remaining_zero_when_not_suspended(self):
        """suspend_remaining is 0 when not in SUSPEND."""
        config = HICConfig(suspend_duration=5.0)
        h = HIC(config=config)
        assert h.suspend_remaining == 0.0

    def test_energy_stable_during_suspend(self, mock_time):
        """Energy stays flat during SUSPEND (no recovery ticks)."""
        config = HICConfig(suspend_duration=5.0)
        h = HIC(config=config)
        h._energy = 10.0
        h.update_breath(confidence=0.7, work_done=False)
        suspended_energy = h.energy

        mock_time.advance(3.0)
        h.update_breath(confidence=0.7, work_done=False)

        assert h.energy == suspended_energy

    def test_recovery_after_suspend_duration(self, mock_time):
        """After suspend_duration, HIC returns to CONTRACT with energy boost."""
        config = HICConfig(
            suspend_duration=0.1,
            recovery_energy=60.0,
        )
        h = HIC(config=config)
        h._energy = 5.0
        h.update_breath(confidence=0.7, work_done=False)
        assert h.state == BreathState.SUSPEND

        mock_time.advance(0.2)
        h.update_breath(confidence=0.7, work_done=False)

        assert h.state == BreathState.CONTRACT
        assert h.energy == 60.0

    def test_suspend_entry_reason_low_energy(self):
        """get_suspend_packet reason reflects energy when energy < 20."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 18.0
        packet = h.get_suspend_packet("node-1")
        assert packet.value_payload["reason"] == "low_energy"

    def test_suspend_entry_reason_low_confidence(self):
        """get_suspend_packet reason is low_confidence when energy >= 20."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 50.0
        packet = h.get_suspend_packet("node-1")
        assert packet.value_payload["reason"] == "low_confidence"


# =============================================================================
# P4: Value Vector Adaptation
# =============================================================================

class TestValueVectorAdaptation:
    """Tests for value vector mutations."""

    def test_adapt_value_vector_increments_correct_keys(self):
        """Positive delta increases value."""
        h = HIC()
        initial_caution = h.value_vector["caution"]
        h.adapt_value_vector({"caution": 0.2})
        assert h.value_vector["caution"] == pytest.approx(initial_caution + 0.2)

    def test_adapt_value_vector_decrements(self):
        """Negative delta decreases value."""
        h = HIC()
        initial_caution = h.value_vector["caution"]
        h.adapt_value_vector({"caution": -0.1})
        assert h.value_vector["caution"] == pytest.approx(initial_caution - 0.1)

    def test_value_vector_clamps_at_max(self):
        """Values cannot exceed 2.0 upper bound."""
        h = HIC()
        h.value_vector["self_preservation"] = 1.9
        h.adapt_value_vector({"self_preservation": 0.5})
        assert h.value_vector["self_preservation"] == 2.0

    def test_value_vector_clamps_at_min(self):
        """Values cannot go below 0.1 lower bound."""
        h = HIC()
        h.value_vector["caution"] = 0.15
        h.adapt_value_vector({"caution": -0.2})
        assert h.value_vector["caution"] == 0.1

    def test_adaptation_count_increments(self):
        """adapt_value_vector increments adaptation_count."""
        h = HIC()
        initial = h.get_status()["adaptation_count"]
        h.adapt_value_vector({"curiosity": 0.1})
        assert h.get_status()["adaptation_count"] == initial + 1

    def test_multiple_keys_adapted_at_once(self):
        """Feedback dict with multiple keys updates all relevant values."""
        h = HIC()
        initial_caution = h.value_vector["caution"]
        initial_curiosity = h.value_vector["curiosity"]
        h.adapt_value_vector({"caution": 0.1, "curiosity": -0.2})
        # Verify both keys changed in expected directions
        assert h.value_vector["caution"] > initial_caution
        assert h.value_vector["curiosity"] < initial_curiosity

    def test_unknown_key_ignored(self):
        """adapt_value_vector ignores keys not in value_vector."""
        h = HIC()
        initial = h.value_vector.copy()
        h.adapt_value_vector({"unknown_key": 999.0})
        assert h.value_vector == initial


# =============================================================================
# P5: SUSPEND Packet Generation
# =============================================================================

class TestSuspendPacket:
    """Tests for get_suspend_packet()."""

    def test_packet_contains_suspend_action(self):
        """Packet value_payload has action='suspend'."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 15.0
        packet = h.get_suspend_packet("node-1")

        assert packet.value_payload["action"] == "suspend"

    def test_packet_includes_current_energy(self):
        """Packet contains current energy snapshot."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 33.3
        packet = h.get_suspend_packet("node-1")
        assert packet.value_payload["energy"] == 33.3

    def test_packet_includes_value_vector_copy(self):
        """Packet includes a copy of current value vector."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        packet = h.get_suspend_packet("node-1")

        vv = packet.value_payload["value_vector"]
        assert "self_preservation" in vv
        assert vv["caution"] == h.value_vector["caution"]
        # Ensure it's a copy, not a reference
        original_caution = h.value_vector["caution"]
        vv["caution"] = 999.0
        assert h.value_vector["caution"] == original_caution

    def test_packet_source_id_matches_caller(self):
        """packet.source_id equals the source_id argument."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        packet = h.get_suspend_packet("my-node")
        assert packet.source_id == "my-node"


# =============================================================================
# P6: Status Reporting
# =============================================================================

class TestStatusReporting:
    """Tests for get_status() consistency."""

    def test_status_contains_all_required_fields(self):
        """get_status returns all required keys."""
        h = HIC()
        status = h.get_status()
        required = {
            "energy", "energy_max", "state", "total_cycles",
            "suspend_count", "adaptation_count", "value_vector",
            "contract_duration", "diffuse_duration", "suspend_duration",
        }
        assert required.issubset(status.keys())

    def test_status_values_match_properties(self):
        """get_status values equal property getters."""
        h = HIC()
        status = h.get_status()
        assert status["energy"] == h.energy
        assert status["state"] == h.state.value
        assert status["energy_max"] == h.config.energy_max

    def test_status_value_vector_is_copy(self):
        """status['value_vector'] is a copy, mutations don't affect HIC."""
        h = HIC()
        status = h.get_status()
        status["value_vector"]["caution"] = 999.0
        assert h.value_vector["caution"] != 999.0


# =============================================================================
# P7: Thread Safety & Concurrency
# =============================================================================

class TestThreadSafety:
    """Tests for RLock-protected state mutations."""

    def test_concurrent_update_breath_no_crash(self):
        """Concurrent update_breath calls never crash."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        errors = []

        def worker():
            try:
                for _ in range(100):
                    h.update_breath(confidence=0.5, work_done=False)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent errors: {errors}"

    def test_concurrent_update_preserves_invariants(self):
        """After concurrent updates, invariants still hold."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)

        def worker():
            for _ in range(50):
                h.update_breath(confidence=0.5, work_done=False)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert 0 <= h.energy <= h.config.energy_max
        assert h.state in BreathState

    def test_concurrent_adapt_value_vector(self):
        """Concurrent value_vector adaptations are serialized without corruption."""
        h = HIC()
        errors = []

        def worker(delta: float):
            try:
                for _ in range(50):
                    h.adapt_value_vector({"caution": delta})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(0.01,)),
            threading.Thread(target=worker, args=(-0.01,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert 0.1 <= h.value_vector["caution"] <= 2.0

    def test_concurrent_suspend_triggers_serialized(self):
        """Multiple concurrent low-energy triggers don't double-count suspend."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 10.0

        results = []

        def worker():
            for _ in range(10):
                state = h.update_breath(confidence=0.1, work_done=False)
                results.append(state)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All returned states should be SUSPEND
        assert all(s == BreathState.SUSPEND for s in results)
        # Suspend count should be 1 (transition only once)
        assert h.suspend_count == 1

    def test_concurrent_status_snapshots(self):
        """get_status under concurrent load never crashes and returns valid dict."""
        h = HIC()
        errors = []
        statuses = []

        def worker():
            try:
                for _ in range(50):
                    statuses.append(h.get_status())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        for s in statuses:
            assert 0 <= s["energy"] <= 100.0


# =============================================================================
# P8: Edge Cases & Invariants
# =============================================================================

class TestEdgeCases:
    """Edge-case and invariant tests."""

    def test_suspend_idempotent(self):
        """Entering SUSPEND multiple times counts only once."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 10.0

        h.update_breath(confidence=0.7, work_done=False)
        first_count = h.suspend_count
        h.update_breath(confidence=0.7, work_done=False)

        assert h.suspend_count == first_count

    def test_confidence_zero_triggers_suspend(self):
        """Confidence = 0.0 triggers SUSPEND."""
        h = HIC()
        h.update_breath(confidence=0.0, work_done=False)
        assert h.state == BreathState.SUSPEND

    def test_energy_exactly_20_does_not_suspend(self):
        """Energy exactly 20.0 does NOT trigger SUSPEND (needs < 20)."""
        h = HIC()
        h._energy = 20.0
        h.update_breath(confidence=0.7, work_done=False)
        assert h.state != BreathState.SUSPEND

    def test_confidence_exactly_0_3_does_not_suspend(self):
        """Confidence exactly 0.3 does NOT trigger SUSPEND (needs < 0.3)."""
        h = HIC()
        h.update_breath(confidence=0.3, work_done=False)
        assert h.state != BreathState.SUSPEND

    def test_rapid_energy_drop_triggers_suspend_once(self):
        """Energy dropping 21→19 triggers SUSPEND exactly once."""
        h = HIC()
        h._energy = 21.0
        h.update_breath(confidence=0.7, work_done=False)
        assert h.state == BreathState.CONTRACT

        h._energy = 19.0
        h.update_breath(confidence=0.7, work_done=False)
        assert h.state == BreathState.SUSPEND
        assert h.suspend_count == 1

    def test_energy_non_negative_after_many_cycles(self, mock_time):
        """Energy never goes negative even after many CONTRACT cycles."""
        config = HICConfig(contract_duration=0.001, recovery_rate=0.0)
        h = HIC(config=config)
        h._energy = 1.0

        for _ in range(200):
            mock_time.advance(0.002)
            h.update_breath(confidence=0.7, work_done=False)

        assert h.energy >= 0.0

    def test_suspend_remaining_never_negative(self, mock_time):
        """suspend_remaining clamps to >=0 even with time-travel."""
        config = HICConfig(suspend_duration=5.0)
        h = HIC(config=config)
        h._energy = 10.0
        h.update_breath(confidence=0.7, work_done=False)

        # Simulate backward time jump (shouldn't happen with monotonic)
        mock_time.advance(-1000)
        assert h.suspend_remaining >= 0.0


# =============================================================================
# P9: Metrics & Observability
# =============================================================================

class TestMetrics:
    """Tests for counter and metric accuracy."""

    def test_total_cycles_increments_on_contract_to_diffuse(self, mock_time):
        """total_cycles increments each CONTRACT→DIFFUSE transition."""
        config = HICConfig(contract_duration=0.001)
        h = HIC(config=config)
        assert h.total_cycles == 0

        mock_time.advance(0.002)
        h.update_breath(confidence=0.7, work_done=False)

        assert h.total_cycles == 1

    def test_suspend_count_only_on_transition(self):
        """suspend_count increments only on CONTRACT→SUSPEND transition."""
        config = HICConfig(suspend_duration=0.1)
        h = HIC(config=config)
        h._energy = 10.0
        h.update_breath(confidence=0.7, work_done=False)
        first = h.suspend_count

        h.update_breath(confidence=0.7, work_done=False)
        assert h.suspend_count == first  # No increment

        h._energy = 100.0
        h._state = BreathState.CONTRACT
        h._last_switch = time.monotonic() - 6.0
        h.update_breath(confidence=0.7, work_done=False)

        h._energy = 5.0
        h.update_breath(confidence=0.7, work_done=False)

        assert h.suspend_count == first + 1

    def test_adaptation_count_tracks_all_feedback(self):
        """adaptation_count increments on every adapt_value_vector call."""
        h = HIC()
        assert h.adaptation_count == 0
        h.adapt_value_vector({"caution": 0.1})
        assert h.adaptation_count == 1
        h.adapt_value_vector({"curiosity": 0.1})
        assert h.adaptation_count == 2


# =============================================================================
# P10: Property Accessors
# =============================================================================

class TestProperties:
    """Tests for read-only properties."""

    def test_energy_property_snapshot(self):
        """energy property returns current energy."""
        h = HIC()
        assert h.energy == 100.0
        h._energy = 42.0
        assert h.energy == 42.0

    def test_state_property_snapshot(self):
        """state property returns current BreathState."""
        h = HIC()
        assert h.state == BreathState.CONTRACT
        h._state = BreathState.SUSPEND
        assert h.state == BreathState.SUSPEND

    def test_is_suspended_property(self):
        """is_suspended is True only when state is SUSPEND."""
        h = HIC()
        assert not h.is_suspended
        h._state = BreathState.SUSPEND
        assert h.is_suspended

    def test_value_vector_snapshot_is_copy(self):
        """value_vector_snapshot returns a copy, mutations don't affect HIC."""
        h = HIC()
        snapshot = h.value_vector_snapshot
        snapshot["caution"] = 999.0
        assert h.value_vector["caution"] != 999.0
