"""
Layer 5 — SuperBrain Tests
Tests multi-region processing, attention competition, global workspace, decay.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.infant.core.layer_5_superbrain import (
    SuperBrain,
    BrainRegion,
    RegionConfig,
    RegionActivity,
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
        """Plan quality is a float 0–1."""
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

        for region_name, region_status in status["regions"].items():
            assert "activation" in region_status
            assert "working_memory_len" in region_status
            assert "specialty" in region_status
