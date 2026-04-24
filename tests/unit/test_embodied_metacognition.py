"""
Unit tests for Phase 5.5 Embodied Metacognition — learning-progress monitor.

TDD coverage:
- Mode starts as EXPLORE
- Switches to EXPLOIT when average confidence exceeds threshold
- Reverts to EXPLORE when confidence drops
- get_mode() returns current mode
- update() called each cycle processes learner stats
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.embodied_metacognition import (
    EmbodiedMetacognition,
    MetacognitiveMode,
)


@pytest.fixture
def meta():
    """Fresh metacognition with defaults."""
    return EmbodiedMetacognition(
        switch_threshold=0.6,  # confidence above -> exploit
        revert_threshold=0.4,  # confidence below -> explore
        window_size=5,
    )


class TestEmbodiedMetacognition:
    """Phase 5.5: Monitor sensorimotor learning to toggle explore/exploit."""

    def test_initial_mode_is_explore(self, meta):
        assert meta.get_mode() == MetacognitiveMode.EXPLORE

    def test_switches_to_exploit_when_confidence_high(self, meta):
        # Feed high confidence values
        for _ in range(5):
            meta.update({"action_a": 0.8, "action_b": 0.7})
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT

    def test_reverts_to_explore_when_confidence_drops(self, meta):
        # First raise to exploit
        for _ in range(5):
            meta.update({"a": 0.8})
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT
        # Then drop
        for _ in range(5):
            meta.update({"a": 0.2})
        assert meta.get_mode() == MetacognitiveMode.EXPLORE

    def test_hysteresis(self, meta):
        """Different thresholds for switch up vs down prevent flickering."""
        # Start explore
        assert meta.get_mode() == MetacognitiveMode.EXPLORE
        # Raise confidence to between thresholds: above revert but below switch
        for _ in range(5):
            meta.update({"a": 0.5})  # 0.4 < 0.5 < 0.6
        assert meta.get_mode() == MetacognitiveMode.EXPLORE  # not high enough to switch
        # Now go above switch threshold
        for _ in range(5):
            meta.update({"a": 0.9})
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT
        # Drop back to middle: should stay exploit until below revert
        for _ in range(5):
            meta.update({"a": 0.5})
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT

    def test_windowed_average(self, meta):
        """Mode depends on recent window, not all history."""
        # Push high values for 3 cycles (window=5, need at least 5 updates to affect)
        for _ in range(3):
            meta.update({"a": 0.9})
        assert meta.get_mode() == MetacognitiveMode.EXPLORE  # not enough samples yet
        # Add two more
        for _ in range(2):
            meta.update({"a": 0.9})
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT

    def test_unknown_actions_ignored(self, meta):
        """Empty confidence dict doesn't crash."""
        meta.update({})
        assert meta.get_mode() == MetacognitiveMode.EXPLORE

    def test_mixed_confidences(self, meta):
        """Average across multiple actions."""
        for _ in range(5):
            meta.update({"a": 0.8, "b": 0.4})  # avg 0.6 -> exploit
        assert meta.get_mode() == MetacognitiveMode.EXPLOIT
