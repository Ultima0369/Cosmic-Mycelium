#!/usr/bin/env python3
"""
Cosmic Mycelium — Infant Node Runner
Starts a single silicon infant with live metrics & health monitoring.

Usage:
    python run_infant.py                    # Start infant with default config
    python run_infant.py --id stardust-001  # Start with custom ID
    python run_infant.py --profile dev      # Development profile (hot reload)
    python run_infant.py --profile prod     # Production profile (no debug)

Environment variables (all optional):
    COSMIC_ENV              - Environment name (dev/staging/prod)
    INFANT_ID               - Unique infant identifier (default: auto-generated)
    INFANT_ENERGY_MAX       - Max HIC energy (default: 100.0)
    REDIS_URL               - Redis connection URL
    KAFKA_BOOTSTRAP_SERVERS - Kafka bootstrap servers
    LOG_LEVEL               - Logging level (DEBUG/INFO/WARN/ERROR)

Physical anchor thresholds:
    PHYSICS_ENERGY_DRIFT_MAX       - Max energy drift ratio (default: 0.001)
    PHYSICS_ADAPTATION_THRESHOLD   - Adaptation trigger threshold (default: 0.001)
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.infant.main import SiliconInfant  # noqa: E402
from cosmic_mycelium.utils.health import HealthChecker  # noqa: E402
from cosmic_mycelium.utils.logging import setup_logging  # noqa: E402
from cosmic_mycelium.utils.metrics import MetricsServer  # noqa: E402


@dataclass
class InfantConfig:
    """Configuration for the infant runner."""

    infant_id: str
    environment: str = "development"
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap: str = "localhost:9092"
    energy_max: float = 100.0
    physics_drift_max: float = 0.001
    physics_adapt_threshold: float = 0.001
    metrics_port: int = 8000
    health_port: int = 8001
    profile: str = "dev"


class InfantRunner:
    """Manages the lifecycle of a silicon infant node."""

    def __init__(self, config: InfantConfig):
        self.config = config
        self.logger = logging.getLogger(f"InfantRunner[{config.infant_id}]")
        self.infant: SiliconInfant | None = None
        self.running = False
        self.metrics_server: MetricsServer | None = None
        self.health_checker: HealthChecker | None = None

        # Setup logging
        setup_logging(
            name=f"cosmic-infant-{config.infant_id}",
            level=config.log_level,
            log_dir=Path("logs"),
        )

        self.logger.info("🌱 Cosmic Mycelium Infant Runner initializing...")
        self.logger.info(f"   ID: {config.infant_id}")
        self.logger.info(f"   Environment: {config.environment}")
        self.logger.info(f"   Profile: {config.profile}")

    async def start(self):
        """Start the infant and all supporting services."""
        self.logger.info("🚀 Starting infant node...")

        # 1. Start metrics server
        self.metrics_server = MetricsServer(port=self.config.metrics_port)
        await self.metrics_server.start()
        self.logger.info(
            f"   📊 Metrics server listening on :{self.config.metrics_port}"
        )

        # 2. Start health checker
        self.health_checker = HealthChecker(
            port=self.config.health_port, infant=self.infant
        )
        await self.health_checker.start()
        self.logger.info(
            f"   ❤️  Health check endpoint: http://localhost:{self.config.health_port}/health"
        )

        # 3. Initialize and start infant
        self.infant = SiliconInfant(
            infant_id=self.config.infant_id,
            config={
                "energy_max": self.config.energy_max,
                "physics_drift_max": self.config.physics_drift_max,
                "physics_adapt_threshold": self.config.physics_adapt_threshold,
                "redis_url": self.config.redis_url,
                "kafka_bootstrap": self.config.kafka_bootstrap,
                "metrics_port": self.config.metrics_port,
                "profile": self.config.profile,
            },
        )

        # 4. Start infant in background task
        self.running = True
        infant_task = asyncio.create_task(self._run_infant())

        # 5. Wait for shutdown signal
        await self._wait_for_shutdown()

        # 6. Clean shutdown
        self.running = False
        await infant_task
        await self.shutdown()

    async def _run_infant(self):
        """Run the infant main loop."""
        try:
            self.infant.run()
        except Exception as e:
            self.logger.error(f"Infant crashed: {e}", exc_info=True)
            self.running = False

    async def _wait_for_shutdown(self):
        """Wait for SIGINT or SIGTERM."""
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def signal_handler():
            self.logger.info("📡 Received shutdown signal...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await stop_event.wait()
        self.logger.info("🛑 Shutdown initiated")

    async def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("🌙 Shutting down infant...")
        self.running = False

        if self.metrics_server:
            await self.metrics_server.stop()

        if self.health_checker:
            await self.health_checker.stop()

        if self.infant:
            self.infant.running = False

        self.logger.info("✅ Infant stopped cleanly")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Cosmic Mycelium — Silicon Infant Node Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Start with auto-generated ID
  %(prog)s --id stardust-001                  # Start with specific ID
  %(prog)s --profile prod --log-level INFO    # Production mode
  %(prog)s --env staging --energy-max 150     # Custom environment & energy

Physical Anchor Thresholds:
  --physics-drift-max DRIFT      Maximum energy drift ratio (default: 0.001 = 0.1%%)
  --physics-adapt-thresh THRESH  Adaptation trigger threshold (default: 0.001)

For more information, visit: https://github.com/cosmic-mycelium
        """,
    )

    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Unique infant identifier (default: auto-generated UUID)",
    )

    parser.add_argument(
        "--env",
        type=str,
        default=os.getenv("COSMIC_ENV", "development"),
        choices=["development", "staging", "production"],
        help="Environment name",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="dev",
        choices=["dev", "prod"],
        help="Runtime profile (dev=debug, prod=optimized)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    parser.add_argument(
        "--energy-max",
        type=float,
        default=100.0,
        help="Maximum HIC energy (default: 100.0)",
    )

    parser.add_argument(
        "--physics-drift-max",
        type=float,
        default=0.001,
        help="Maximum energy drift ratio (default: 0.001 = 0.1%%)",
    )

    parser.add_argument(
        "--physics-adapt-thresh",
        type=float,
        default=0.001,
        help="Adaptation trigger threshold (default: 0.001)",
    )

    parser.add_argument(
        "--metrics-port",
        type=int,
        default=8000,
        help="Port for metrics server (default: 8000)",
    )

    parser.add_argument(
        "--health-port",
        type=int,
        default=8001,
        help="Port for health check server (default: 8001)",
    )

    parser.add_argument(
        "--mini",
        action="store_true",
        help="Start in MiniInfant 'silicon bee' mode (lightweight, no cluster)",
    )

    parser.add_argument(
        "--cycles",
        type=int,
        default=1000,
        help="Max breath cycles in mini mode (default: 1000)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Generate infant ID if not provided
    infant_id = args.id or f"infant-{uuid.uuid4().hex[:8]}"

    # Create configuration
    config = InfantConfig(
        infant_id=infant_id,
        environment=args.env,
        log_level=args.log_level,
        energy_max=args.energy_max,
        physics_drift_max=args.physics_drift_max,
        physics_adapt_threshold=args.physics_adapt_thresh,
        metrics_port=args.metrics_port,
        health_port=args.health_port,
        profile=args.profile,
    )

    # Print banner
    print("\n" + "=" * 60)
    print("   🌌  Cosmic Mycelium — Silicon Infant 🌌")
    print("=" * 60)
    print(f"   Infant ID  : {infant_id}")
    print(f"   Environment: {args.env}")
    print(f"   Profile    : {args.profile}")
    print(f"   Energy Max : {config.energy_max}")
    print(f"   Drift Max  : {config.physics_drift_max * 100:.3f}%%")
    print("=" * 60 + "\n")

    # ── MiniInfant mode (lightweight "silicon bee") ──
    if args.mini:
        return _run_mini_infant(infant_id, args.cycles)

    # ── Full SiliconInfant mode ──
    runner = InfantRunner(config)

    try:
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def _run_mini_infant(infant_id: str, max_cycles: int):
    """Run MiniInfant in lightweight 'silicon bee' mode."""
    from cosmic_mycelium.infant.mini import MiniInfant

    print("\n" + "=" * 60)
    print("   🐝  Cosmic Mycelium — Mini Infant (硅基蜜蜂) 🐝")
    print("=" * 60)
    print(f"   ID     : {infant_id}")
    print(f"   Cycles : {max_cycles}")
    print(f"   Mode   : lightweight (no cluster/metrics/health)")
    print("=" * 60 + "\n")

    baby = MiniInfant(infant_id, verbose=True)
    report = baby.run(max_cycles=max_cycles)

    print("\n" + "=" * 60)
    print("   📋  Mini Infant 最终报告")
    print("=" * 60)
    for k, v in report.items():
        print(f"   {k}: {v}")
    print("=" * 60 + "\n")

    return report


if __name__ == "__main__":
    main()
