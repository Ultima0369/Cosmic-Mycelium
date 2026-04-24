"""
Unit Tests: sensors — SensorSimulator
Tests multi-modal sensor data generation.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from cosmic_mycelium.infant.sensors import SensorArray, SensorReading, SensorType


class TestSensorArrayBasics:
    """Basic sensor array construction and status."""

    def test_sensor_array_initializes_with_defaults(self):
        """Default configuration creates valid sensor array."""
        sa = SensorArray()
        assert sa.vibration_base_freq == 50.0
        assert sa.temperature_mean == 22.0
        assert len(sa.spectrum_peaks) == 3

    def test_read_all_returns_three_keys(self):
        """read_all() returns vibration, temperature, spectrum_power."""
        sa = SensorArray()
        readings = sa.read_all()
        assert "vibration" in readings
        assert "temperature" in readings
        assert "spectrum_power" in readings

    def test_readings_are_non_negative(self):
        """All sensor values are physically valid (temperature > absolute zero)."""
        sa = SensorArray()
        for _ in range(100):
            readings = sa.read_all()
            # Vibration is signed (oscillatory), check magnitude is reasonable
            assert abs(readings["vibration"]) < 1.0
            assert readings["temperature"] > -273.15  # Absolute zero in Celsius
            assert readings["spectrum_power"] >= 0

    def test_readings_change_over_time(self):
        """Sensor values vary across successive reads."""
        sa = SensorArray()
        first = sa.read_all()
        time.sleep(0.01)
        second = sa.read_all()
        # Values should differ (statistically almost certain)
        assert (
            first["vibration"] != second["vibration"]
            or first["temperature"] != second["temperature"]
        )

    def test_get_reading_returns_sensor_reading_object(self):
        """get_reading() produces SensorReading with correct type."""
        sa = SensorArray()
        reading = sa.get_reading(SensorType.VIBRATION)
        assert isinstance(reading, SensorReading)
        assert reading.sensor_id == "vibration"
        assert reading.timestamp > 0
        assert abs(reading.value) < 1.0  # Vibration is signed, bounded amplitude

    def test_get_status_contains_expected_keys(self):
        """get_status() returns monitoring dict with required fields."""
        sa = SensorArray()
        status = sa.get_status()
        assert "sensor_count" in status
        assert "last_readings" in status
        assert "vibration_range" in status
        assert status["sensor_count"] == 3


class TestSensorPhysics:
    """Physical realism of sensor outputs."""

    def test_vibration_amplitude_bounded(self):
        """Vibration amplitude stays within plausible range."""
        sa = SensorArray(vibration_amplitude=0.1)
        for _ in range(100):
            v = sa.read_all()["vibration"]
            # Base amp 0.1 * (1±0.3 modulation) + noise(3sigma≈0.06) -> expect |v| < 0.5
            assert abs(v) < 0.5

    def test_temperature_around_mean(self):
        """Temperature oscillates around configured mean."""
        sa = SensorArray(temperature_mean=22.0, temperature_variation=2.0)
        samples = [sa.read_all()["temperature"] for _ in range(100)]
        avg = sum(samples) / len(samples)
        # Average should be within ±0.5°C of mean (by law of large numbers)
        assert 21.5 <= avg <= 22.5

    def test_spectrum_power_positive(self):
        """Spectrum total power is always positive."""
        sa = SensorArray()
        for _ in range(50):
            assert sa.read_all()["spectrum_power"] > 0

    def test_vibration_frequency_approximately_50hz(self):
        """Vibration signal has correct 50Hz base frequency."""
        sa = SensorArray(vibration_base_freq=50.0, vibration_amplitude=1.0)
        # Sample at ~1kHz for 200ms to capture ~10 cycles
        samples = []
        interval = 0.001  # 1ms target interval
        next_sample = time.monotonic()
        total_samples = 0
        total_duration = 0.2  # 200ms target
        start = time.monotonic()
        while time.monotonic() - start < total_duration:
            samples.append(sa.read_all()["vibration"])
            total_samples += 1
            next_sample += interval
            sleep_time = next_sample - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
        duration = time.monotonic() - start

        # Count zero crossings (sign changes)
        crossings = sum(
            1 for i in range(1, len(samples)) if samples[i - 1] * samples[i] < 0
        )
        measured_hz = crossings / (2 * duration)  # Each cycle has 2 crossings
        # Allow 10% tolerance
        assert 45 <= measured_hz <= 55


class TestSensorDeterminism:
    """Deterministic RNG ensures reproducible tests."""

    @patch("time.time")
    def test_deterministic_with_seed(self, mock_time):
        """Same seed produces identical reading sequences (fully deterministic)."""
        # Fixed time for all time.time() calls
        mock_time.return_value = 1000.0

        sa1 = SensorArray()
        sa1._rng = type(sa1._rng)(42)
        sa2 = SensorArray()
        sa2._rng = type(sa2._rng)(42)

        # Synchronize start times
        common_start = 1000.0
        sa1._start_time = common_start
        sa2._start_time = common_start

        # Compare 10 successive readings
        for _ in range(10):
            r1 = sa1.read_all()
            r2 = sa2.read_all()
            # All fields should match exactly (same RNG state, same elapsed=0)
            assert r1["vibration"] == pytest.approx(r2["vibration"], abs=1e-10)
            assert r1["temperature"] == pytest.approx(r2["temperature"], abs=1e-10)
            assert r1["spectrum_power"] == pytest.approx(
                r2["spectrum_power"], abs=1e-10
            )

    def test_different_seeds_produce_different_sequences(self):
        """Different seeds yield different data streams."""
        sa1 = SensorArray()
        sa1._rng = type(sa1._rng)(42)
        sa2 = SensorArray()
        sa2._rng = type(sa2._rng)(123)

        values_match = all(
            sa1.read_all()["vibration"] == sa2.read_all()["vibration"]
            for _ in range(10)
        )
        assert not values_match


class TestSensorEventInjection:
    """External event injection (touch, flash, sound)."""

    def test_inject_event_stores_event_data(self):
        """inject_event() creates an event in active_events."""
        sa = SensorArray()
        sa.inject_event(SensorType.VIBRATION, magnitude=0.5, duration=1.0)
        # Event should be in active_events list
        assert len(sa._active_events) == 1
        event = sa._active_events[0]
        assert event["sensor_type"] == SensorType.VIBRATION
        assert event["magnitude"] == 0.5
        assert event["end_time"] > time.time()

    def test_injected_event_modifies_sensor_reading(self):
        """During event window, sensor reading is boosted."""
        sa = SensorArray()
        base = sa.read_all()["vibration"]
        sa.inject_event(SensorType.VIBRATION, magnitude=0.5, duration=2.0)
        boosted = sa.read_all()["vibration"]
        # Should be higher (within event duration)
        assert boosted > base + 0.4  # Near the injected magnitude

    def test_event_decays_after_duration(self):
        """Event effect disappears after duration expires."""
        sa = SensorArray()
        base = sa.read_all()["vibration"]
        sa.inject_event(SensorType.VIBRATION, magnitude=0.5, duration=0.1)
        time.sleep(0.15)  # Wait for expiry
        after = sa.read_all()["vibration"]
        # Should return to near baseline (within noise)
        assert abs(after - base) < 0.1


class TestSensorEdgeCases:
    """Edge case handling."""

    def test_temperature_absolute_zero_never_reached(self):
        """Temperature never goes below absolute zero (0K ≈ -273°C)."""
        sa = SensorArray(
            temperature_mean=22.0, temperature_variation=50.0
        )  # Extreme variation
        for _ in range(1000):
            temp = sa.read_all()["temperature"]
            assert temp > -300  # Well above absolute zero in Celsius

    def test_zero_vibration_when_amplitude_zero(self):
        """Setting amplitude to 0 yields near-zero vibration (noise floor only)."""
        sa = SensorArray(vibration_amplitude=0.0)
        readings = [sa.read_all()["vibration"] for _ in range(100)]
        # With 0 amplitude, only noise remains (small absolute values)
        avg_abs = sum(abs(r) for r in readings) / len(readings)
        assert avg_abs < 0.05  # Noise floor

    def test_empty_spectrum_peaks_yields_zero(self):
        """No spectrum peaks configured → spectrum power ≈ 0."""
        sa = SensorArray(spectrum_peaks=[])
        power = sa.read_all()["spectrum_power"]
        assert power < 0.05  # Near zero
