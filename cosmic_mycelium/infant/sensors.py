"""
Sensor Simulator — Realistic Multi-Modal Sensor Data Generation
Generates synthetic sensor streams for infant perception: vibration, temperature, spectrum.
Physical values anchor to real-world ranges for biological plausibility.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


class SensorType(Enum):
    VIBRATION = "vibration"    # Seismic/mechanical waves (Hz, amplitude)
    TEMPERATURE = "temperature"  # Celsius
    SPECTRUM = "spectrum"      # Light frequency distribution (nm, intensity)


@dataclass
class SensorReading:
    """A single sensor reading at a timestamp."""
    timestamp: float
    sensor_id: str
    value: float
    metadata: Optional[Dict] = None


@dataclass
class SensorArray:
    """
    An array of sensors providing multi-modal perception.

    Generates biologically-plausible sensor data:
    - Vibration: sinusoidal base + noise, amplitude-modulated
    - Temperature: slow drift with daily cycle + random walk
    - Spectrum: multi-peak distribution (simulating light sources)
    """

    # Configuration
    vibration_base_freq: float = 50.0      # Hz (mains hum)
    vibration_amplitude: float = 0.1       # Base amplitude
    temperature_mean: float = 22.0         # Celsius (room temp)
    temperature_variation: float = 2.0     # Daily cycle amplitude
    spectrum_peaks: list[Tuple[float, float]] = field(default_factory=lambda: [
        (450.0, 0.8),   # Blue peak (nm)
        (550.0, 1.0),   # Green peak (nm)
        (650.0, 0.6),   # Red peak (nm)
    ])

    # Internal state
    _start_time: float = field(init=False, default_factory=time.time)
    _last_values: Dict[str, float] = field(init=False, default_factory=dict)
    _active_events: list[Dict] = field(init=False, default_factory=list)
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        self._rng = random.Random(42)  # Deterministic for tests

    def read_all(self) -> Dict[str, float]:
        """
        Read all sensors and return current physical state dict.

        Returns:
            Dict with keys: vibration, temperature, spectrum_power
        """
        now = time.time()
        elapsed = now - self._start_time

        # Clean up expired events
        self._active_events = [
            e for e in self._active_events
            if e["end_time"] > now
        ]

        # Compute event boosts per sensor type
        event_boost = {"vibration": 0.0, "temperature": 0.0, "spectrum_power": 0.0}
        for event in self._active_events:
            sensor_key = event["sensor_type"].value
            if sensor_key in event_boost:
                event_boost[sensor_key] += event["magnitude"]

        # Vibration: base sine + amplitude modulation + noise + event boost
        # Signed signal — physical displacement can be positive or negative
        vib_base = self.vibration_amplitude * math.sin(2 * math.pi * self.vibration_base_freq * elapsed)
        vib_mod = 0.3 * math.sin(2 * math.pi * 0.5 * elapsed)  # Slow amplitude modulation
        vib_noise = self._rng.gauss(0, 0.02)
        vibration = vib_base * (1 + vib_mod) + vib_noise + event_boost["vibration"]

        # Temperature: daily cycle + noise + event boost
        daily_cycle = self.temperature_variation * math.sin(2 * math.pi * elapsed / 86400)
        temp_noise = self._rng.gauss(0, 0.1)
        temperature = self.temperature_mean + daily_cycle + temp_noise + event_boost["temperature"]

        # Spectrum: sum of Gaussian peaks + noise + event boost
        total_power = 0.0
        for peak_nm, peak_intensity in self.spectrum_peaks:
            power = peak_intensity * math.exp(-((elapsed % 10) ** 2) / 2)
            total_power += power
        spectrum_noise = self._rng.uniform(0, 0.05)
        spectrum_power = max(0.0, total_power + spectrum_noise + event_boost["spectrum_power"])

        self._last_values = {
            "vibration": vibration,
            "temperature": temperature,
            "spectrum_power": spectrum_power,
        }

        return self._last_values.copy()

    def get_reading(self, sensor_type: SensorType) -> SensorReading:
        """Get a single sensor reading with timestamp."""
        values = self.read_all()
        return SensorReading(
            timestamp=time.time(),
            sensor_id=sensor_type.value,
            value=values[sensor_type.value],
        )

    def inject_event(self, sensor_type: SensorType, magnitude: float, duration: float) -> None:
        """
        Inject an external event (e.g., touch, flash, sound).

        Args:
            sensor_type: Which sensor to affect
            magnitude: Event strength (added to baseline)
            duration: How long the event lasts (seconds)
        """
        self._active_events.append({
            "sensor_type": sensor_type,
            "magnitude": magnitude,
            "end_time": time.time() + duration,
        })

    def get_status(self) -> Dict:
        """Return sensor array status for monitoring."""
        readings = self.read_all()
        return {
            "sensor_count": 3,
            "last_readings": readings,
            "vibration_range": [0.0, 1.0],
            "temperature_range": [15.0, 30.0],
            "spectrum_range": [0.0, 3.0],
        }
