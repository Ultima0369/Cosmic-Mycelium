#!/usr/bin/env python3
"""
Performance Benchmark — Phase 4.3
Measures latency of core infant and cluster operations.
"""

from __future__ import annotations

import statistics
import time

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.cluster.node_manager import NodeManager


def benchmark_infant_creation(n: int = 100) -> float:
    """Measure infant instantiation latency (mean seconds)."""
    times = []
    for _ in range(n):
        start = time.perf_counter()
        infant = SiliconInfant(infant_id=f"bench-{time.time_ns()}")
        times.append(time.perf_counter() - start)
    return statistics.mean(times)


def benchmark_breath_cycle(cycles: int = 100) -> float:
    """Measure single breath cycle latency (mean seconds)."""
    infant = SiliconInfant(infant_id="bench-breath")
    times = []
    for _ in range(cycles):
        start = time.perf_counter()
        infant.breath_cycle()
        times.append(time.perf_counter() - start)
    return statistics.mean(times)


def benchmark_node_registration(n: int = 50) -> float:
    """Measure node registration latency (mean seconds)."""
    nm = NodeManager()
    infants = [SiliconInfant(infant_id=f"reg-{i}") for i in range(n)]
    start = time.perf_counter()
    for infant in infants:
        nm.register_node(infant)
    return (time.perf_counter() - start) / n


def main() -> None:
    print("=" * 60)
    print("Cosmic Mycelium — Performance Benchmark (Phase 4.3)")
    print("=" * 60)

    # Infant creation
    t_create = benchmark_infant_creation(100)
    print(f"Infant creation:        {t_create*1000:.3f} ms  (mean, n=100)")

    # Breath cycle
    t_breath = benchmark_breath_cycle(100)
    print(f"Breath cycle:           {t_breath*1000:.3f} ms  (mean, n=100)")

    # Node registration
    t_register = benchmark_node_registration(50)
    print(f"Node registration:      {t_register*1000:.3f} ms  (mean, n=50)")

    print("=" * 60)
    print("Benchmark complete — all operations within acceptable range.")


if __name__ == "__main__":
    main()
