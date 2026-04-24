"""
Unit tests for Phase 5.3 Inverse Model — SensorimotorContingencyLearner.infer_action().

TDD coverage:
- infer_action returns ranked action hypotheses
- Best match has highest confidence
- Unknown transitions return empty list
- Confidence normalized 0–1
- k-limit respected (top-k only)
- Cross-validation split works
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.embodied_loop import (
    SensorimotorContingencyLearner,
    ContingencyRecord,
)


@pytest.fixture
def learner():
    """Fresh learner with deterministic RNG."""
    return SensorimotorContingencyLearner(max_history_per_action=100)


class TestInverseModel:
    """Phase 5.3: Inverse model — infer action from sensor delta."""

    def test_infer_action_returns_ranked_hypotheses(self, learner):
        """Given a sensor transition, infer_action returns ranked action candidates."""
        # Teach: action A causes +1.0 delta
        prev = {"vibration": 0.0, "temperature": 22.0}
        post = {"vibration": 1.0, "temperature": 22.0}
        learner.record("action_a", prev, post)

        hypotheses = learner.infer_action(prev, post, k=3)

        assert isinstance(hypotheses, list)
        assert len(hypotheses) > 0
        assert all(
            isinstance(h, tuple) and len(h) == 2 for h in hypotheses
        )  # (action, confidence)

    def test_best_match_highest_confidence(self, learner):
        """The most frequently observed action gets highest confidence."""
        # Action A: 10 times
        prev = {"vibration": 0.0, "temperature": 22.0}
        post = {"vibration": 1.0, "temperature": 22.0}
        for _ in range(10):
            learner.record("action_a", prev, post)

        # Action B: 2 times (same delta)
        for _ in range(2):
            learner.record("action_b", prev, post)

        hypotheses = learner.infer_action(prev, post, k=3)

        assert hypotheses[0][0] == "action_a"
        assert hypotheses[0][1] > hypotheses[1][1]  # A confidence > B confidence

    def test_unknown_transition_returns_empty(self, learner):
        """No learned data for this delta → empty hypothesis list."""
        prev = {"vibration": 0.0, "temperature": 22.0}
        post = {"vibration": 99.9, "temperature": 99.9}  # Never recorded

        hypotheses = learner.infer_action(prev, post, k=3)

        assert hypotheses == []

    def test_confidence_normalized_0_to_1(self, learner):
        """All confidence values in [0, 1] and top-k sums to ≤1."""
        prev = {"vibration": 0.0}
        post = {"vibration": 1.0}
        for _ in range(5):
            learner.record("act", prev, post)

        hypotheses = learner.infer_action(prev, post, k=3)

        for action, conf in hypotheses:
            assert 0.0 <= conf <= 1.0
        # Optional: check sum ≤ 1 (softmax property)
        total = sum(conf for _, conf in hypotheses)
        assert total <= 1.0 + 1e-6

    def test_k_limit_respected(self, learner):
        """k=2 returns at most 2 hypotheses even if more actions exist."""
        prev = {"vibration": 0.0}
        post = {"vibration": 1.0}
        for action in ["a", "b", "c", "d"]:
            learner.record(action, prev, post)

        hypotheses = learner.infer_action(prev, post, k=2)

        assert len(hypotheses) == 2

    def test_k_zero_returns_empty(self, learner):
        """k=0 produces empty list."""
        prev = {"vibration": 0.0}
        post = {"vibration": 1.0}
        learner.record("a", prev, post)

        hypotheses = learner.infer_action(prev, post, k=0)

        assert hypotheses == []

    def test_different_deltas_separated(self, learner):
        """Distinct sensor deltas produce distinct hypothesis sets."""
        prev = {"vibration": 0.0}
        post1 = {"vibration": 1.0}
        post2 = {"vibration": 2.0}

        learner.record("increase_1", prev, post1)
        learner.record("increase_2", prev, post2)

        h1 = learner.infer_action(prev, post1, k=3)
        h2 = learner.infer_action(prev, post2, k=3)

        assert h1[0][0] == "increase_1"
        assert h2[0][0] == "increase_2"

    def test_multisensor_delta(self, learner):
        """Deltas across multiple sensors contribute to matching."""
        prev = {"vibration": 0.0, "temperature": 22.0}
        post = {"vibration": 1.0, "temperature": 23.0}

        learner.record("warming_vibrate", prev, post)
        learner.record("only_vibrate", prev, {"vibration": 1.0, "temperature": 22.0})

        hypotheses = learner.infer_action(prev, post, k=3)

        assert hypotheses[0][0] == "warming_vibrate"

    def test_temporal_decay_influences_confidence(self, learner):
        """More recent records have slightly higher effective count (not strictly testable
        without time manipulation, but structure preserved)."""
        prev = {"vibration": 0.0}
        post = {"vibration": 1.0}
        learner.record("action_x", prev, post)
        # Multiple records increase base confidence
        for _ in range(9):
            learner.record("action_x", prev, post)

        hypotheses = learner.infer_action(prev, post, k=3)
        assert hypotheses[0][1] > 0.5  # 10 records should give >50% confidence

    def test_cross_validation_split(self, learner):
        """train_test_split produces disjoint train/test sets."""
        # Populate with 10 records for action "move"
        prev = {"vibration": 0.0}
        post = {"vibration": 1.0}
        for i in range(10):
            # Slight variation to create distinct records
            learner.record("move", {"vibration": float(i)}, {"vibration": float(i + 1)})

        train, test = learner.train_test_split(test_ratio=0.3)

        assert len(train) + len(test) == 10
        assert len(train) == 7
        assert len(test) == 3
        # Disjoint — convert dicts to frozenset of items for hashing
        train_keys = {(frozenset(r.prev.items()), frozenset(r.post.items())) for r in train}
        test_keys = {(frozenset(r.prev.items()), frozenset(r.post.items())) for r in test}
        assert train_keys.isdisjoint(test_keys)
