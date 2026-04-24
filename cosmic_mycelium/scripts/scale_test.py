"""
Node Manager Scale Stress Test — Phase 3 scale validation
Tests NodeManager with 1000+ simulated nodes, health monitoring load.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

import psutil

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.cluster.node_manager import NodeManager
from cosmic_mycelium.infant.main import SiliconInfant


@dataclass
class ScaleReport:
    passed: bool
    target_nodes: int
    actual_nodes: int
    registration_time_s: float
    health_check_time_s: float
    memory_mb: float
    details: dict


class ScaleStressTest:
    """Validate NodeManager scales to 1000+ nodes."""

    def __init__(self, target: int = 1000):
        self.target = target

    def run(self) -> ScaleReport:
        print("\n" + "=" * 60)
        print(f"   📈 Node Manager Scale Test — {self.target} nodes")
        print("=" * 60 + "\n")

        nm = NodeManager(min_nodes=3, max_nodes=self.target + 100)
        nm.start()

        # Phase A: Registration burst
        print(f"  Registering {self.target} infants...")
        start_reg = time.time()
        infants = [SiliconInfant(infant_id=f"scale-{i:04d}") for i in range(self.target)]

        for infant in infants:
            nm.register_node(infant)
        reg_time = time.time() - start_reg
        print(f"  ✓ Registered in {reg_time:.2f}s")

        # Phase B: Health monitoring iteration
        print(f"  Running health monitor tick...")
        start_health = time.time()
        import asyncio
        asyncio.run(nm._check_all_nodes())
        health_time = time.time() - start_health
        print(f"  ✓ Health check in {health_time:.4f}s")

        active = nm.get_active_node_ids()
        mem = psutil.Process().memory_info().rss / 1024**2

        # Validation
        passed = len(active) == self.target
        details = {
            "registration_rate": self.target / reg_time if reg_time > 0 else float('inf'),
            "health_check_ms": health_time * 1000,
            "nodes_per_sec": self.target / reg_time,
        }

        print("\n" + "=" * 60)
        print(f"   {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"   Target:     {self.target:,}")
        print(f"   Active:     {len(active):,}")
        print(f"   Reg rate:   {details['registration_rate']:.1f} nodes/s")
        print(f"   Health tick: {details['health_check_ms']:.2f} ms")
        print(f"   Memory:     {mem:.1f} MB")
        print("=" * 60 + "\n")

        return ScaleReport(
            passed=passed,
            target_nodes=self.target,
            actual_nodes=len(active),
            registration_time_s=reg_time,
            health_check_time_s=health_time,
            memory_mb=mem,
            details=details,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Node Manager Scale Stress Test (Phase 3)"
    )
    parser.add_argument(
        '--nodes',
        type=int,
        default=1000,
        help='Number of nodes to simulate (default: 1000)'
    )
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()

    test = ScaleStressTest(target=args.nodes)
    report = test.run()

    if args.json:
        print(json.dumps(asdict(report), indent=2))

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
