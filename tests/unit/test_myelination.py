"""
Layer 4 — Myelination Memory Tests
Tests Hebbian reinforcement, feature extraction (SHA256), trace forgetting, path recall.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.infant.core.layer_4_myelination_memory import (
    MyelinationMemory,
    MemoryTrace,
)


class TestMyelinationInitialization:
    """Tests for memory initialization."""

    def test_traces_starts_empty(self):
        """New memory has no traces."""
        mem = MyelinationMemory()
        assert len(mem.traces) == 0

    def test_feature_codebook_starts_empty(self):
        """Feature codebook starts empty."""
        mem = MyelinationMemory()
        assert len(mem.feature_codebook) == 0

    def test_default_max_traces(self):
        """Default max_traces is 10000."""
        mem = MyelinationMemory()
        assert mem.max_traces == 10000


class TestReinforcement:
    """Tests for reinforce() Hebbian learning."""

    def test_reinforce_creates_new_trace(self):
        """Reinforcing a new path creates a MemoryTrace."""
        mem = MyelinationMemory()
        path = ["action_1", "action_2"]
        mem.reinforce(path, success=True)

        path_key = "->".join(path)
        assert path_key in mem.traces
        assert mem.traces[path_key].strength > 0

    def test_reinforce_success_increases_strength(self):
        """Successful reinforcement increases strength by 1.2×."""
        mem = MyelinationMemory()
        path = ["a", "b", "c"]
        mem.reinforce(path, success=True)
        first_strength = mem.traces["->".join(path)].strength

        mem.reinforce(path, success=True)
        second_strength = mem.traces["->".join(path)].strength

        assert second_strength > first_strength
        assert pytest.approx(second_strength / first_strength, rel=1e-5) == 1.2

    def test_reinforce_failure_decreases_strength(self):
        """Failed reinforcement decreases strength by 0.8×."""
        mem = MyelinationMemory()
        path = ["x", "y"]
        mem.reinforce(path, success=True)
        first_strength = mem.traces["->".join(path)].strength

        mem.reinforce(path, success=False)
        second_strength = mem.traces["->".join(path)].strength

        assert second_strength < first_strength
        assert pytest.approx(second_strength / first_strength, rel=1e-5) == 0.8

    def test_reinforce_strength_capped_at_10(self):
        """Strength cannot exceed 10.0 upper bound."""
        mem = MyelinationMemory()
        path = ["boost"]
        mem.traces["boost"] = MemoryTrace(
            path="boost",
            strength=9.5,
            last_accessed=0.0,
            access_count=1,
        )
        mem.reinforce(path, success=True)  # 9.5 * 1.2 = 11.4 → clamp to 10

        assert mem.traces["boost"].strength == 10.0

    def test_reinforce_strength_floors_at_0_1(self):
        """Strength cannot go below 0.1 lower bound."""
        mem = MyelinationMemory()
        path = ["weaken"]
        mem.traces["weaken"] = MemoryTrace(
            path="weaken",
            strength=0.15,
            last_accessed=0.0,
            access_count=1,
        )
        mem.reinforce(path, success=False)  # 0.15 * 0.8 = 0.12

        assert mem.traces["weaken"].strength == pytest.approx(0.12)

        mem.reinforce(path, success=False)  # 0.12 * 0.8 = 0.096 → clamp to 0.1
        assert mem.traces["weaken"].strength == 0.1


class TestFeatureExtraction:
    """Tests for extract_feature() SHA256 hashing."""

    def test_extract_feature_returns_8_char_string(self):
        """Feature code is exactly 8 hexadecimal characters."""
        mem = MyelinationMemory()
        feature = mem.extract_feature({"sensor": 1.0, "temp": 25.0})
        assert len(feature) == 8

    def test_extract_feature_is_deterministic(self):
        """Same data produces identical feature code."""
        mem = MyelinationMemory()
        data = {"a": 1, "b": 2}
        f1 = mem.extract_feature(data)
        f2 = mem.extract_feature(data)
        assert f1 == f2

    def test_extract_feature_differentiates_data(self):
        """Different data produces different feature codes (collision-free for test set)."""
        mem = MyelinationMemory()
        f1 = mem.extract_feature({"x": 1})
        f2 = mem.extract_feature({"x": 2})
        assert f1 != f2

    def test_extract_feature_increments_codebook(self):
        """feature_codebook counter increments on each extraction."""
        mem = MyelinationMemory()
        mem.extract_feature({"a": 1})
        mem.extract_feature({"a": 1})  # Same data → same code
        mem.extract_feature({"a": 2})  # Different data → different code

        codes = mem.feature_codebook
        assert len(codes) == 2  # Two distinct codes
        assert all(count >= 1 for count in codes.values())

    def test_extract_feature_handles_nested_structures(self):
        """Feature extraction handles nested dicts via JSON serialization."""
        mem = MyelinationMemory()
        data = {"nested": {"a": 1, "b": [2, 3]}, "flat": 4}
        feature = mem.extract_feature(data)
        assert len(feature) == 8
        # Verify it's hex
        assert all(c in "0123456789abcdef" for c in feature)


class TestRecall:
    """Tests for recall() path retrieval."""

    def test_recall_returns_trace_for_existing_path(self):
        """Existing strong trace is returned."""
        mem = MyelinationMemory()
        path = ["a", "b"]
        mem.traces["a->b"] = MemoryTrace(
            path="a->b",
            strength=5.0,
            last_accessed=0.0,
            access_count=1,
        )

        trace = mem.recall(path)
        assert trace is not None
        assert trace.strength == 5.0

    def test_recall_returns_none_for_weak_trace(self):
        """Trace below min_strength returns None."""
        mem = MyelinationMemory()
        path = ["weak"]
        mem.traces["weak"] = MemoryTrace(
            path="weak",
            strength=0.3,
            last_accessed=0.0,
            access_count=1,
        )

        trace = mem.recall(path, min_strength=0.5)
        assert trace is None

    def test_recall_returns_none_for_missing_path(self):
        """Unknown path returns None."""
        mem = MyelinationMemory()
        trace = mem.recall(["nonexistent"])
        assert trace is None

    def test_recall_increments_access_count(self):
        """Successful recall increments access_count."""
        mem = MyelinationMemory()
        path = ["tracked"]
        mem.traces["tracked"] = MemoryTrace(
            path="tracked",
            strength=2.0,
            last_accessed=0.0,
            access_count=1,
        )

        mem.recall(path)
        assert mem.traces["tracked"].access_count == 2

    def test_recall_updates_last_accessed(self):
        """recall() updates last_accessed to current time."""
        import time as t
        mem = MyelinationMemory()
        path = ["recent"]
        old_time = t.time() - 1000
        mem.traces["recent"] = MemoryTrace(
            path="recent",
            strength=2.0,
            last_accessed=old_time,
            access_count=1,
        )

        mem.recall(path)
        assert mem.traces["recent"].last_accessed > old_time


class TestForgetting:
    """Tests for forget() eviction of weak/old traces."""

    def test_forget_removes_weakest_traces_when_over_capacity(self):
        """When trace count > max_traces, weakest traces are removed."""
        mem = MyelinationMemory(max_traces=3)
        # Add 5 traces with varying strength
        mem.traces["a"] = MemoryTrace(path="a", strength=1.0, last_accessed=0.0, access_count=1)
        mem.traces["b"] = MemoryTrace(path="b", strength=2.0, last_accessed=0.0, access_count=1)
        mem.traces["c"] = MemoryTrace(path="c", strength=0.5, last_accessed=0.0, access_count=1)
        mem.traces["d"] = MemoryTrace(path="d", strength=1.5, last_accessed=0.0, access_count=1)
        mem.traces["e"] = MemoryTrace(path="e", strength=0.3, last_accessed=0.0, access_count=1)

        # Forgetting should remove weakest (e:0.3, c:0.5) first
        mem.forget()

        assert len(mem.traces) == 3
        # Strongest 3 survive
        assert "b" in mem.traces  # 2.0
        assert "d" in mem.traces  # 1.5
        assert "a" in mem.traces  # 1.0

    def test_forget_does_nothing_under_capacity(self):
        """forget() is a no-op when under max_traces."""
        mem = MyelinationMemory(max_traces=10)
        mem.reinforce(["a", "b"])
        mem.reinforce(["c", "d"])

        mem.forget()
        assert len(mem.traces) == 2  # No eviction

    def test_forget_removes_oldest_when_strength_tied(self):
        """When strengths equal, oldest (last_accessed) is evicted first."""
        import time
        mem = MyelinationMemory(max_traces=1)  # capacity 1, have 2 -> evict one
        now = time.time()
        mem.traces["old"] = MemoryTrace(
            path="old",
            strength=1.0,
            last_accessed=now - 100,
            access_count=1,
        )
        mem.traces["new"] = MemoryTrace(
            path="new",
            strength=1.0,
            last_accessed=now,
            access_count=1,
        )

        mem.forget()

        assert "new" in mem.traces  # Newer survives
        assert "old" not in mem.traces


class TestBestPaths:
    """Tests for get_best_paths()."""

    def test_get_best_paths_returns_sorted_by_strength(self):
        """Best paths are ordered descending by strength."""
        mem = MyelinationMemory()
        mem.traces["low"] = MemoryTrace(path="low", strength=1.0, last_accessed=0.0, access_count=1)
        mem.traces["high"] = MemoryTrace(path="high", strength=5.0, last_accessed=0.0, access_count=1)
        mem.traces["mid"] = MemoryTrace(path="mid", strength=3.0, last_accessed=0.0, access_count=1)

        best = mem.get_best_paths(3)

        assert best[0][0] == "high"
        assert best[1][0] == "mid"
        assert best[2][0] == "low"

    def test_get_best_paths_respects_n_limit(self):
        """get_best_paths(n) returns at most n results."""
        mem = MyelinationMemory()
        for i in range(10):
            mem.traces[f"path_{i}"] = MemoryTrace(
                path=f"path_{i}",
                strength=float(i),
                last_accessed=0.0,
                access_count=1,
            )

        best = mem.get_best_paths(3)
        assert len(best) == 3


class TestCoverage:
    """Tests for get_coverage_ratio()."""

    def test_coverage_zero_when_empty(self):
        """Coverage is 0.0 when no traces."""
        mem = MyelinationMemory()
        assert mem.get_coverage_ratio() == 0.0

    def test_coverage_ratio_meaningful(self):
        """Coverage returns a float in [0, 1] range."""
        mem = MyelinationMemory()
        mem.reinforce(["a", "b"])
        coverage = mem.get_coverage_ratio()
        assert 0.0 <= coverage <= 1.0
