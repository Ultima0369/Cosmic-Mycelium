"""
Layer 1 — Timescale Segmenter (Abstract Segmentation Layer)
Multi-scale time/space segmentation, feature extraction.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Scale(IntEnum):
    """Timescale enumeration — the fractal hierarchy of time."""

    MILLISECOND = 1
    SECOND = 2
    MINUTE = 3
    HOUR = 4
    DAY = 5
    WEEK = 6


@dataclass
class Segment:
    """A segmented time/space window."""

    start_time: float
    end_time: float
    features: dict[str, Any] = field(default_factory=dict)
    scale: Scale = Scale.MILLISECOND


class TimescaleSegmenter:
    """
    Layer 1: Abstract Segmentation.

    Splits continuous sensor/data streams into segments at multiple timescales.
    Maintains separate sliding windows per scale and escalates when full.
    """

    def __init__(
        self,
        ms_window: int = 1000,
        sec_window: int = 100,
        min_window: int = 60,
    ):
        """
        Args:
            ms_window: Capacity of millisecond window (samples)
            sec_window: Capacity of second window (samples)
            min_window: Capacity of minute window (samples)
        """
        self.millisecond_window: deque = deque(maxlen=ms_window)
        self.second_window: deque = deque(maxlen=sec_window)
        self.minute_window: deque = deque(maxlen=min_window)
        self.current_scale = Scale.MILLISECOND

    def accumulate(self, data: dict) -> None:
        """
        Add a data point to all windows.
        Escalates scale if current window becomes full.
        """
        self.millisecond_window.append(data)
        self.second_window.append(data)
        self.minute_window.append(data)

        # Check if current scale window is full and escalate
        window = self._get_window_for_scale(self.current_scale)
        if window is not None and len(window) >= window.maxlen:
            self.escalate_scale()

    def _get_window_for_scale(self, scale: Scale) -> deque | None:
        """Get the deque corresponding to a scale."""
        mapping = {
            Scale.MILLISECOND: self.millisecond_window,
            Scale.SECOND: self.second_window,
            Scale.MINUTE: self.minute_window,
        }
        return mapping.get(scale)

    def create_segment(self) -> Segment:
        """
        Create a segment from the current window's data.
        Returns a Segment with extracted features.
        """
        window = self._get_window_for_scale(self.current_scale)
        if window is None or len(window) == 0:
            return Segment(
                start_time=time.time(),
                end_time=time.time(),
                features={},
                scale=self.current_scale,
            )

        values = [d.get("v", 0.0) for d in window]
        count = len(values)
        mean_val = sum(values) / count if count > 0 else 0.0

        features = {
            "count": count,
            "mean_value": mean_val,
            "min_value": min(values) if values else 0.0,
            "max_value": max(values) if values else 0.0,
        }

        return Segment(
            start_time=time.time(),
            end_time=time.time() + 0.001 * self.current_scale.value,
            features=features,
            scale=self.current_scale,
        )

    def escalate_scale(self) -> None:
        """Move to coarser timescale."""
        if self.current_scale < Scale.MINUTE:
            self.current_scale = Scale(self.current_scale.value + 1)

    def reset(self) -> None:
        """Clear all time windows and reset to millisecond scale."""
        self.millisecond_window.clear()
        self.second_window.clear()
        self.minute_window.clear()
        self.current_scale = Scale.MILLISECOND
