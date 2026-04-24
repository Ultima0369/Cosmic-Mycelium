"""
Unit tests for SensorimotorContingencyLearner (Phase 5.1).

TDD coverage:
- record() accumulates delta observations
- predict() returns weighted prediction or None for unknown actions
- get_contingency() returns avg delta vector
- known_actions() lists learned actions
- get_confidence() grows with observations
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.embodied_loop import (
    SensorimotorContingencyLearner,
    SensorReading,
)


@pytest.fixture
def learner():
    """Fresh learner instance."""
    return SensorimotorContingencyLearner(max_history_per_action=10)


class TestSensorimotorContingencyLearner:
    """Core learning and prediction behaviors."""

    def test_record_single_observation(self, learner):
        """record() stores a single action→delta mapping."""
        prev = {"vibration": 0.2, "temperature": 25.0}
        post = {"vibration": 0.8, "temperature": 25.1}
        learner.record("adjust_breath", prev, post)

        assert "adjust_breath" in learner.known_actions()
        contingency = learner.get_contingency("adjust_breath")
        assert contingency is not None
        assert pytest.approx(contingency["vibration"]) == 0.6
        assert pytest.approx(contingency["temperature"]) == 0.1

    def test_record_multiple_observations_average(self, learner):
        """Multiple records produce averaged deltas."""
        action = "contract_ms=150"
        for i in range(5):
            learner.record(
                action,
                {"vibration": 0.1},
                {"vibration": 0.1 + 0.5},  # delta = 0.5 each time
            )

        contingency = learner.get_contingency(action)
        assert pytest.approx(contingency["vibration"]) == 0.5

    def test_record_mixed_sensor_sets(self, learner):
        """Handles observations with different sensor sets gracefully."""
        learner.record("action1", {"a": 1.0, "b": 2.0}, {"a": 2.0, "c": 3.0})
        # delta: a=+1.0, b=-2.0, c=+3.0
        c = learner.get_contingency("action1")
        assert pytest.approx(c["a"]) == 1.0
        assert pytest.approx(c["b"]) == -2.0
        assert pytest.approx(c["c"]) == 3.0

    def test_predict_returns_updated_sensors(self, learner):
        """predict() applies avg delta to current sensors."""
        learner.record("act", {"x": 0.0}, {"x": 1.0})  # avg delta = +1

        pred = learner.predict("act", {"x": 5.0, "y": 2.0})
        assert pred is not None
        assert pytest.approx(pred["x"]) == 6.0
        assert pred["y"] == 2.0  # unchanged

    def test_predict_unknown_action_returns_none(self, learner):
        """predict() returns None for unseen actions."""
        pred = learner.predict("unknown", {"x": 1.0})
        assert pred is None

    def test_known_actions_lists_all(self, learner):
        """known_actions() returns all learned action signatures."""
        learner.record("a1", {"s": 1}, {"s": 2})
        learner.record("a2", {"s": 1}, {"s": 3})
        actions = set(learner.known_actions())
        assert actions == {"a1", "a2"}

    def test_get_confidence_increases_with_observations(self, learner):
        """Confidence rises as more observations are collected, saturating ~0.8 at 20."""
        action = "frequent_action"
        for _ in range(25):
            learner.record(action, {"s": 0}, {"s": 1})

        conf = learner.get_confidence(action)
        assert conf > 0.8  # 25/(25+5) = 0.83

    def test_get_confidence_zero_for_unknown(self, learner):
        assert learner.get_confidence("never_seen") == 0.0

    def test_get_status_returns_summary(self, learner):
        """get_status() provides monitoring info."""
        learner.record("act1", {"a": 1}, {"a": 2})
        learner.record("act2", {"b": 1}, {"b": 2})

        status = learner.get_status()
        assert status["known_actions"] == 2
        assert status["total_observations"] == 2
        assert set(status["actions"]) == {"act1", "act2"}

    def test_max_history_enforcement(self, learner):
        """Older observations are evicted when window exceeded."""
        action = "bounded"
        for i in range(15):  # max_history=10
            learner.record(action, {"s": 0}, {"s": float(i)})

        # Average of last 10 values (5..14) = 9.5
        contingency = learner.get_contingency(action)
        assert pytest.approx(contingency["s"]) == 9.5
