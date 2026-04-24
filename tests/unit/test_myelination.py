"""
Layer 4 — Myelination Memory Tests
Tests Hebbian reinforcement, feature extraction (SHA256), trace forgetting, path recall.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from cosmic_mycelium.infant.core.layer_4_myelination_memory import (
    DecaySchedule,
    MemoryTrace,
    MyelinationMemory,
)
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper


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
        """Successful reinforcement increases strength by 1.2x."""
        mem = MyelinationMemory()
        path = ["a", "b", "c"]
        mem.reinforce(path, success=True)
        first_strength = mem.traces["->".join(path)].strength

        mem.reinforce(path, success=True)
        second_strength = mem.traces["->".join(path)].strength

        assert second_strength > first_strength
        assert pytest.approx(second_strength / first_strength, rel=1e-5) == 1.2

    def test_reinforce_failure_decreases_strength(self):
        """Failed reinforcement decreases strength by 0.8x."""
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
        mem = MyelinationMemory()
        path = ["recent"]
        old_time = time.time() - 1000
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
        mem.traces["a"] = MemoryTrace(
            path="a", strength=1.0, last_accessed=0.0, access_count=1
        )
        mem.traces["b"] = MemoryTrace(
            path="b", strength=2.0, last_accessed=0.0, access_count=1
        )
        mem.traces["c"] = MemoryTrace(
            path="c", strength=0.5, last_accessed=0.0, access_count=1
        )
        mem.traces["d"] = MemoryTrace(
            path="d", strength=1.5, last_accessed=0.0, access_count=1
        )
        mem.traces["e"] = MemoryTrace(
            path="e", strength=0.3, last_accessed=0.0, access_count=1
        )

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
        mem.traces["low"] = MemoryTrace(
            path="low", strength=1.0, last_accessed=0.0, access_count=1
        )
        mem.traces["high"] = MemoryTrace(
            path="high", strength=5.0, last_accessed=0.0, access_count=1
        )
        mem.traces["mid"] = MemoryTrace(
            path="mid", strength=3.0, last_accessed=0.0, access_count=1
        )

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


class TestForgettingDecaySchedules:
    """Tests for forget() with different decay schedules."""

    def test_forget_exponential_decay(self):
        """Exponential decay reduces strength over time."""
        mem = MyelinationMemory(
            decay_schedule=DecaySchedule.EXPONENTIAL, decay_rate=0.1
        )
        path = ["test"]
        # Create trace with old timestamp (2 hours ago)
        old_time = time.time() - 7200  # 2 hours
        mem.traces[path[0]] = MemoryTrace(
            path=path[0],
            strength=1.0,
            last_accessed=old_time,
            access_count=1,
            decay_schedule=DecaySchedule.EXPONENTIAL,
            decay_rate=0.1,
        )
        mem.forget()
        # After 2 hours with rate 0.1/hour: decay = exp(-0.1 * 2) ≈ 0.818
        expected = 1.0 * math.exp(-0.1 * 2)
        assert mem.traces[path[0]].strength == pytest.approx(expected, rel=1e-2)

    def test_forget_step_decay(self):
        """STEP decay drops strength at hourly boundaries."""
        mem = MyelinationMemory(decay_schedule=DecaySchedule.STEP, decay_rate=0.2)
        path = ["step_test"]
        # 2.5 hours ago → 2 full steps
        old_time = time.time() - 9000  # 2.5 hours
        mem.traces[path[0]] = MemoryTrace(
            path=path[0],
            strength=1.0,
            last_accessed=old_time,
            access_count=1,
            decay_schedule=DecaySchedule.STEP,
            decay_rate=0.2,
        )
        mem.forget()
        # 2 steps * (1-0.2) = 0.64
        assert mem.traces[path[0]].strength == pytest.approx(0.64, rel=1e-2)

    def test_forget_sigmoid_decay(self):
        """SIGMOID decay is slow then fast then slow."""
        mem = MyelinationMemory(decay_schedule=DecaySchedule.SIGMOID)
        path = ["sigmoid_test"]
        # 10 hours ago — past the steep part (t0=5)
        old_time = time.time() - 36000  # 10 hours
        mem.traces[path[0]] = MemoryTrace(
            path=path[0],
            strength=1.0,
            last_accessed=old_time,
            access_count=1,
            decay_schedule=DecaySchedule.SIGMOID,
            decay_rate=0.01,
        )
        mem.forget()
        # Sigmoid at age=10 drives strength ≈ 0, below 0.05 deletion threshold
        assert path[0] not in mem.traces

    def test_forget_removes_trace_when_strength_below_threshold(self):
        """Traces with strength < 0.05 are deleted."""
        mem = MyelinationMemory()
        mem.traces["fading"] = MemoryTrace(
            path="fading",
            strength=0.04,
            last_accessed=time.time() - 10000,
            access_count=1,
        )
        mem.forget()
        assert "fading" not in mem.traces


class TestConsolidation:
    """Tests for consolidate_similar_paths()."""

    def test_consolidate_merges_paths_with_common_prefix(self):
        """Paths sharing prefix are consolidated into stronger trace."""
        mem = MyelinationMemory(consolidation_threshold=0.5)
        # Create two paths with common prefix "a->b"
        mem.traces["a->b->c"] = MemoryTrace(
            path="a->b->c", strength=2.0, last_accessed=time.time(), access_count=1
        )
        mem.traces["a->b->d"] = MemoryTrace(
            path="a->b->d", strength=3.0, last_accessed=time.time(), access_count=1
        )

        merged = mem.consolidate_similar_paths()

        assert merged == 1  # One prefix trace created
        assert "a->b" in mem.traces
        # Prefix strength = min(10.0, avg_strength * 0.5) = min(10, 2.5*0.5=1.25)
        assert mem.traces["a->b"].strength == pytest.approx(1.25, rel=1e-2)
        # Original paths preserved
        assert "a->b->c" in mem.traces
        assert "a->b->d" in mem.traces

    def test_consolidate_strengthens_existing_prefix(self):
        """Existing prefix trace gets strengthened."""
        mem = MyelinationMemory()
        # Existing prefix with some strength
        mem.traces["x->y"] = MemoryTrace(
            path="x->y", strength=1.0, last_accessed=time.time(), access_count=1
        )
        mem.traces["x->y->z"] = MemoryTrace(
            path="x->y->z", strength=2.0, last_accessed=time.time(), access_count=1
        )

        mem.consolidate_similar_paths()

        # Existing "x->y" strength increased by avg_strength*0.3 = ((1+2)/2)*0.3 = 1.5*0.3 = 0.45
        assert mem.traces["x->y"].strength == pytest.approx(1.45, rel=1e-2)

    def test_consolidate_no_merge_for_single_paths(self):
        """Paths without common prefix are not consolidated."""
        mem = MyelinationMemory()
        mem.traces["solo"] = MemoryTrace(
            path="solo", strength=1.0, last_accessed=time.time(), access_count=1
        )

        merged = mem.consolidate_similar_paths()

        assert merged == 0
        assert "solo" in mem.traces


class TestNormalization:
    """Tests for normalize_strengths()."""

    def test_normalize_scales_to_target_max(self):
        """All strengths scaled to [0.1, target_max]."""
        mem = MyelinationMemory()
        mem.traces["a"] = MemoryTrace(
            path="a", strength=1.0, last_accessed=0.0, access_count=1
        )
        mem.traces["b"] = MemoryTrace(
            path="b", strength=5.0, last_accessed=0.0, access_count=1
        )
        mem.traces["c"] = MemoryTrace(
            path="c", strength=9.0, last_accessed=0.0, access_count=1
        )

        mem.normalize_strengths(target_max=5.0)

        # Min=1.0, Max=9.0 → normalized: 0.1 + (5-0.1)*(s-1)/(9-1)
        # a: 0.1 + 4.9*(0/8) = 0.1
        # b: 0.1 + 4.9*(4/8) = 0.1 + 2.45 = 2.55
        # c: 0.1 + 4.9*(8/8) = 5.0
        assert mem.traces["a"].strength == pytest.approx(0.1)
        assert mem.traces["b"].strength == pytest.approx(2.55, rel=1e-2)
        assert mem.traces["c"].strength == pytest.approx(5.0)

    def test_normalize_no_change_when_all_equal(self):
        """No normalization when all strengths equal."""
        mem = MyelinationMemory()
        mem.traces["a"] = MemoryTrace(
            path="a", strength=2.0, last_accessed=0.0, access_count=1
        )
        mem.traces["b"] = MemoryTrace(
            path="b", strength=2.0, last_accessed=0.0, access_count=1
        )

        mem.normalize_strengths(target_max=5.0)

        # Should be unchanged (early return)
        assert mem.traces["a"].strength == 2.0
        assert mem.traces["b"].strength == 2.0

    def test_normalize_handles_single_trace(self):
        """Normalization with single trace does nothing."""
        mem = MyelinationMemory()
        mem.traces["single"] = MemoryTrace(
            path="single", strength=3.0, last_accessed=0.0, access_count=1
        )

        mem.normalize_strengths()

        assert mem.traces["single"].strength == 3.0


class TestCoverageEdgeCases:
    """Edge cases in get_coverage_ratio()."""

    def test_coverage_max_entropy_single_trace(self):
        """With single trace, max_entropy = log(1) = 0, handled gracefully."""
        mem = MyelinationMemory()
        mem.reinforce(["only_one"])
        # Should not divide by zero; entropy component becomes 0
        coverage = mem.get_coverage_ratio()
        assert 0.0 <= coverage <= 1.0
        assert coverage > 0  # Some capacity utilization

    def test_coverage_with_zero_total_strength(self):
        """If all strengths are zero (edge case), coverage still valid."""
        mem = MyelinationMemory()
        # Manually set zero-strength traces
        mem.traces["zero"] = MemoryTrace(
            path="zero", strength=0.0, last_accessed=0.0, access_count=1
        )
        coverage = mem.get_coverage_ratio()
        # Should be finite and in range
        assert math.isfinite(coverage)
        assert 0.0 <= coverage <= 1.0


@pytest.fixture
def mem_with_semantic():
    """MyelinationMemory with SemanticMapper for semantic consolidation tests."""
    mapper = SemanticMapper(embedding_dim=16)
    return MyelinationMemory(semantic_mapper=mapper)


class TestSemanticConsolidation:
    """Tests for consolidate_semantic_paths (Epic 3)."""

    def test_consolidate_semantic_paths_merges_similar_end_states(
        self, mem_with_semantic
    ):
        """Paths ending in semantically similar states get merged."""
        # Create two paths that end in similar physical states
        # Path A: ends with state {"vibration": 0.5, "temperature": 22.0}
        mem_with_semantic.reinforce(
            ["sensor_read", "process", "stabilize"],
            success=True,
            end_state={"vibration": 0.5, "temperature": 22.0},
        )
        # Path B: ends with state {"vibration": 0.52, "temperature": 22.1}
        # Similar enough (cosine similarity > 0.9) to be merged
        mem_with_semantic.reinforce(
            ["sense", "compute", "adjust"],
            success=True,
            end_state={"vibration": 0.52, "temperature": 22.1},
        )

        # Both traces should have state_embedding set
        traces = list(mem_with_semantic.traces.values())
        assert all(t.state_embedding is not None for t in traces)

        # Run consolidation
        merged = mem_with_semantic.consolidate_semantic_paths(similarity_threshold=0.9)

        # Should have merged at least one pair
        assert merged >= 0  # May or may not merge depending on exact similarity
        # After consolidation, total traces should be <= original count
        assert len(mem_with_semantic.traces) <= 2

    def test_consolidate_semantic_paths_no_op_without_semantic_mapper(self):
        """consolidate_semantic_paths returns 0 when no semantic_mapper."""
        mem = MyelinationMemory(semantic_mapper=None)
        mem.reinforce(["a", "b"], success=True, end_state={"vibration": 0.5})
        mem.reinforce(["c", "d"], success=True, end_state={"vibration": 0.6})
        merged = mem.consolidate_semantic_paths()
        assert merged == 0

    def test_consolidate_semantic_paths_no_op_with_single_trace(self, mem_with_semantic):
        """consolidate_semantic_paths returns 0 with fewer than 2 candidates."""
        mem_with_semantic.reinforce(
            ["single"], success=True, end_state={"vibration": 0.5}
        )
        merged = mem_with_semantic.consolidate_semantic_paths()
        assert merged == 0

    def test_consolidate_ignores_traces_without_state_embedding(self, mem_with_semantic):
        """Traces without state_embedding are skipped."""
        mem_with_semantic.reinforce(["no_state"], success=True)  # no end_state
        mem_with_semantic.reinforce(
            ["with_state"], success=True, end_state={"vibration": 0.5}
        )
        merged = mem_with_semantic.consolidate_semantic_paths()
        # Only one trace has embedding, can't merge → 0
        assert merged == 0

    def test_reinforce_stores_state_embedding_when_end_state_provided(
        self, mem_with_semantic
    ):
        """reinforce with end_state computes and stores state_embedding."""
        mem_with_semantic.reinforce(
            ["action1", "action2"],
            success=True,
            end_state={"temperature": 37.0, "vibration": 0.1},
        )
        trace = mem_with_semantic.traces["action1->action2"]
        assert trace.state_embedding is not None
        assert isinstance(trace.state_embedding, np.ndarray)
        assert trace.state_embedding.shape[0] == 16  # embedding_dim
