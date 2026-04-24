"""
Integration test: Embodied Cognition Loop — sensorimotor learning + active perception.

Tests end-to-end flow across multiple breath cycles:
- Learner accumulates (action, prev_sensors, post_sensors) records
- Predictions become possible after enough observations
- Active perception gate tracks sensor uncertainty

Note: These tests patch infant.act() to return a valid non-suspend action,
bypassing the decision pipeline (which may SUSPEND due to low confidence).
This isolates the embodied recording mechanism.
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.common.data_packet import CosmicPacket


@pytest.mark.asyncio
class TestEmbodiedLoopIntegration:
    """Full infant cycle with embodied components."""

    async def test_sensorimotor_learner_accumulates_across_cycles(self, monkeypatch):
        """After N cycles, learner has recorded action→sensor deltas."""
        infant = SiliconInfant(
            infant_id="embodied-test-01",
            config={"energy_max": 100.0, "contract_duration": 0.01, "diffuse_duration": 0.001}
        )
        learner = infant._sensorimotor_learner

        # Patch act() to always return a valid action (bypass SUSPEND due to low confidence)
        call_count = {"n": 0}
        def fake_act(perception, predicted, confidence):
            call_count["n"] += 1
            return CosmicPacket(
                timestamp=perception["timestamp"],
                source_id=infant.infant_id,
                value_payload={
                    "action": "plan_execution",
                    "plan": {"path": [f"step_{call_count['n']}"]},
                    "confidence": confidence,
                    "sensor_snapshot": perception.get("sensors", {}),
                },
            )
        monkeypatch.setattr(infant, "act", fake_act)

        # Run a few CONTRACT cycles (actions happen)
        for _ in range(5):
            infant.breath_cycle()

        # Learner should have recorded at least one action
        actions = learner.known_actions()
        assert len(actions) > 0, "No actions learned by learner"

        # Contingency for first action should have non-zero deltas
        first_action = actions[0]
        contingency = learner.get_contingency(first_action)
        assert contingency is not None
        # At least one sensor delta is non-zero (action changed something)
        assert any(abs(v) > 0 for v in contingency.values())

    async def test_active_perception_updates_from_prediction_error(self, monkeypatch):
        """Prediction error from verify() propagates to perception gate."""
        infant = SiliconInfant(
            infant_id="embodied-test-02",
            config={"energy_max": 100.0, "contract_duration": 0.01, "diffuse_duration": 0.001}
        )
        gate = infant._active_perception_gate

        # Patch act() to return valid action
        monkeypatch.setattr(infant, "act", lambda *a, **kw: CosmicPacket(
            timestamp=0, source_id=infant.infant_id, value_payload={"action": "plan_execution", "plan": {"path": ["x"]}}
        ))

        # Run several cycles to accumulate error signals
        for _ in range(5):
            infant.breath_cycle()

        # After cycles, gate should have some interest scores
        scores = gate.interest_scores
        assert len(scores) > 0, "Active perception gate has no sensor interests"
        # At least one sensor should have non-zero interest (errors drove updates)
        assert any(v > 0 for v in scores.values())

    async def test_learner_predicts_after_learning(self, monkeypatch):
        """Once learned, learner.predict() returns plausible post-sensor values."""
        infant = SiliconInfant(
            infant_id="embodied-test-03",
            config={"energy_max": 100.0, "contract_duration": 0.01, "diffuse_duration": 0.001}
        )
        learner = infant._sensorimotor_learner

        # Patch act() to return valid action
        monkeypatch.setattr(infant, "act", lambda *a, **kw: CosmicPacket(
            timestamp=0, source_id=infant.infant_id, value_payload={"action": "plan_execution", "plan": {"path": ["x"]}}
        ))

        # Collect some history first
        for _ in range(3):
            infant.breath_cycle()

        # Pick a known action and a sensor reading
        actions = learner.known_actions()
        assert len(actions) > 0
        action = actions[0]

        # Current sensors from latest perception
        current_sensors = infant.sensors.read_all()
        predicted = learner.predict(action, current_sensors)
        assert predicted is not None
        # Predicted should have at least the sensor keys that learner saw
        assert set(predicted.keys()).intersection(current_sensors.keys())

    async def test_get_active_sensors_returns_top_k(self, monkeypatch):
        """get_active_sensors(k) returns k most interesting sensors."""
        infant = SiliconInfant(
            infant_id="embodied-test-04",
            config={"energy_max": 100.0, "contract_duration": 0.01, "diffuse_duration": 0.001}
        )
        # Patch act() to return valid action
        monkeypatch.setattr(infant, "act", lambda *a, **kw: CosmicPacket(
            timestamp=0, source_id=infant.infant_id, value_payload={"action": "plan_execution", "plan": {"path": ["x"]}}
        ))

        # Run a few cycles to populate gate
        for _ in range(5):
            infant.breath_cycle()

        top3 = infant.get_active_sensors(k=3)
        assert isinstance(top3, set)
        assert len(top3) <= 3
        # Should be subset of known sensors
        all_sensors = set(infant.sensors.read_all().keys())
        assert top3.issubset(all_sensors)
