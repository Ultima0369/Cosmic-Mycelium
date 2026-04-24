"""
Embodied Metacognition — Phase 5.5

Monitors sensorimotor learning progress to toggle between
exploration and exploitation modes. Uses a rolling average
of action confidence (inverse model posterior) with hysteresis
thresholds to prevent flickering.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class MetacognitiveMode(Enum):
    """Learning strategy mode."""
    EXPLORE = "explore"  # try new actions, build model
    EXPLOIT = "exploit"  # use known high-confidence actions


@dataclass
class EmbodiedMetacognition:
    """
    Tracks confidence across actions and switches between EXPLORE/EXPLOIT.

    Hysteresis: separate thresholds for entering EXPLOIT (higher) and
    reverting to EXPLORE (lower) prevent rapid oscillation on borderline
    confidence values.

    Example:
        meta = EmbodiedMetacognition(switch_threshold=0.6, revert_threshold=0.4, window_size=5)
        meta.update({"a": 0.8, "b": 0.7})  # avg=0.75 → EXPLOIT
        meta.get_mode()  # MetacognitiveMode.EXPLOIT
    """

    switch_threshold: float  # avg confidence above → EXPLOIT
    revert_threshold: float  # avg confidence below → EXPLORE
    window_size: int = field(default=5)

    _window: deque[float] = field(init=False, default_factory=lambda: deque(maxlen=1))
    _mode: MetacognitiveMode = field(init=False, default=MetacognitiveMode.EXPLORE)
    _sample_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        object.__setattr__(self, '_window', deque(maxlen=self.window_size))

    def update(self, confidence_dict: Dict[str, float]) -> None:
        """
        Process learner confidence outputs for the current cycle.

        Args:
            confidence_dict: {action_signature: posterior_confidence}
        """
        if confidence_dict:
            avg = sum(confidence_dict.values()) / len(confidence_dict)
        else:
            avg = 0.0
        self._window.append(avg)
        self._sample_count += 1
        # Only switch mode once we have a full window of data
        if self._sample_count < self.window_size:
            return
        rolling = sum(self._window) / len(self._window)
        if self._mode is MetacognitiveMode.EXPLORE and rolling > self.switch_threshold:
            self._mode = MetacognitiveMode.EXPLOIT
        elif self._mode is MetacognitiveMode.EXPLOIT and rolling < self.revert_threshold:
            self._mode = MetacognitiveMode.EXPLORE

    def get_mode(self) -> MetacognitiveMode:
        """Return current metacognitive mode."""
        return self._mode

    def get_exploration_factor(self) -> float:
        """
        Return exploration factor for the slime explorer.

        EXPLORE → high randomness (0.6)
        EXPLOIT → low randomness, follow known paths (0.1)
        """
        return 0.6 if self._mode is MetacognitiveMode.EXPLORE else 0.1
