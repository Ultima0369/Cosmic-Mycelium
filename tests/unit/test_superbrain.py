"""
Layer 5 — SuperBrain Tests
Tests multi-region processing, attention competition, global workspace, decay.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cosmic_mycelium.infant.core.layer_5_superbrain import (
    SuperBrain,
)


class TestSuperBrainInitialization:
    """Tests for brain construction."""

    def test_default_num_regions(self):
        """Default number of regions is 5."""
        brain = SuperBrain()
        assert brain.num_regions == 5

    def test_all_default_regions_exist(self):
        """All five default regions are present."""
        brain = SuperBrain()
        expected = {"sensory", "predictor", "planner", "executor", "meta"}
        assert set(brain.regions.keys()) == expected

    def test_working_memory_limits(self):
        """Each region's working_memory respects maxlen."""
        brain = SuperBrain()
        for region in brain.regions.values():
            assert hasattr(region.working_memory, "maxlen")
            assert region.working_memory.maxlen == 100

    def test_all_regions_start_at_zero_activation(self):
        """Initial activation is 0.0 for all regions."""
        brain = SuperBrain()
        for region in brain.regions.values():
            assert region.activation == 0.0


class TestPerception:
    """Tests for perceive() sensory input routing."""

    def test_perceive_stores_stimulus_in_sensory_region(self):
        """Perceived stimulus appended to sensory working_memory."""
        brain = SuperBrain()
        stimulus = {"sensor": "vibration", "value": 0.5}

        brain.perceive(stimulus)

        sensory = brain.regions["sensory"]
        assert len(sensory.working_memory) == 1
        assert sensory.working_memory[0] == stimulus

    def test_perceive_increments_sensory_activation(self):
        """Sensory region activation increases on perceive."""
        brain = SuperBrain()
        initial = brain.regions["sensory"].activation

        brain.perceive({"x": 1.0})

        assert brain.regions["sensory"].activation > initial

    def test_perceive_respects_maxlen(self):
        """Working memory FIFO evicts oldest when full."""
        brain = SuperBrain()
        sensory = brain.regions["sensory"]
        for i in range(110):
            brain.perceive({"i": i})

        assert len(sensory.working_memory) == 100
        assert sensory.working_memory[0]["i"] == 10  # First 10 evicted


class TestPrediction:
    """Tests for predict() from predictor region."""

    def test_predict_returns_dict(self):
        """predict() returns a dict with next_state."""
        brain = SuperBrain()
        context = {"state": {"q": 1.0, "p": 0.0}}
        result = brain.predict(context)

        assert isinstance(result, dict)
        assert "next_state" in result

    def test_predict_increments_predictor_activation(self):
        """Predictor region activation increases on predict."""
        brain = SuperBrain()
        initial = brain.regions["predictor"].activation

        brain.predict({"test": 1.0})

        assert brain.regions["predictor"].activation > initial


class TestPlanning:
    """Tests for plan() and plan selection."""

    def test_plan_returns_plan_object(self):
        """plan() returns a dict with path, quality, metadata."""
        brain = SuperBrain()
        context = {"goal": "orbit"}
        result = brain.plan(context)

        assert isinstance(result, dict)
        assert "path" in result
        assert "quality" in result
        assert isinstance(result["quality"], float)

    def test_plan_quality_in_range(self):
        """Plan quality is a float 0-1."""
        brain = SuperBrain()
        for _ in range(10):
            plan = brain.plan({"seed": _})
            assert 0.0 <= plan["quality"] <= 1.0

    def test_plan_increments_planner_activation(self):
        """Planner activation increases on plan()."""
        brain = SuperBrain()
        initial = brain.regions["planner"].activation
        brain.plan({"g": "test"})
        assert brain.regions["planner"].activation > initial


class TestExecution:
    """Tests for execute() via executor region."""

    def test_execute_processes_action(self):
        """execute() records action in executor working memory."""
        brain = SuperBrain()
        action = {"type": "move", "target": "x=5"}
        brain.execute(action)

        executor = brain.regions["executor"]
        assert len(executor.working_memory) == 1

    def test_execute_increments_executor_activation(self):
        """Executor activation increases on execute."""
        brain = SuperBrain()
        initial = brain.regions["executor"].activation
        brain.execute({"cmd": "run"})
        assert brain.regions["executor"].activation > initial


class TestGlobalWorkspace:
    """Tests for broadcast_global_workspace()."""

    def test_broadcast_increases_all_region_activations(self):
        """Broadcast bumps activation for all regions."""
        brain = SuperBrain()
        message = {"priority": 0.9}
        initial_activations = {name: r.activation for name, r in brain.regions.items()}

        brain.broadcast_global_workspace(message)

        for name, region in brain.regions.items():
            assert region.activation > initial_activations[name]

    def test_broadcast_records_in_meta_region(self):
        """Meta region logs broadcast messages."""
        brain = SuperBrain()
        message = {"event": "test_broadcast"}
        brain.broadcast_global_workspace(message)

        meta = brain.regions["meta"]
        assert len(meta.working_memory) >= 1
        assert message in meta.working_memory


class TestDecay:
    """Tests for decay_activations()."""

    def test_decay_reduces_all_activations(self):
        """All region activations decay by factor."""
        brain = SuperBrain()
        # Set all activations to 0.5 first
        for region in brain.regions.values():
            region.activation = 0.5

        brain.decay_activations(decay_factor=0.9)

        for region in brain.regions.values():
            assert region.activation == pytest.approx(0.45)

    def test_decay_floor_at_zero(self):
        """Activations never go negative."""
        brain = SuperBrain()
        # Set very small activation, strong decay
        brain.regions["sensory"].activation = 0.01
        brain.decay_activations(decay_factor=0.1)

        assert brain.regions["sensory"].activation >= 0.0


class TestStatus:
    """Tests for get_status()."""

    def test_status_includes_all_regions(self):
        """Status includes each region's activity."""
        brain = SuperBrain()
        status = brain.get_status()

        assert "regions" in status
        for name in brain.regions:
            assert name in status["regions"]

    def test_status_region_fields_complete(self):
        """Each region status has all required fields."""
        brain = SuperBrain()
        status = brain.get_status()

        for _, region_status in status["regions"].items():
            assert "activation" in region_status
            assert "working_memory_len" in region_status
            assert "specialty" in region_status


class TestCompetition:
    """Tests for _competition_step() attention competition."""

    def test_competition_returns_winner_name(self):
        """Competition returns name of winning region (greedy deterministic)."""
        brain = SuperBrain(attention_temp=0.0)  # Greedy: highest activation wins
        # Set different activations
        brain.regions["sensory"].activation = 0.9
        brain.regions["predictor"].activation = 0.5
        brain.regions["planner"].activation = 0.3
        winner = brain._competition_step()
        # With greedy selection, highest activation wins
        assert winner == "sensory"

    def test_competition_returns_none_when_empty(self):
        """No regions → None winner."""
        brain = SuperBrain()
        brain.regions.clear()
        assert brain._competition_step() is None

    def test_competition_filters_low_activation(self):
        """Winner must have activation >= 0.3."""
        brain = SuperBrain()
        for region in brain.regions.values():
            region.activation = 0.1
        winner = brain._competition_step()
        assert winner is None

    def test_competition_greedy_when_temp_zero(self):
        """With attention_temp=0, highest activation wins deterministically."""
        brain = SuperBrain(attention_temp=0.0)
        brain.regions["sensory"].activation = 0.8
        brain.regions["predictor"].activation = 0.5
        # Seed numpy random for deterministic softmax alternative path
        with patch("numpy.random.choice", return_value=0):
            winner = brain._competition_step()
            # Should pick highest (sensory index 0)
            assert winner == "sensory"


class TestStagnation:
    """Tests for _check_stagnation() meta-cognition."""

    def test_stagnation_increments_when_inactive(self):
        """Counter increments when region activation low."""
        brain = SuperBrain()
        stagnation = brain._check_stagnation()
        # All regions start at 0 activation → stagnation=1
        assert all(v == 1 for v in stagnation.values())

    def test_stagnation_resets_on_activation(self):
        """Counter resets to 0 when region activates (>0.2)."""
        brain = SuperBrain()
        # Simulate recent activation
        brain.regions["sensory"].activation_history = [0.5, 0.6, 0.7]
        brain.regions["sensory"].activation = 0.6
        stagnation = brain._check_stagnation()
        assert stagnation["sensory"] == 0


class TestPathway:
    """Tests for adjust_pathway() Hebbian plasticity."""

    def test_adjust_pathway_increases_weight(self):
        """Positive delta increases pathway weight, clamped to 1.0."""
        brain = SuperBrain()
        # Find an existing pathway
        pathway = brain.pathways[0]
        initial = pathway.weight
        result = brain.adjust_pathway(pathway.source, pathway.target, delta=0.2)
        assert result is True
        assert pathway.weight == min(1.0, initial + 0.2)

    def test_adjust_pathway_decreases_weight(self):
        """Negative delta decreases weight, clamped to 0.0."""
        brain = SuperBrain()
        pathway = brain.pathways[0]
        initial = pathway.weight
        result = brain.adjust_pathway(pathway.source, pathway.target, delta=-0.3)
        assert result is True
        assert pathway.weight == max(0.0, initial - 0.3)

    def test_adjust_pathway_returns_false_if_missing(self):
        """Returns False when pathway doesn't exist."""
        brain = SuperBrain()
        result = brain.adjust_pathway("nonexistent", "fake", delta=0.1)
        assert result is False


class TestHealth:
    """Tests for get_region_health() meta-cognition."""

    def test_health_includes_all_metrics(self):
        """Health dict contains all required fields per region."""
        brain = SuperBrain()
        # Give some activation history
        brain.regions["sensory"].activation = 0.8
        brain.regions["sensory"].activation_history = [0.5, 0.6, 0.7, 0.8]
        health = brain.get_region_health()
        for _, metrics in health.items():
            assert "activation_mean" in metrics
            assert "activation_variance" in metrics
            assert "stagnation" in metrics
            assert "memory_utilization" in metrics

    def test_health_computes_mean_and_variance(self):
        """Activation mean and variance computed from history."""
        brain = SuperBrain()
        brain.regions["predictor"].activation_history = [0.2, 0.4, 0.6, 0.8]
        health = brain.get_region_health()
        predictor_health = health["predictor"]
        assert predictor_health["activation_mean"] == pytest.approx(0.5)
        # variance of [0.2, 0.4, 0.6, 0.8] = 0.05
        assert predictor_health["activation_variance"] == pytest.approx(0.05, rel=1e-2)


class TestPlanEdgeCases:
    """Edge cases for plan()."""

    def test_plan_returns_none_for_empty_options(self):
        """Empty options list returns None."""
        brain = SuperBrain()
        result = brain.plan(options=[])
        assert result is None

    def test_plan_returns_none_for_low_quality(self):
        """Best option quality < 0.5 returns None."""
        brain = SuperBrain()
        options = [{"path": "bad", "quality": 0.3}]
        result = brain.plan(options=options)
        assert result is None

    def test_plan_uses_default_options_when_none(self):
        """When options=None, generates default options."""
        brain = SuperBrain()
        result = brain.plan(goal={"target": "test"})
        assert result is not None
        assert "path" in result
        assert "quality" in result

    def test_plan_none_does_not_raise(self):
        """Goal=None doesn't crash (hashable)."""
        brain = SuperBrain()
        result = brain.plan(goal=None)
        # Should still return a plan or None, no exception
        assert result is None or isinstance(result, dict)


class TestBroadcastCompetition:
    """Tests for broadcast_global_workspace with competition_enabled=True."""

    def test_broadcast_competition_blocks_without_winner(self):
        """When competition enabled and no winner, broadcast fails."""
        brain = SuperBrain(competition_enabled=True)
        # Set all activations below threshold
        for r in brain.regions.values():
            r.activation = 0.1
        result = brain.broadcast_global_workspace({"msg": "test"})
        assert result is False

    def test_broadcast_competition_blocks_when_priority_too_low(self):
        """Even with winner, priority below winner activation blocks."""
        brain = SuperBrain(competition_enabled=True)
        brain.regions["sensory"].activation = 0.8  # High activation
        # Priority (0.3) < region activation (0.8) should fail
        result = brain.broadcast_global_workspace({"msg": "test"}, priority=0.3)
        assert result is False
