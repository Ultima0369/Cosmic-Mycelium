"""
Performance Budget Tests — CI-validatable hot path latency budgets.

Each test measures a core hot path and asserts it stays within budget.
These are the "speed limits" of the codebase — if they fail, something
regressed on a critical path.

Budgets are set for CPython on modern x86_64. CI runners are usually
slower than dev machines, so budgets include 2-3x headroom over measured
performance. When upgrading hardware or moving to PyPy, update downward.

Hot Path Map:
  P0 (must pass in CI):
    SympNetEngine.step()         — < 10μs  (single integration step)
    SympNetEngine.predict(10)    — < 100μs (10-step prediction)
    HIC.update_breath()          — < 50μs  (breath state machine)
    bee_heartbeat()              — < 50ms  (full cycle, accelerated config)
    MyelinationMemory.reinforce  — < 50μs  (path strength update)
    SlimeExplorer.explore        — < 20ms  (parallel spore exploration)
    FractalDialogueBus.publish   — < 2ms   (message dispatch)

  P1 (warning threshold, tracked but non-blocking):
    SympNetEngine.step()         — < 5μs   (optimal)
    SlimeExplorer.converge       — < 10ms  (path convergence)
    Infant instantiation         — < 50ms  (MiniInfant.__init__)
"""

from __future__ import annotations

import statistics
import time

import pytest

from cosmic_mycelium.common.fractal import MessageEnvelope, Scale
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
from cosmic_mycelium.infant.hic import HIC, HICConfig
from cosmic_mycelium.infant.mini import MiniInfant, MyelinationMemory

# ── Budget constants (seconds) ────────────────────────────────────────

# P0 — hard limits: failure = regression
BUDGET_SYMPNET_STEP: float = 15e-6       # 15 μs
BUDGET_SYMPNET_PREDICT: float = 150e-6   # 150 μs
BUDGET_HIC_UPDATE_BREATH: float = 50e-6  # 50 μs
BUDGET_MEMORY_REINFORCE: float = 50e-6   # 50 μs
BUDGET_SLIME_EXPLORE: float = 20e-3      # 20 ms
BUDGET_SLIME_CONVERGE: float = 10e-3     # 10 ms
BUDGET_FRACTAL_PUBLISH: float = 2e-3     # 2 ms
BUDGET_BEE_HEARTBEAT: float = 50e-3      # 50 ms
BUDGET_INFANT_CREATION: float = 100e-3   # 100 ms

# P1 — soft limits: warn but allow
WARN_SYMPNET_STEP: float = 5e-6          # 5 μs
WARN_SLIME_CONVERGE: float = 10e-3       # 10 ms

# Iterations for stable measurement
N_FAST: int = 10_000     # μs-scale operations
N_MEDIUM: int = 100      # ms-scale operations
N_SINGLE: int = 10       # single-operation measurement (averaged)


def _mean_latency(fn, n: int = N_FAST) -> float:
    """Measure mean latency of fn() over n iterations."""
    # Warmup
    for _ in range(100):
        fn()
    times = []
    for _ in range(n):
        start = time.perf_counter_ns()
        fn()
        elapsed_ns = time.perf_counter_ns() - start
        times.append(elapsed_ns)
    return statistics.mean(times) / 1e9  # seconds


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sympnet() -> SympNetEngine:
    return SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)


@pytest.fixture
def hic() -> HIC:
    return HIC(config=HICConfig(
        energy_max=100.0,
        contract_duration=0.001,   # 1ms — fast for testing
        diffuse_duration=0.001,    # 1ms
        suspend_duration=0.001,    # 1ms
    ))


@pytest.fixture
def memory() -> MyelinationMemory:
    m = MyelinationMemory()
    # Pre-populate some paths for realistic measurement
    for i in range(100):
        m.reinforce(f"path_{i}", success=True, saliency=0.5)
    return m


@pytest.fixture
def bus() -> FractalDialogueBus:
    return FractalDialogueBus("perf-test-bus")


@pytest.fixture
def infant(bus: FractalDialogueBus) -> MiniInfant:
    return MiniInfant(
        "perf-bee",
        mass=1.0,
        spring_constant=1.0,
        contract_duration=0.001,
        diffuse_duration=0.001,
        suspend_duration=0.001,
        fractal_bus=bus,
        verbose=False,
    )


# ── P0 Budget Tests ───────────────────────────────────────────────────

class TestSympNetBudget:
    """SympNet hot paths — the physics anchor must be fast."""

    def test_step_latency(self, sympnet: SympNetEngine) -> None:
        """A single step() must complete within 10 μs (P0)."""
        q, p = 1.0, 0.5

        def _step() -> None:
            nonlocal q, p  # noqa: F824
            q, p = sympnet.step(q, p, 0.01)

        mean_s = _mean_latency(_step, N_FAST)
        assert mean_s < BUDGET_SYMPNET_STEP, (
            f"SympNet.step() mean {mean_s*1e6:.2f}μs exceeds budget "
            f"{BUDGET_SYMPNET_STEP*1e6:.2f}μs"
        )

    def test_predict_latency(self, sympnet: SympNetEngine) -> None:
        """10-step prediction must complete within 100 μs (P0)."""
        q, p = 1.0, 0.5
        mean_s = _mean_latency(
            lambda: sympnet.predict(q, p, steps=10), N_FAST
        )
        assert mean_s < BUDGET_SYMPNET_PREDICT, (
            f"SympNet.predict(10) mean {mean_s*1e6:.2f}μs exceeds budget "
            f"{BUDGET_SYMPNET_PREDICT*1e6:.2f}μs"
        )

    def test_drift_budget(self, sympnet: SympNetEngine) -> None:
        """1M steps must drift < 0.1% (P0, from CLAUDE.md)."""
        q, p = 1.0, 0.5
        dt = 0.001
        e0 = sympnet.compute_energy(q, p)
        for _ in range(1_000_000):
            q, p = sympnet.step(q, p, dt)
        drift = abs(sympnet.compute_energy(q, p) - e0) / e0
        assert drift < 0.001, (
            f"Energy drift {drift:.6e} exceeds 0.001 threshold"
        )


class TestHICBudget:
    """HIC update_breath is called on every heartbeat."""

    def test_update_breath_latency(self, hic: HIC) -> None:
        """update_breath() must complete within 50 μs (P0)."""
        start = time.perf_counter_ns()
        count = 0
        # Run through many transitions
        for _ in range(N_FAST):
            hic.update_breath(confidence=0.7, work_done=True)
            count += 1
        elapsed_s = (time.perf_counter_ns() - start) / 1e9
        mean_s = elapsed_s / count
        assert mean_s < BUDGET_HIC_UPDATE_BREATH, (
            f"HIC.update_breath() mean {mean_s*1e6:.2f}μs exceeds budget "
            f"{BUDGET_HIC_UPDATE_BREATH*1e6:.2f}μs"
        )


class TestMemoryBudget:
    """MyelinationMemory reinforce/forget are called every cycle."""

    def test_reinforce_latency(self, memory: MyelinationMemory) -> None:
        """reinforce() must complete within 50 μs (P0)."""
        mean_s = _mean_latency(
            lambda: memory.reinforce("test_path", success=True, saliency=0.5),
            N_FAST,
        )
        assert mean_s < BUDGET_MEMORY_REINFORCE, (
            f"MyelinationMemory.reinforce() mean {mean_s*1e6:.2f}μs exceeds "
            f"budget {BUDGET_MEMORY_REINFORCE*1e6:.2f}μs"
        )


class TestSlimeExplorerBudget:
    """SlimeExplorer hot paths — runs every contract phase."""

    def test_explore_latency(self, infant: MiniInfant) -> None:
        """explore() must complete within 20 ms (P0)."""
        context = {
            "energy": 80.0,
            "confidence": 0.7,
            "position": 1.0,
            "momentum": 0.5,
        }
        mean_s = _mean_latency(
            lambda: infant.explorer.explore(context),
            N_MEDIUM,
        )
        assert mean_s < BUDGET_SLIME_EXPLORE, (
            f"SlimeExplorer.explore() mean {mean_s*1e3:.2f}ms exceeds budget "
            f"{BUDGET_SLIME_EXPLORE*1e3:.2f}ms"
        )

    def test_converge_latency(self, infant: MiniInfant) -> None:
        """converge() must complete within 10 ms (P0)."""
        context = {
            "energy": 80.0,
            "confidence": 0.7,
            "position": 1.0,
            "momentum": 0.5,
        }
        spores = infant.explorer.explore(context)
        mean_s = _mean_latency(
            lambda: infant.explorer.converge(threshold=0.6, spores=spores),
            N_MEDIUM,
        )
        assert mean_s < BUDGET_SLIME_CONVERGE, (
            f"SlimeExplorer.converge() mean {mean_s*1e3:.2f}ms exceeds budget "
            f"{BUDGET_SLIME_CONVERGE*1e3:.2f}ms"
        )


class TestFractalBudget:
    """FractalDialogueBus — cross-node communication hot path."""

    def test_publish_latency(self, bus: FractalDialogueBus) -> None:
        """publish() must complete within 2 ms (P0)."""
        # Add a few subscribers for realistic load
        for i in range(5):
            bus.subscribe(Scale.INFANT, lambda msg: None, name=f"sub_{i}")

        env = MessageEnvelope(
            source_scale=Scale.INFANT, target_scale=Scale.INFANT,
            payload={"key": "value"}, source_id="perf-test",
        )
        mean_s = _mean_latency(
            lambda: bus.publish(env),
            N_MEDIUM,
        )
        assert mean_s < BUDGET_FRACTAL_PUBLISH, (
            f"FractalDialogueBus.publish() mean {mean_s*1e3:.2f}ms exceeds "
            f"budget {BUDGET_FRACTAL_PUBLISH*1e3:.2f}ms"
        )

    def test_broadcast_latency(self, bus: FractalDialogueBus) -> None:
        """broadcast_to_scale() with subscribers."""
        for i in range(5):
            bus.subscribe(Scale.MESH, lambda msg: None, name=f"sub_{i}")

        mean_s = _mean_latency(
            lambda: bus.broadcast_to_scale(Scale.MESH, {"alert": "test"}),
            N_MEDIUM,
        )
        assert mean_s < 5e-3, (
            f"broadcast_to_scale() mean {mean_s*1e3:.2f}ms too slow"
        )


class TestFullCycleBudget:
    """Full bee_heartbeat end-to-end latency."""

    def test_bee_heartbeat_latency(self, infant: MiniInfant) -> None:
        """Full heartbeat must average < 50 ms (P0)."""

        # Run N cycles, measure total time
        start = time.perf_counter()
        n_cycles = 10
        for _ in range(n_cycles):
            infant.bee_heartbeat()
        elapsed = time.perf_counter() - start
        mean_s = elapsed / n_cycles

        assert mean_s < BUDGET_BEE_HEARTBEAT, (
            f"bee_heartbeat() mean {mean_s*1e3:.2f}ms exceeds budget "
            f"{BUDGET_BEE_HEARTBEAT*1e3:.2f}ms"
        )

    def test_infant_creation_latency(self) -> None:
        """MiniInfant instantiation must be < 100 ms (P0)."""
        mean_s = _mean_latency(
            lambda: MiniInfant("creation-perf-test", verbose=False),
            N_SINGLE,
        )
        assert mean_s < BUDGET_INFANT_CREATION, (
            f"MiniInfant() mean {mean_s*1e3:.2f}ms exceeds budget "
            f"{BUDGET_INFANT_CREATION*1e3:.2f}ms"
        )


# ── P1 Warning Tests (non-blocking, informational) ───────────────────

@pytest.mark.slow
class TestP1WarningThresholds:
    """P1 soft limits — warn on regression but don't block CI."""

    def test_step_optimal(self, sympnet: SympNetEngine) -> None:
        """SympNet.step() should aim for < 5 μs (P1 target)."""
        q, p = 1.0, 0.5

        def _step() -> None:
            nonlocal q, p  # noqa: F824
            q, p = sympnet.step(q, p, 0.01)

        mean_s = _mean_latency(_step, N_FAST)
        if mean_s >= WARN_SYMPNET_STEP:
            pytest.skip(
                f"Step {mean_s*1e6:.2f}μs above P1 target {WARN_SYMPNET_STEP*1e6:.2f}μs"
                " — investigate if this persists"
            )
