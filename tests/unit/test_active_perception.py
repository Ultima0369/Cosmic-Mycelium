"""
Unit tests for ActivePerceptionGate (Phase 5.1-2).

TDD coverage:
- update() increases interest on large prediction errors
- decay() gradually reduces all interest scores
- get_attention_mask() returns top-k sensors
- should_sample() threshold check
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.active_perception import ActivePerceptionGate


@pytest.fixture
def gate():
    """Fresh gate with default parameters."""
    return ActivePerceptionGate(initial_interest=0.1, decay_rate=0.9, boost=2.0)


class TestActivePerceptionGate:
    """Attention-based sensor selection."""

    def test_initial_state_all_sensors_at_baseline(self, gate):
        """New gate starts with empty interest dict."""
        assert gate.interest_scores == {}

    def test_update_boosts_interest_on_large_error(self, gate):
        """update() increases interest for sensors with high prediction error."""
        # Large error on vibration, small on temperature
        gate.update({"vibration": 1.0, "temperature": 0.1})

        scores = gate.interest_scores
        assert scores["vibration"] > scores["temperature"]

    def test_update_decays_existing_scores(self, gate):
        """Repeated updates decay previous scores."""
        gate.update({"a": 0.5})
        score_after_first = gate.interest_scores["a"]

        # Second update with zero error should decay
        gate.update({"a": 0.0})
        score_after_second = gate.interest_scores["a"]

        assert score_after_second < score_after_first

    def test_decay_method_reduces_all_scores(self, gate):
        """decay() multiplies all scores by decay factor."""
        gate.interest_scores = {"x": 1.0, "y": 0.5}
        gate.decay()

        assert pytest.approx(gate.interest_scores["x"]) == 0.9
        assert pytest.approx(gate.interest_scores["y"]) == 0.45

    def test_get_attention_mask_returns_top_k(self, gate):
        """get_attention_mask(k) returns k highest-scoring sensors."""
        gate.interest_scores = {
            "a": 0.9,
            "b": 0.3,
            "c": 0.6,
            "d": 0.1,
        }
        top2 = gate.get_attention_mask(k=2)
        assert top2 == {"a", "c"}

    def test_get_attention_mask_all_when_fewer_than_k(self, gate):
        """Returns all sensors when fewer than k exist."""
        gate.interest_scores = {"a": 0.5, "b": 0.3}
        mask = gate.get_attention_mask(k=5)
        assert mask == {"a", "b"}

    def test_should_sample_threshold_check(self, gate):
        """should_sample() returns True if score >= threshold."""
        gate.interest_scores = {"x": 0.8, "y": 0.3}

        assert gate.should_sample("x", threshold=0.5) is True
        assert gate.should_sample("y", threshold=0.5) is False

    def test_new_sensor_initialized_on_first_error(self, gate):
        """Sensors not seen before start at error * boost (surprise-driven)."""
        gate.update({"new_sensor": 0.5})

        assert "new_sensor" in gate.interest_scores
        assert pytest.approx(gate.interest_scores["new_sensor"]) == 0.5 * 2.0  # error * boost

    def test_interest_stays_non_negative(self, gate):
        """Decay never drives scores negative."""
        gate.interest_scores = {"a": 0.01}
        for _ in range(100):
            gate.decay()

        assert gate.interest_scores["a"] >= 0

    def test_reset_clears_all_scores(self, gate):
        """reset() empties interest dict."""
        gate.interest_scores = {"a": 1.0, "b": 0.5}
        gate.reset()
        assert gate.interest_scores == {}
