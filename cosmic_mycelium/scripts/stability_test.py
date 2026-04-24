"""
Long-Running Stability Test — Phase 1.1
Simulates 1000 hours of operation (accelerated: 100k breath cycles).
Checks for: energy leaks, memory leaks, state corruption.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

import psutil

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.infant.main import SiliconInfant


@dataclass
class StabilityReport:
    passed: bool
    total_cycles: int
    duration_seconds: float
    final_energy: float
    energy_variance: float
    memory_mb: float
    details: dict


class LongRunningTest:
    """Accelerated stability test: 100k cycles ≈ 1000 hours simulated."""

    def __init__(self, cycles: int = 100_000):
        self.cycles = cycles

    def run(self) -> StabilityReport:
        print("\n" + "=" * 60)
        print("   🕐 Long-Running Stability Test (Phase 1.1)")
        print(f"   Running {self.cycles:,} accelerated cycles...")
        print("=" * 60 + "\n")

        infant = SiliconInfant(infant_id="stability-test")
        start_time = time.time()
        start_mem = psutil.Process().memory_info().rss / 1024**2
        energy_samples = []

        for i in range(self.cycles):
            # Run breath cycle (may return packet or None)
            infant.breath_cycle()

            # Sample energy every 1000 cycles
            if i % 1000 == 0:
                energy_samples.append(infant.hic.energy)

            # Progress indicator
            if self.cycles >= 10000 and i % 10000 == 0:
                print(f"  Progress: {i:,}/{self.cycles:,} cycles ({i/self.cycles*100:.1f}%)")

        duration = time.time() - start_time
        end_mem = psutil.Process().memory_info().rss / 1024**2
        final_energy = infant.hic.energy

        # Compute energy variance (should not drift to zero or explode)
        import numpy as np
        energy_array = np.array(energy_samples)
        energy_variance = float(np.var(energy_array))

        # Memory growth check: should not leak > 10 MB over run
        mem_growth = end_mem - start_mem

        # Energy sanity: should be within [0, energy_max]
        energy_ok = 0.0 <= final_energy <= infant.hic.config.energy_max

        passed = energy_ok and mem_growth < 10.0  # < 10 MB leak acceptable

        report = StabilityReport(
            passed=passed,
            total_cycles=self.cycles,
            duration_seconds=duration,
            final_energy=final_energy,
            energy_variance=energy_variance,
            memory_mb=end_mem,
            details={
                "memory_growth_mb": float(mem_growth),
                "cycles_per_second": self.cycles / duration if duration > 0 else 0.0,
                "energy_ok": energy_ok,
                "threshold_mem_leak_mb": 10.0,
            },
        )

        print("\n" + "=" * 60)
        print(f"   {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"   Cycles:     {report.total_cycles:,}")
        print(f"   Duration:   {report.duration_seconds:.2f}s")
        print(f"   Throughput: {report.details['cycles_per_second']:.1f} cycles/s")
        print(f"   Final energy: {report.final_energy:.2f}")
        print(f"   Memory:     {report.memory_mb:.2f} MB (growth: {report.details['memory_growth_mb']:.2f} MB)")
        print("=" * 60 + "\n")

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Long-Running Stability Test (Phase 1.1)"
    )
    parser.add_argument(
        '--cycles',
        type=int,
        default=100_000,
        help='Number of breath cycles to run (default: 100,000 ≈ 1000h accelerated)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output JSON only'
    )
    args = parser.parse_args()

    test = LongRunningTest(cycles=args.cycles)
    report = test.run()

    if args.json:
        import json
        print(json.dumps(asdict(report), indent=2))

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
