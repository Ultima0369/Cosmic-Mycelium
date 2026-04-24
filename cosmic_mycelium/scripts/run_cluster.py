#!/usr/bin/env python3
"""
Cosmic Mycelium — Cluster Runner
Manages a multi-node cluster of silicon infants.

Usage:
    python run_cluster.py --nodes 3              # Start 3 infant nodes
    python run_cluster.py --nodes 5 --profile prod  # 5 nodes, production mode

Environment variables:
    COSMIC_ENV              - Environment name
    REDIS_URL               - Redis connection URL
    KAFKA_BOOTSTRAP_SERVERS - Kafka bootstrap servers
    NODE_MANAGER_URL        - Node manager API URL
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.cluster.node_manager import NodeManager  # noqa: E402
from cosmic_mycelium.utils.logging import setup_logging  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cosmic Mycelium — Silicon Infant Cluster Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--nodes",
        type=int,
        default=3,
        help="Number of infant nodes to spawn (default: 3)",
    )

    parser.add_argument(
        "--min-nodes",
        type=int,
        default=3,
        help="Minimum nodes to maintain (default: 3)",
    )

    parser.add_argument(
        "--max-nodes",
        type=int,
        default=100,
        help="Maximum nodes allowed (default: 100)",
    )

    parser.add_argument(
        "--env",
        type=str,
        default=os.getenv("COSMIC_ENV", "development"),
        choices=["development", "staging", "production"],
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="dev",
        choices=["dev", "prod"],
    )

    return parser.parse_args()


class ClusterRunner:
    """Orchestrates a multi-node silicon infant cluster."""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("ClusterRunner")
        self.node_manager: NodeManager | None = None
        self.running = False

        setup_logging(
            name="cosmic-cluster",
            level=config.log_level,
            log_dir=Path("logs"),
        )

    async def start(self):
        """Start the cluster."""
        self.logger.info("🌀 Starting Cosmic Mycelium Cluster...")
        self.logger.info(f"   Target nodes: {self.config.nodes}")
        self.logger.info(f"   Min/Max: {self.config.min_nodes}/{self.config.max_nodes}")

        # Initialize node manager
        self.node_manager = NodeManager(
            min_nodes=self.config.min_nodes,
            max_nodes=self.config.max_nodes,
        )

        # Start node manager
        await self.node_manager.start()

        # Spawn initial nodes
        self.logger.info("🌱 Spawning infant nodes...")
        for i in range(self.config.nodes):
            node_id = f"infant-cluster-{i:03d}"
            await self.node_manager.spawn_node(node_id)
            await asyncio.sleep(0.5)  # Stagger startup

        self.running = True
        self.logger.info(f"✅ Cluster running with {self.config.nodes} nodes")

        # Monitor cluster health
        await self._monitor_loop()

    async def _monitor_loop(self):
        """Monitor cluster health and auto-repair."""
        while self.running:
            try:
                status = self.node_manager.get_cluster_status()
                self.logger.info(
                    f"📊 Cluster: {status['active_nodes']}/{status['target_nodes']} nodes | "
                    f"Drift OK: {status['physics_anchor_ok']} | "
                    f"Resonance: {status['avg_resonance']:.3f}"
                )

                # Auto-repair: spawn node if below minimum
                if status["active_nodes"] < self.config.min_nodes:
                    self.logger.warning(
                        f"⚠️  Node count below minimum ({status['active_nodes']} < {self.config.min_nodes}), spawning..."
                    )
                    new_id = f"infant-auto-{uuid.uuid4().hex[:8]}"
                    await self.node_manager.spawn_node(new_id)

                await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def shutdown(self):
        """Graceful cluster shutdown."""
        self.logger.info("🌙 Shutting down cluster...")
        self.running = False

        if self.node_manager:
            await self.node_manager.stop()

        self.logger.info("✅ Cluster stopped")


async def main():
    args = parse_args()

    print("\n" + "=" * 60)
    print("   🌀 Cosmic Mycelium — Cluster Manager 🌀")
    print("=" * 60)
    print(f"   Nodes      : {args.nodes}")
    print(f"   Min/Max    : {args.min_nodes}/{args.max_nodes}")
    print(f"   Environment: {args.env}")
    print(f"   Profile    : {args.profile}")
    print("=" * 60 + "\n")

    runner = ClusterRunner(args)

    try:
        await runner.start()
    except KeyboardInterrupt:
        print("\n📡 Shutdown signal received...")
    finally:
        await runner.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
