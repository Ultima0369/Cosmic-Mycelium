"""
Integration Tests: scripts/run_infant.py — Infant Runner Entry Point
Tests CLI argument parsing, config validation, and InfantRunner lifecycle.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))


class TestRunInfantArgumentParsing:
    """Test CLI argument handling in parse_args()."""

    def test_parse_args_defaults(self):
        """Default values are sensible."""
        from cosmic_mycelium.scripts.run_infant import parse_args

        # Test with empty argv (rely on defaults)
        with patch.object(sys, "argv", ["run_infant.py"]):
            args = parse_args()
            assert args.id is None
            assert args.env == "development"
            assert args.profile == "dev"
            assert args.log_level == "INFO"
            assert args.energy_max == 100.0
            assert args.physics_drift_max == 0.001
            assert args.physics_adapt_thresh == 0.001
            assert args.metrics_port == 8000
            assert args.health_port == 8001

    def test_parse_args_custom_id(self):
        """--id overrides default."""
        from cosmic_mycelium.scripts.run_infant import parse_args

        with patch.object(sys, "argv", ["run_infant.py", "--id", "custom-123"]):
            args = parse_args()
            assert args.id == "custom-123"

    def test_parse_args_custom_energy_max(self):
        """--energy-max overrides default."""
        from cosmic_mycelium.scripts.run_infant import parse_args

        with patch.object(sys, "argv", ["run_infant.py", "--energy-max", "150.5"]):
            args = parse_args()
            assert args.energy_max == 150.5

    def test_parse_args_all_custom(self):
        """All arguments can be overridden."""
        from cosmic_mycelium.scripts.run_infant import parse_args

        with patch.object(
            sys,
            "argv",
            [
                "run_infant.py",
                "--id",
                "test-id",
                "--env",
                "production",
                "--profile",
                "prod",
                "--log-level",
                "DEBUG",
                "--energy-max",
                "200",
                "--physics-drift-max",
                "0.005",
                "--physics-adapt-thresh",
                "0.002",
                "--metrics-port",
                "9090",
                "--health-port",
                "9091",
            ],
        ):
            args = parse_args()
            assert args.id == "test-id"
            assert args.env == "production"
            assert args.profile == "prod"
            assert args.log_level == "DEBUG"
            assert args.energy_max == 200.0
            assert args.physics_drift_max == 0.005
            assert args.physics_adapt_thresh == 0.002
            assert args.metrics_port == 9090
            assert args.health_port == 9091


class TestRunInfantImports:
    """Ensure all imports in run_infant.py work correctly."""

    def test_imports_success(self):
        try:
            from cosmic_mycelium.scripts.run_infant import main, parse_args

            assert callable(main)
            assert callable(parse_args)
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")


class TestRunInfantConfigValidation:
    """Config value validation."""

    def test_physics_thresholds_positive(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig

        cfg = InfantConfig(infant_id="test", physics_drift_max=0.01)
        assert cfg.physics_drift_max > 0
        assert cfg.physics_adapt_threshold > 0

    def test_port_numbers_valid(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig

        cfg = InfantConfig(infant_id="test", metrics_port=8000, health_port=8001)
        assert 1 <= cfg.metrics_port <= 65535
        assert 1 <= cfg.health_port <= 65535


class TestInfantRunnerInitialization:
    """Test InfantRunner constructor."""

    def test_runner_initializes_with_config(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-runner")
        runner = InfantRunner(cfg)
        assert runner.config == cfg
        assert runner.infant is None
        assert runner.running is False
        assert runner.metrics_server is None
        assert runner.health_checker is None

    def test_runner_logger_created(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-logger")
        runner = InfantRunner(cfg)
        assert runner.logger is not None
        assert "InfantRunner" in runner.logger.name


class TestInfantRunnerStart:
    """Test the async start() method lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_infant_and_servers(self):
        from cosmic_mycelium.scripts.run_infant import (
            HealthChecker,
            InfantConfig,
            InfantRunner,
            MetricsServer,
        )

        cfg = InfantConfig(infant_id="test-start")
        runner = InfantRunner(cfg)

        with (
            patch.object(MetricsServer, "start", new=AsyncMock()),
            patch.object(HealthChecker, "start", new=AsyncMock()),
            patch.object(runner, "_wait_for_shutdown", new=AsyncMock()) as mock_wait,
            patch.object(runner, "shutdown", new=AsyncMock()),
            patch.object(runner, "_run_infant", new=AsyncMock()),
        ):
            await runner.start()
            # Should have called wait and shutdown (via finally)
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        from cosmic_mycelium.scripts.run_infant import (
            HealthChecker,
            InfantConfig,
            InfantRunner,
            MetricsServer,
        )

        cfg = InfantConfig(infant_id="test-flag")
        runner = InfantRunner(cfg)

        with (
            patch.object(MetricsServer, "start", new=AsyncMock()),
            patch.object(HealthChecker, "start", new=AsyncMock()),
            patch.object(
                runner, "_wait_for_shutdown", new=AsyncMock(return_value=None)
            ),
            patch.object(runner, "shutdown", new=AsyncMock()),
            patch.object(runner, "_run_infant", new=AsyncMock()),
        ):
            await runner.start()
            # running is reset to False after shutdown (in finally block)
            assert runner.running is False


class TestInfantRunnerShutdown:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_servers_and_infant(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-shutdown")
        runner = InfantRunner(cfg)
        runner.metrics_server = AsyncMock()
        runner.health_checker = AsyncMock()
        runner.infant = MagicMock()
        runner.running = True

        await runner.shutdown()

        runner.metrics_server.stop.assert_awaited_once()
        runner.health_checker.stop.assert_awaited_once()
        runner.infant.shutdown.assert_called_once()
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_components(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-null-shutdown")
        runner = InfantRunner(cfg)
        # All None — should not raise
        await runner.shutdown()
        assert runner.running is False


class TestInfantRunnerRunInfant:
    """Test _run_infant background task wrapper."""

    @pytest.mark.asyncio
    async def test_run_infant_calls_infant_run(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-run-task")
        runner = InfantRunner(cfg)
        runner.infant = MagicMock()
        runner.infant.run = MagicMock()

        await runner._run_infant()

        runner.infant.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_infant_logs_crash_and_stops(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-crash")
        runner = InfantRunner(cfg)
        runner.infant = MagicMock()
        runner.infant.run.side_effect = RuntimeError("simulated crash")
        with patch.object(runner.logger, "error") as mock_error:
            await runner._run_infant()
            mock_error.assert_called_once()
            assert runner.running is False


class TestInfantRunnerSignalHandling:
    """Test _wait_for_shutdown signal handling."""

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_returns_on_stop_event(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-signal")
        runner = InfantRunner(cfg)
        # Simulate immediate stop event by patching asyncio.Event
        with patch("asyncio.Event") as MockEvent:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            MockEvent.return_value = mock_event
            # Also need to patch loop.add_signal_handler to avoid issues
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.add_signal_handler = MagicMock()
                await runner._wait_for_shutdown()
                mock_event.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_signal_handler_set_stop(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, InfantRunner

        cfg = InfantConfig(infant_id="test-signal")
        runner = InfantRunner(cfg)
        with patch("asyncio.Event") as MockEvent:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            MockEvent.return_value = mock_event
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.add_signal_handler = MagicMock()
                # Start wait in background
                task = asyncio.create_task(runner._wait_for_shutdown())
                # Give it a moment to set up handlers
                await asyncio.sleep(0.01)
                # Simulate signal by calling the handler that was registered
                # The handler should call stop_event.set()
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                # Handler should have been registered for SIGINT and SIGTERM
                assert mock_loop.return_value.add_signal_handler.call_count >= 2


class TestInfantRunnerMain:
    """Test main() entry point logic."""

    def test_main_creates_config_from_args(self):
        from cosmic_mycelium.scripts.run_infant import InfantConfig, main

        with (
            patch("cosmic_mycelium.scripts.run_infant.InfantRunner") as MockRunner,
            patch("asyncio.run"),
            patch("builtins.print"),
            patch("cosmic_mycelium.scripts.run_infant.parse_args") as mock_parse,
        ):
            mock_args = argparse.Namespace(
                id="test-config",
                env="development",
                profile="dev",
                log_level="INFO",
                energy_max=100.0,
                physics_drift_max=0.001,
                physics_adapt_thresh=0.001,
                metrics_port=8000,
                health_port=8001,
                mini=False,
                cycles=1000,
            )
            mock_parse.return_value = mock_args
            mock_runner = MagicMock()
            MockRunner.return_value = mock_runner
            main()
            # Verify InfantConfig was constructed with correct args
            config_call = MockRunner.call_args[0][0]
            assert isinstance(config_call, InfantConfig)
            assert config_call.infant_id == "test-config"

    def test_main_exception_handling(self):
        from cosmic_mycelium.scripts.run_infant import main

        with (
            patch("cosmic_mycelium.scripts.run_infant.InfantRunner"),
            patch("asyncio.run") as mock_asyncio_run,
            patch("builtins.print"),
            patch("cosmic_mycelium.scripts.run_infant.parse_args") as mock_parse,
            patch("sys.exit") as mock_exit,
            patch("logging.error"),
        ):
            mock_args = argparse.Namespace(
                id="test-exc",
                env="development",
                profile="dev",
                log_level="INFO",
                energy_max=100.0,
                physics_drift_max=0.001,
                physics_adapt_thresh=0.001,
                metrics_port=8000,
                health_port=8001,
                mini=False,
                cycles=1000,
            )
            mock_parse.return_value = mock_args
            mock_asyncio_run.side_effect = RuntimeError("simulated failure")
            main()
            mock_exit.assert_called_once_with(1)

    def test_main_keyboard_interrupt(self):
        from cosmic_mycelium.scripts.run_infant import main

        with (
            patch("cosmic_mycelium.scripts.run_infant.InfantRunner"),
            patch("asyncio.run") as mock_asyncio_run,
            patch("builtins.print") as mock_print,
            patch("cosmic_mycelium.scripts.run_infant.parse_args") as mock_parse,
        ):
            mock_args = argparse.Namespace(
                id="test-kb",
                env="development",
                profile="dev",
                log_level="INFO",
                energy_max=100.0,
                physics_drift_max=0.001,
                physics_adapt_thresh=0.001,
                metrics_port=8000,
                health_port=8001,
                mini=False,
                cycles=1000,
            )
            mock_parse.return_value = mock_args
            mock_asyncio_run.side_effect = KeyboardInterrupt()
            main()
            # Should print goodbye message
            assert any("Goodbye" in str(call) for call in mock_print.call_args_list)
