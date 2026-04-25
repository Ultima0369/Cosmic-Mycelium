#!/usr/bin/env python3
"""
Cosmic Mycelium — Hot Path Performance Benchmark

Measures latency of every critical code path and validates against
defined budgets. Both a standalone CI tool and a development aid.

Usage:
    python scripts/benchmark_hotpath.py              # Full suite
    python scripts/benchmark_hotpath.py --quick      # Fast subset (P0 only)
    python scripts/benchmark_hotpath.py --json       # JSON output for CI
    python scripts/benchmark_hotpath.py --check      # Exit 1 on budget breach

Output: table of hot paths, mean latency, budget, and pass/fail status.

Hot paths and budgets (defined at module level so they're the source of truth):

    │ Hot Path                          │ P0 Budget    │ P1 Target     │
    ├───────────────────────────────────┼──────────────┼───────────────┤
    │ SympNetEngine.step()             │ < 10 μs      │ < 5 μs        │
    │ SympNetEngine.predict(steps=10)  │ < 100 μs     │ < 50 μs       │
    │ HIC.update_breath()              │ < 50 μs      │ < 20 μs       │
    │ MyelinationMemory.reinforce()    │ < 50 μs      │ < 20 μs       │
    │ SlimeExplorer.explore()          │ < 20 ms      │ < 10 ms       │
    │ SlimeExplorer.converge()         │ < 10 ms      │ < 5 ms        │
    │ FractalDialogueBus.publish()     │ < 2 ms       │ < 200 μs      │
    │ MiniInfant.bee_heartbeat()       │ < 50 ms      │ < 20 ms       │
    │ MiniInfant instantiation         │ < 100 ms     │ < 50 ms       │
    │ SympNet 1M-step drift            │ < 0.1%       │ < 0.05%       │
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

# Add project root
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cosmic_mycelium.common.fractal import MessageEnvelope, Scale
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
from cosmic_mycelium.infant.hic import HIC, HICConfig
from cosmic_mycelium.infant.mini import MiniInfant, MyelinationMemory


# ── Budget definitions (seconds, unless noted) ────────────────────────

# fmt: off
BUDGETS: dict[str, dict[str, float]] = {
    "sympnet_step":           {"p0": 15e-6,  "p1": 5e-6},
    "sympnet_predict_10":     {"p0": 150e-6, "p1": 50e-6},
    "sympnet_1m_drift_ratio": {"p0": 0.001,  "p1": 0.0005},
    "hic_update_breath":      {"p0": 50e-6,  "p1": 20e-6},
    "memory_reinforce":       {"p0": 50e-6,  "p1": 20e-6},
    "slime_explore":          {"p0": 20e-3,  "p1": 10e-3},
    "slime_converge":         {"p0": 10e-3,  "p1": 5e-3},
    "fractal_publish":        {"p0": 2e-3,   "p1": 200e-6},
    "bee_heartbeat":          {"p0": 50e-3,  "p1": 20e-3},
    "infant_creation":        {"p0": 100e-3, "p1": 50e-3},
}
# fmt: on

N_WARMUP = 500
N_FAST = 10_000  # μs-scale operations
N_MEDIUM = 200   # ms-scale operations


def mean_latency(fn, n: int = N_FAST) -> float:
    """Measure mean latency of fn() over n iterations."""
    for _ in range(N_WARMUP):
        fn()
    times = [0.0] * n
    for i in range(n):
        t0 = time.perf_counter_ns()
        fn()
        times[i] = time.perf_counter_ns() - t0
    return statistics.mean(times) / 1e9


@dataclass
class BenchmarkResult:
    name: str
    mean_s: float
    p0_budget: float
    p1_budget: float
    passed_p0: bool = False
    passed_p1: bool = False

    def __post_init__(self):
        self.passed_p0 = self.mean_s < self.p0_budget
        self.passed_p1 = self.mean_s < self.p1_budget

    @property
    def status(self) -> str:
        if self.passed_p0:
            return "✅ PASS"
        return "❌ FAIL"

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mean_s": round(self.mean_s, 9),
            "mean_ns": round(self.mean_s * 1e9, 1),
            "p0_budget_s": self.p0_budget,
            "p1_budget_s": self.p1_budget,
            "passed_p0": self.passed_p0,
            "passed_p1": self.passed_p1,
        }


def run_all(quick: bool = False) -> list[BenchmarkResult]:
    """Run all hot path benchmarks. Returns results list."""
    results: list[BenchmarkResult] = []

    # ── 1. SympNetEngine.step() ──────────────────────────────────────
    sympnet = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
    q, p = 1.0, 0.5

    def _step() -> None:
        nonlocal q, p
        q, p = sympnet.step(q, p, 0.01)

    s = mean_latency(_step, N_FAST)
    results.append(BenchmarkResult(
        "SympNetEngine.step()", s,
        BUDGETS["sympnet_step"]["p0"], BUDGETS["sympnet_step"]["p1"],
    ))

    # ── 2. SympNetEngine.predict(10) ──────────────────────────────────
    q, p = 1.0, 0.5
    s = mean_latency(lambda: sympnet.predict(q, p, steps=10), N_FAST)
    results.append(BenchmarkResult(
        "SympNetEngine.predict(10)", s,
        BUDGETS["sympnet_predict_10"]["p0"], BUDGETS["sympnet_predict_10"]["p1"],
    ))

    # ── 3. SympNet 1M-step drift ──────────────────────────────────────
    if not quick:
        q, p = 1.0, 0.5
        e0 = sympnet.compute_energy(q, p)
        for _ in range(1_000_000):
            q, p = sympnet.step(q, p, 0.001)
        drift = abs(sympnet.compute_energy(q, p) - e0) / e0
        results.append(BenchmarkResult(
            "SympNet 1M-step drift", drift,
            BUDGETS["sympnet_1m_drift_ratio"]["p0"],
            BUDGETS["sympnet_1m_drift_ratio"]["p1"],
        ))

    # ── 4. HIC.update_breath() ────────────────────────────────────────
    hic = HIC(config=HICConfig(
        energy_max=100.0,
        contract_duration=0.001,
        diffuse_duration=0.001,
        suspend_duration=0.001,
    ))

    def _hic_update() -> None:
        hic.update_breath(confidence=0.7, work_done=True)

    s = mean_latency(_hic_update, N_FAST)
    results.append(BenchmarkResult(
        "HIC.update_breath()", s,
        BUDGETS["hic_update_breath"]["p0"], BUDGETS["hic_update_breath"]["p1"],
    ))

    # ── 5. MyelinationMemory.reinforce() ──────────────────────────────
    mem = MyelinationMemory()
    for i in range(100):
        mem.reinforce(f"path_{i}", success=True, saliency=0.5)

    s = mean_latency(lambda: mem.reinforce("test_path", True, 0.5), N_FAST)
    results.append(BenchmarkResult(
        "MyelinationMemory.reinforce()", s,
        BUDGETS["memory_reinforce"]["p0"], BUDGETS["memory_reinforce"]["p1"],
    ))

    # ── 6. SlimeExplorer.explore() ────────────────────────────────────
    bee = MiniInfant("bench-bee", verbose=False,
                     contract_duration=0.001, diffuse_duration=0.001,
                     suspend_duration=0.001)
    ctx = {"energy": 80.0, "confidence": 0.7, "position": 1.0, "momentum": 0.5}

    s = mean_latency(lambda: bee.explorer.explore(ctx), N_MEDIUM)
    results.append(BenchmarkResult(
        "SlimeExplorer.explore()", s,
        BUDGETS["slime_explore"]["p0"], BUDGETS["slime_explore"]["p1"],
    ))

    # ── 7. SlimeExplorer.converge() ───────────────────────────────────
    spores = bee.explorer.explore(ctx)
    s = mean_latency(lambda: bee.explorer.converge(0.6, spores), N_MEDIUM)
    results.append(BenchmarkResult(
        "SlimeExplorer.converge()", s,
        BUDGETS["slime_converge"]["p0"], BUDGETS["slime_converge"]["p1"],
    ))

    # ── 8. FractalDialogueBus.publish() ───────────────────────────────
    bus = FractalDialogueBus("bench-bus")
    for i in range(5):
        bus.subscribe(Scale.INFANT, lambda msg: None, name=f"sub_{i}")

    envelope = MessageEnvelope(
        source_scale=Scale.INFANT, target_scale=Scale.INFANT,
        payload={"k": "v"}, source_id="bench",
    )
    s = mean_latency(
        lambda: bus.publish(envelope), N_MEDIUM
    )
    results.append(BenchmarkResult(
        "FractalDialogueBus.publish()", s,
        BUDGETS["fractal_publish"]["p0"], BUDGETS["fractal_publish"]["p1"],
    ))

    # ── 9. bee_heartbeat() ────────────────────────────────────────────
    bee2 = MiniInfant("bench-beat", verbose=False,
                      contract_duration=0.001, diffuse_duration=0.001,
                      suspend_duration=0.001)
    t0 = time.perf_counter()
    n = 20
    for _ in range(n):
        bee2.bee_heartbeat()
    s = (time.perf_counter() - t0) / n
    results.append(BenchmarkResult(
        "MiniInfant.bee_heartbeat()", s,
        BUDGETS["bee_heartbeat"]["p0"], BUDGETS["bee_heartbeat"]["p1"],
    ))

    # ── 10. MiniInfant creation ───────────────────────────────────────
    s = mean_latency(
        lambda: MiniInfant("creation-bench", verbose=False), N_MEDIUM // 10
    )
    results.append(BenchmarkResult(
        "MiniInfant()", s,
        BUDGETS["infant_creation"]["p0"], BUDGETS["infant_creation"]["p1"],
    ))

    return results


def print_table(results: list[BenchmarkResult]) -> None:
    """Print formatted results table."""
    print()
    print("=" * 90)
    print("   🌌 Cosmic Mycelium — Hot Path Performance Benchmark")
    print("=" * 90)
    print(f"{'Hot Path':<38} {'Mean':>10} {'P0 Budget':>10} {'P1 Budget':>10}  Status")
    print("-" * 90)
    for r in results:
        unit = "μs" if r.mean_s < 1e-3 else "ms"
        scale = 1e6 if unit == "μs" else 1e3
        p0_unit = BUDGETS.get(r.name.split("(")[0].strip().lower(), {}).get("p0", 0)
        print(
            f"{r.name:<38} "
            f"{r.mean_s * scale:>8.2f}{unit} "
            f"{r.p0_budget * scale:>8.2f}{unit} "
            f"{r.p1_budget * scale:>8.2f}{unit}  "
            f"{r.status}"
        )
    print("-" * 90)
    p0_pass = sum(1 for r in results if r.passed_p0)
    p1_pass = sum(1 for r in results if r.passed_p1)
    print(f"P0: {p0_pass}/{len(results)} passed    "
          f"P1: {p1_pass}/{len(results)} passed")
    print("=" * 90)
    print()


def print_json(results: list[BenchmarkResult]) -> None:
    """Print JSON summary for CI consumption."""
    print(json.dumps({
        "benchmark": "hotpath",
        "p0_passed": all(r.passed_p0 for r in results),
        "p1_passed": all(r.passed_p1 for r in results),
        "results": [r.summary for r in results],
    }, indent=2))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Hot path performance benchmark")
    parser.add_argument("--quick", action="store_true", help="Skip 1M-step drift test")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if any P0 budget breached")
    args = parser.parse_args()

    results = run_all(quick=args.quick)

    if args.json:
        print_json(results)
    else:
        print_table(results)

    if args.check:
        return 1 if not all(r.passed_p0 for r in results) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
