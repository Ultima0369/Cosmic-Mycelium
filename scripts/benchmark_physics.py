#!/usr/bin/env python3
"""
Cosmic Mycelium — Physics Benchmark Suite
Validates the "Physical Anchor" integrity of SympNet engine.

This is the ultimate truth test: energy drift must stay below 0.1%.
Run with: python -m cosmic_mycelium.tests.physics.benchmark_physics
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

import numpy as np

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine


@dataclass
class PhysicsReport:
    """Results of a physics validation run."""
    test_name: str
    passed: bool
    details: dict
    timestamp: float = 0.0

    def to_dict(self):
        return asdict(self)


class PhysicsBenchmark:
    """Runs the factory-grade physics validation suite."""

    def __init__(self, output_dir: Path = Path("reports")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[PhysicsReport] = []

    def run_all(self) -> bool:
        """Run all physics tests. Returns True if all pass."""
        print("\n" + "=" * 60)
        print("   ⚛️  Cosmic Mycelium — Physics Validation Suite")
        print("=" * 60 + "\n")

        tests = [
            ("Energy Conservation (Simple Harmonic)", self.test_energy_conservation_sho),
            ("Energy Conservation (Damped)", self.test_energy_conservation_damped),
            ("Symplectic Integrator Order", self.test_symplectic_order),
            ("Long-term Drift Accumulation", self.test_drift_accumulation),
            ("Numerical Stability (Large Steps)", self.test_numerical_stability),
            ("Phase Space Volume Preservation", self.test_phase_space_preservation),
        ]

        all_passed = True
        for name, test_fn in tests:
            print(f"Running: {name}...", end=" ", flush=True)
            start = time.time()
            passed, details = test_fn()
            elapsed = time.time() - start

            result = PhysicsReport(
                test_name=name,
                passed=passed,
                details=details,
                timestamp=time.time(),
            )
            self.results.append(result)

            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} ({elapsed:.2f}s)")

            if not passed:
                all_passed = False
                print(f"   ⚠️  Details: {details}")

        print("\n" + "=" * 60)
        if all_passed:
            print("   ✅ All physics tests passed — anchor is secure.")
        else:
            print("   ❌ Some physics tests failed — anchor compromised!")
        print("=" * 60 + "\n")

        self._save_report()
        return all_passed

    def test_energy_conservation_sho(self) -> Tuple[bool, dict]:
        """
        Test 1: Simple Harmonic Oscillator Energy Conservation.
        The Hamiltonian H = p²/(2m) + ½kq² should be conserved.
        Expected drift ratio: < 0.001 (0.1%)
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
        q, p = 1.0, 0.0  # Start at max displacement, zero momentum
        dt = 0.01
        steps = 10000

        initial_energy = engine.compute_energy(q, p)
        max_drift = 0.0

        for _ in range(steps):
            q, p = engine.step(q, p, dt)
            current_energy = engine.compute_energy(q, p)
            drift = abs(current_energy - initial_energy) / max(initial_energy, 1e-9)
            max_drift = max(max_drift, drift)

        passed = max_drift < 0.001
        return passed, {
            "initial_energy": float(initial_energy),
            "final_energy": float(current_energy),
            "max_drift_ratio": float(max_drift),
            "threshold": 0.001,
            "steps": steps,
            "dt": dt,
        }

    def test_energy_conservation_damped(self) -> Tuple[bool, dict]:
        """
        Test 2: Damped Oscillator Energy Decay.
        With damping, energy should decay monotonically.
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.1)
        q, p = 1.0, 0.0
        dt = 0.01
        steps = 5000

        energies = []
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
            energies.append(engine.compute_energy(q, p))

        # Energy should strictly decrease (or stay constant if undamped)
        is_monotonic = all(energies[i] >= energies[i+1] for i in range(len(energies)-1))
        total_decay = (energies[0] - energies[-1]) / energies[0]

        passed = is_monotonic and total_decay > 0.01  # At least 1% decay
        return passed, {
            "initial_energy": float(energies[0]),
            "final_energy": float(energies[-1]),
            "total_decay_ratio": float(total_decay),
            "monotonic": is_monotonic,
            "steps": steps,
        }

    def test_symplectic_order(self) -> Tuple[bool, dict]:
        """
        Test 3: Symplectic Integrator Order Preservation.
        Leapfrog integration should preserve symplectic structure over long times.
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0)
        q, p = 1.0, 0.0
        dt = 0.01
        period = 2 * np.pi  # For SHO with ω=1
        steps_per_period = int(period / dt)

        # Run 1000 periods
        total_steps = steps_per_period * 1000
        final_energies = []

        for period_idx in range(1000):
            for _ in range(steps_per_period):
                q, p = engine.step(q, p, dt)
            final_energies.append(engine.compute_energy(q, p))

        # Energy should not drift systematically over many periods
        energy_mean = np.mean(final_energies)
        energy_std = np.std(final_energies)
        drift = (max(final_energies) - min(final_energies)) / energy_mean

        passed = drift < 0.005  # 0.5% drift over 1000 periods
        return passed, {
            "periods": 1000,
            "steps_per_period": steps_per_period,
            "total_steps": total_steps,
            "energy_mean": float(energy_mean),
            "energy_std": float(energy_std),
            "drift_ratio": float(drift),
            "threshold": 0.005,
        }

    def test_drift_accumulation(self) -> Tuple[bool, dict]:
        """
        Test 4: Long-term Drift Accumulation.
        Over 1 million steps, cumulative error should still be < 0.1%.
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
        q, p = 1.0, 0.5
        dt = 0.001
        steps = 1_000_000

        initial_energy = engine.compute_energy(q, p)

        # Checkpoint at intervals
        checkpoints = [100_000, 200_000, 500_000, 1_000_000]
        checkpoint_drifts = {}

        for step in range(1, steps + 1):
            q, p = engine.step(q, p, dt)

            if step in checkpoints:
                current_energy = engine.compute_energy(q, p)
                drift = abs(current_energy - initial_energy) / initial_energy
                checkpoint_drifts[str(step)] = float(drift)

        final_energy = engine.compute_energy(q, p)
        final_drift = abs(final_energy - initial_energy) / initial_energy

        passed = final_drift < 0.001
        return passed, {
            "initial_energy": float(initial_energy),
            "final_energy": float(final_energy),
            "final_drift_ratio": float(final_drift),
            "checkpoint_drifts": checkpoint_drifts,
            "threshold": 0.001,
            "steps": steps,
        }

    def test_numerical_stability(self) -> Tuple[bool, dict]:
        """
        Test 5: Numerical Stability at Large Step Sizes.
        Even with dt approaching instability limit (dt ~ 2/ω), energy should not explode.
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0)
        q, p = 1.0, 0.0

        # Leapfrog is stable for dt up to about 2.8/ω
        # Test with dt = 1.5 (large but stable region)
        dt = 1.5
        steps = 1000

        energies = []
        for _ in range(steps):
            q, p = engine.step(q, p, dt)
            energies.append(engine.compute_energy(q, p))

        max_energy = max(energies)
        min_energy = min(energies)
        oscillation_amplitude = (max_energy - min_energy) / np.mean(energies)

        # Energy should oscillate but not grow exponentially
        passed = oscillation_amplitude < 2.0  # Less than 200% oscillation
        return passed, {
            "dt": dt,
            "steps": steps,
            "max_energy": float(max_energy),
            "min_energy": float(min_energy),
            "mean_energy": float(np.mean(energies)),
            "oscillation_amplitude": float(oscillation_amplitude),
            "threshold": 2.0,
        }

    def test_phase_space_preservation(self) -> Tuple[bool, dict]:
        """
        Test 6: Phase Space Volume Preservation (Liouville's Theorem).
        A symplectic integrator should preserve phase space volume.
        """
        engine = SympNetEngine(mass=1.0, spring_constant=1.0)
        dt = 0.01
        steps = 10000

        # Start with ensemble of nearby initial conditions
        base_q, base_p = 1.0, 0.0
        epsilon = 1e-6

        # Track area of triangle formed by 3 nearby points
        points = [
            (base_q, base_p),
            (base_q + epsilon, base_p),
            (base_q, base_p + epsilon),
        ]

        # Evolve all points
        evolved = []
        for q0, p0 in points:
            q, p = q0, p0
            for _ in range(steps):
                q, p = engine.step(q, p, dt)
            evolved.append((q, p))

        # Compute parallelogram area (cross product magnitude)
        (q1, p1), (q2, p2), (q3, p3) = evolved
        area = abs((q2 - q1) * (p3 - p1) - (q3 - q1) * (p2 - p1))

        # Compare to initial area (should be epsilon^2)
        initial_area = epsilon * epsilon
        area_ratio = area / initial_area

        # Volume should be preserved within 1%
        passed = 0.99 < area_ratio < 1.01
        return passed, {
            "initial_area": float(initial_area),
            "final_area": float(area),
            "area_ratio": float(area_ratio),
            "steps": steps,
            "epsilon": epsilon,
        }

    def _save_report(self):
        """Save results to JSON file."""
        report_path = self.output_dir / "physics-validation.json"
        report = {
            "project": "Cosmic Mycelium",
            "component": "SympNet Engine (Physics Anchor)",
            "timestamp": time.time(),
            "all_passed": all(r.passed for r in self.results),
            "tests": [r.to_dict() for r in self.results],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
            },
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"📄 Report saved to: {report_path}")

        # Also save a short summary
        summary_path = self.output_dir / "physics-summary.txt"
        with open(summary_path, 'w') as f:
            f.write("Cosmic Mycelium — Physics Validation Summary\n")
            f.write("=" * 50 + "\n\n")
            for r in self.results:
                status = "✅ PASS" if r.passed else "❌ FAIL"
                f.write(f"{status}  {r.test_name}\n")
                if not r.passed:
                    f.write(f"        Details: {r.details}\n")
            f.write(f"\nTotal: {sum(1 for r in self.results if r.passed)}/{len(self.results)} passed\n")

        print(f"📄 Summary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Cosmic Mycelium Physics Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path("reports"),
        help='Output directory for reports (default: ./reports)'
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Only output JSON report (no console output)'
    )
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Exit on first failure'
    )

    args = parser.parse_args()

    benchmark = PhysicsBenchmark(output_dir=args.output)

    if not args.json_only:
        all_passed = benchmark.run_all()
    else:
        all_passed = True
        for test_name, test_fn in [
            ("Energy Conservation (SHO)", benchmark.test_energy_conservation_sho),
            ("Energy Conservation (Damped)", benchmark.test_energy_conservation_damped),
            ("Symplectic Order", benchmark.test_symplectic_order),
            ("Drift Accumulation", benchmark.test_drift_accumulation),
            ("Numerical Stability", benchmark.test_numerical_stability),
            ("Phase Space Preservation", benchmark.test_phase_space_preservation),
        ]:
            passed, details = test_fn()
            all_passed = all_passed and passed
            if args.fail_fast and not passed:
                break

        benchmark._save_report()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
