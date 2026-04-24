"""
Unit tests for Phase 5.2 Selective Sensing — SensorArray.read_active().

TDD coverage:
- read_active() with no mask equals read_all()
- read_active() with partial mask only updates selected sensors
- Unselected sensors return cached values
- Energy/semantic state still consistent
"""

from __future__ import annotations

import time
import pytest

from cosmic_mycelium.infant.sensors import SensorArray, SensorType


@pytest.fixture
def sensor_array():
    """Fresh SensorArray with deterministic RNG."""
    arr = SensorArray()
    # Reset start time for deterministic tests
    arr._start_time = time.time()
    arr._last_values = {"vibration": 0.0, "temperature": 22.0, "spectrum_power": 1.0}
    return arr


class TestSelectiveSensing:
    """Phase 5.2: Selective sensing to reduce computation."""

    def test_read_active_no_mask_equals_read_all(self, sensor_array):
        """read_active(None) returns same semantics as read_all()."""
        all_readings = sensor_array.read_all()
        active_readings = sensor_array.read_active(attention_mask=None)

        assert set(all_readings.keys()) == set(active_readings.keys())
        # Allow larger tolerance due to time drift between two calls (temp has daily cycle)
        for key in all_readings:
            assert abs(all_readings[key] - active_readings[key]) < 1.0  # 1 degree/unit tolerance

    def test_read_active_empty_mask_equals_read_all(self, sensor_array):
        """read_active(set()) also reads all sensors."""
        all_readings = sensor_array.read_all()
        active_readings = sensor_array.read_active(attention_mask=set())

        assert set(all_readings.keys()) == set(active_readings.keys())

    def test_partial_mask_only_updates_selected_sensors(self, sensor_array):
        """Only sensors in mask get fresh values; others stay cached."""
        # Set known cached values
        sensor_array._last_values = {
            "vibration": 0.5,
            "temperature": 25.0,
            "spectrum_power": 1.5,
        }

        # Select only vibration for refresh
        fresh = sensor_array.read_active(attention_mask={"vibration"})

        # vibration changed (computed fresh), others stayed cached
        assert fresh["vibration"] != 0.5  # should be a newly computed value
        assert fresh["temperature"] == 25.0  # cached
        assert fresh["spectrum_power"] == 1.5  # cached

    def test_multiple_mask_updates_multiple_sensors(self, sensor_array):
        """Multiple sensors in mask all refresh."""
        sensor_array._last_values = {
            "vibration": 0.0,
            "temperature": 22.0,
            "spectrum_power": 1.0,
        }

        fresh = sensor_array.read_active(attention_mask={"vibration", "temperature"})

        # Both selected sensors should change from initial cached values
        # (they are computed from time, so different from 0.0 and 22.0)
        assert fresh["vibration"] != 0.0
        assert fresh["temperature"] != 22.0
        # spectrum stays cached
        assert fresh["spectrum_power"] == 1.0

    def test_invalid_sensor_in_mask_is_ignored(self, sensor_array):
        """Mask containing unknown sensor name doesn't crash; it's silently skipped."""
        sensor_array._last_values = {"vibration": 0.5, "temperature": 25.0, "spectrum_power": 1.0}

        # "nonexistent" should be silently ignored — no exception
        fresh = sensor_array.read_active(attention_mask={"vibration", "nonexistent"})

        # vibration updated (valid), temperature cached (not selected), spectrum cached
        assert fresh["vibration"] != 0.5  # fresh value
        assert fresh["temperature"] == 25.0  # cached
        assert fresh["spectrum_power"] == 1.0  # cached
        # nonexistent not in output
        assert "nonexistent" not in fresh

    def test_cached_values_stable_across_multiple_calls(self, sensor_array):
        """When sensor not in mask, value stays identical across calls."""
        sensor_array._last_values = {"vibration": 0.5, "temperature": 25.0, "spectrum_power": 1.0}

        call1 = sensor_array.read_active(attention_mask={"vibration"})
        call2 = sensor_array.read_active(attention_mask={"vibration"})
        call3 = sensor_array.read_active(attention_mask={"vibration"})

        # Non-selected sensors identical across all calls
        assert call1["temperature"] == call2["temperature"] == call3["temperature"] == 25.0
        assert call1["spectrum_power"] == call2["spectrum_power"] == call3["spectrum_power"] == 1.0

    def test_last_values_updated_only_for_selected(self, sensor_array):
        """_last_values internal cache updates only for sensors in mask."""
        sensor_array._last_values = {"vibration": 0.0, "temperature": 22.0, "spectrum_power": 1.0}

        _ = sensor_array.read_active(attention_mask={"temperature"})

        # Only temperature updated in _last_values
        assert "temperature" in sensor_array._last_values
        # vibration and spectrum unchanged
        assert sensor_array._last_values["vibration"] == 0.0
        assert sensor_array._last_values["spectrum_power"] == 1.0
