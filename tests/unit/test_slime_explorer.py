"""
Layer 3 — Slime Mold Explorer Tests
Tests parallel exploration, spore generation, convergence, and deterministic RNG.
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.layer_3_slime_explorer import (
    SlimeExplorer,
    Spore,
)


class TestSlimeExplorerInitialization:
    """Tests for explorer construction."""

    def test_default_num_spores(self):
        """Default is 10 spores."""
        explorer = SlimeExplorer()
        assert explorer.num_spores == 10

    def test_custom_num_spores(self):
        """Custom spore count respected."""
        explorer = SlimeExplorer(num_spores=25)
        assert explorer.num_spores == 25

    def test_spores_list_starts_empty(self):
        """spores list empty until explore() called."""
        explorer = SlimeExplorer()
        assert len(explorer.spores) == 0

    def test_pheromone_map_starts_empty(self):
        """pheromone_map starts empty."""
        explorer = SlimeExplorer()
        assert len(explorer.pheromone_map) == 0

    def test_success_history_starts_empty(self):
        """success_history starts empty."""
        explorer = SlimeExplorer()
        assert len(explorer.success_history) == 0


class TestSporeGeneration:
    """Tests for explore() spore production."""

    def test_explore_returns_correct_number_of_spores(self):
        """explore() returns exactly num_spores spores."""
        explorer = SlimeExplorer(num_spores=7)
        spores = explorer.explore({}, None)

        assert len(spores) == 7

    def test_each_spore_has_unique_id(self):
        """Spore IDs are unique within an exploration batch."""
        explorer = SlimeExplorer(num_spores=10)
        spores = explorer.explore({}, None)

        ids = [s.id for s in spores]
        assert len(set(ids)) == len(ids)

    def test_spore_energy_in_expected_range(self):
        """Spore energy is within 0.5-1.5 (RNG range)."""
        explorer = SlimeExplorer(num_spores=50)
        spores = explorer.explore({}, None)

        for spore in spores:
            assert 0.5 <= spore.energy <= 1.5

    def test_spore_path_length_in_expected_range(self):
        """Spore path length is 1-5 (RNG range)."""
        explorer = SlimeExplorer(num_spores=100)
        spores = explorer.explore({}, None)

        for spore in spores:
            assert 1 <= len(spore.path) <= 5

    def test_spore_path_actions_are_strings(self):
        """Path actions are action_N_M formatted strings."""
        explorer = SlimeExplorer(num_spores=10)
        spores = explorer.explore({}, None)

        for spore in spores:
            for action in spore.path:
                assert isinstance(action, str)
                assert action.startswith("action_")

    def test_spore_quality_in_range(self):
        """Spore quality is within [0.0, 1.0]."""
        explorer = SlimeExplorer(num_spores=30)
        spores = explorer.explore({}, None)

        for spore in spores:
            assert 0.0 <= spore.quality <= 1.0

    def test_spore_age_starts_at_zero(self):
        """New spores have age 0."""
        explorer = SlimeExplorer()
        spores = explorer.explore({}, None)
        assert all(s.age == 0 for s in spores)


class TestDeterministicRNG:
    """Tests for seeded RNG reproducibility."""

    def test_exploration_is_deterministic(self):
        """Two independent explorers produce identical spore batches."""
        explorer1 = SlimeExplorer(num_spores=10)
        explorer2 = SlimeExplorer(num_spores=10)

        spores1 = explorer1.explore({}, None)
        spores2 = explorer2.explore({}, None)

        # Compare structural properties
        assert len(spores1) == len(spores2)
        for s1, s2 in zip(spores1, spores2, strict=False):
            assert s1.id == s2.id
            assert s1.path == s2.path
            assert s1.energy == s2.energy
            assert s1.quality == s2.quality

    def test_rng_seed_is_fixed(self):
        """The internal RNG is seeded with a constant (42)."""
        # This is a white-box test ensuring the seed is deterministic
        explorer = SlimeExplorer()
        # If seed wasn't fixed, this would be flaky
        first_energy = explorer.rng.uniform(0.5, 1.5)
        # Just verifying RNG works; real determinism tested in test_exploration_is_deterministic
        assert isinstance(first_energy, float)


class TestConvergenceThreshold:
    """Tests for converge() selection logic."""

    def test_converge_returns_best_spore(self):
        """converge() returns the spore with highest quality."""
        explorer = SlimeExplorer(num_spores=5)
        # Manually set spores with known qualities
        explorer.spores = [
            Spore(id="a", quality=0.3),
            Spore(id="b", quality=0.8),
            Spore(id="c", quality=0.5),
        ]

        best = explorer.converge()

        assert best.id == "b"
        assert best.quality == 0.8

    def test_converge_respects_threshold(self):
        """converge() returns None if best quality below threshold."""
        explorer = SlimeExplorer(num_spores=3)
        explorer.spores = [
            Spore(id="a", quality=0.2),
            Spore(id="b", quality=0.3),
        ]

        best = explorer.converge(threshold=0.5)

        assert best is None

    def test_converge_empty_spores_returns_none(self):
        """converge() with no spores returns None."""
        explorer = SlimeExplorer()
        explorer.spores = []
        assert explorer.converge() is None


class TestPlan:
    """Tests for plan() orchestration."""

    def test_plan_returns_tuple(self):
        """plan() returns (best_spore_or_None, confidence)."""
        explorer = SlimeExplorer(num_spores=5)
        result = explorer.plan({"sensor": 1.0}, "test_goal")

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_plan_calls_explore_and_converge(self):
        """plan() runs explore then converge internally."""
        explorer = SlimeExplorer(num_spores=5)
        # Spy on internal methods by replacing them
        original_explore = explorer.explore
        original_converge = explorer.converge

        explore_called = []
        converge_called = []

        def spy_explore(*args, **kwargs):
            explore_called.append(True)
            return original_explore(*args, **kwargs)

        def spy_converge(*args, **kwargs):
            converge_called.append(True)
            return original_converge(*args, **kwargs)

        explorer.explore = spy_explore
        explorer.converge = spy_converge

        explorer.plan({}, "goal")

        assert len(explore_called) == 1
        assert len(converge_called) == 1

    def test_plan_confidence_scales_with_best_quality(self):
        """Confidence roughly equals best spore quality (0-1 range)."""
        explorer = SlimeExplorer(num_spores=10)
        best, confidence = explorer.plan({}, "goal")

        if best:
            assert 0.0 <= confidence <= 1.0
            assert confidence == pytest.approx(best.quality, abs=0.05)


class TestPheromoneReinforcement:
    """Tests for pheromone-based path reinforcement."""

    def test_reinforce_path_increments_pheromone(self):
        """reinforce_path adds to pheromone_map entry."""
        explorer = SlimeExplorer()
        path = ["a", "b", "c"]
        explorer.reinforce_path(path)

        path_key = "->".join(path)
        assert path_key in explorer.pheromone_map
        assert explorer.pheromone_map[path_key] > 0

    def test_reinforce_path_multiple_times_stacks(self):
        """Multiple reinforcements accumulate."""
        explorer = SlimeExplorer()
        path = ["x", "y"]
        explorer.reinforce_path(path, delta=0.5)
        explorer.reinforce_path(path, delta=0.3)

        path_key = "->".join(path)
        assert explorer.pheromone_map[path_key] == pytest.approx(0.8)

    def test_reinforce_path_decay_factor(self):
        """Reinforcement respects decay factor."""
        explorer = SlimeExplorer()
        path = ["p", "q"]
        explorer.reinforce_path(path, delta=1.0, decay=0.5)

        # Total should be 1.0 * 0.5 = 0.5
        path_key = "->".join(path)
        assert explorer.pheromone_map[path_key] == pytest.approx(0.5)
