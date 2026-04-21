"""
Integration Tests: scripts/run_cluster.py — Cluster Runner Entry Point
Tests CLI argument parsing, ClusterRunner lifecycle, and NodeManager integration.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))


class TestRunClusterArgumentParsing:
    """Test CLI argument handling in parse_args()."""

    def test_parse_args_defaults(self):
        """Default values are sensible."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        with patch.object(sys, 'argv', ['run_cluster.py']):
            args = parse_args()
            assert args.nodes == 3
            assert args.min_nodes == 3
            assert args.max_nodes == 100
            assert args.env == 'development'
            assert args.log_level == 'INFO'
            assert args.profile == 'dev'

    def test_parse_args_custom_nodes(self):
        """--nodes overrides default."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        with patch.object(sys, 'argv', ['run_cluster.py', '--nodes', '5']):
            args = parse_args()
            assert args.nodes == 5

    def test_parse_args_custom_limits(self):
        """--min-nodes and --max-nodes override defaults."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        with patch.object(sys, 'argv', ['run_cluster.py', '--min-nodes', '2', '--max-nodes', '50']):
            args = parse_args()
            assert args.min_nodes == 2
            assert args.max_nodes == 50

    def test_parse_args_all_custom(self):
        """All arguments can be overridden."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        with patch.object(sys, 'argv', [
            'run_cluster.py',
            '--nodes', '10',
            '--min-nodes', '5',
            '--max-nodes', '20',
            '--env', 'production',
            '--log-level', 'DEBUG',
            '--profile', 'prod',
        ]):
            args = parse_args()
            assert args.nodes == 10
            assert args.min_nodes == 5
            assert args.max_nodes == 20
            assert args.env == 'production'
            assert args.log_level == 'DEBUG'
            assert args.profile == 'prod'


class TestRunClusterImports:
    """Ensure all imports in run_cluster.py work correctly."""

    def test_imports_success(self):
        try:
            from cosmic_mycelium.scripts.run_cluster import parse_args, ClusterRunner
            assert callable(parse_args)
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")


class TestClusterRunnerInitialization:
    """Test ClusterRunner constructor."""

    def test_runner_initializes_with_config(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py', '--nodes', '5']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
            assert runner.config == args
            assert runner.node_manager is None
            assert runner.running is False
            assert runner.logger is not None
            assert "ClusterRunner" in runner.logger.name


    @pytest.mark.asyncio
    async def test_start_creates_node_manager_and_spawns_nodes(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner, NodeManager
        with patch.object(sys, 'argv', ['run_cluster.py', '--nodes', '3']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)

        mock_nm = AsyncMock()
        with patch('cosmic_mycelium.scripts.run_cluster.NodeManager', return_value=mock_nm), \
             patch.object(runner, '_monitor_loop', new=AsyncMock()):
            await runner.start()
            assert runner.node_manager is mock_nm
            assert mock_nm.start.await_count == 1
            assert mock_nm.spawn_node.await_count == 3
            assert runner.running is True

    @pytest.mark.asyncio
    async def test_start_staggers_node_startup(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner, NodeManager
        with patch.object(sys, 'argv', ['run_cluster.py', '--nodes', '2']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)

        mock_nm = AsyncMock()
        with patch('cosmic_mycelium.scripts.run_cluster.NodeManager', return_value=mock_nm), \
             patch.object(runner, '_monitor_loop', new=AsyncMock()), \
             patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            await runner.start()
            # spawn_node called 2x, sleep called 2x (after each spawn)
            assert mock_nm.spawn_node.await_count == 2
            assert mock_sleep.await_count == 2


class TestClusterRunnerShutdown:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_node_manager(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
        runner.node_manager = AsyncMock()
        runner.running = True

        await runner.shutdown()
        runner.node_manager.stop.assert_awaited_once()
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_node_manager(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
        runner.node_manager = None
        runner.running = True
        await runner.shutdown()
        assert runner.running is False


class TestClusterRunnerMonitorLoop:
    """Test _monitor_loop health monitoring and auto-repair."""

    @pytest.mark.asyncio
    async def test_monitor_logs_cluster_status(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
        runner.node_manager = MagicMock()
        runner.node_manager.get_cluster_status.return_value = {
            'active_nodes': 3, 'target_nodes': 3,
            'physics_anchor_ok': True, 'avg_resonance': 0.75,
        }
        runner.running = True

        with patch.object(runner.logger, 'info') as mock_log, \
             patch('asyncio.sleep', new=AsyncMock(side_effect=asyncio.CancelledError)):
            try:
                await runner._monitor_loop()
            except asyncio.CancelledError:
                pass
            assert any('Cluster:' in str(call) for call in mock_log.call_args_list)

    @pytest.mark.asyncio
    async def test_monitor_auto_spawns_below_minimum(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py', '--min-nodes', '3']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
        runner.node_manager = MagicMock()
        runner.node_manager.get_cluster_status.return_value = {
            'active_nodes': 1, 'target_nodes': 3,
            'physics_anchor_ok': True, 'avg_resonance': 0.5,
        }
        runner.node_manager.spawn_node = AsyncMock()
        runner.running = True

        with patch('asyncio.sleep', new=AsyncMock(side_effect=lambda _: setattr(runner, 'running', False) or asyncio.sleep(0))):
            await runner._monitor_loop()
        runner.node_manager.spawn_node.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_monitor_handles_exceptions_gracefully(self):
        from cosmic_mycelium.scripts.run_cluster import ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py']):
            from cosmic_mycelium.scripts.run_cluster import parse_args
            args = parse_args()
            runner = ClusterRunner(args)
        runner.node_manager = MagicMock()
        runner.node_manager.get_cluster_status.side_effect = RuntimeError("NM failure")
        runner.running = True

        with patch.object(runner.logger, 'error') as mock_error, \
             patch('asyncio.sleep', new=AsyncMock(side_effect=asyncio.CancelledError)):
            try:
                await runner._monitor_loop()
            except asyncio.CancelledError:
                pass
            assert any('Monitor error' in str(call) for call in mock_error.call_args_list)


class TestClusterRunnerMain:
    """Test main() entry point logic."""

    def test_main_parses_args_and_creates_runner(self):
        from cosmic_mycelium.scripts.run_cluster import parse_args, ClusterRunner
        with patch.object(sys, 'argv', ['run_cluster.py', '--nodes', '5']):
            args = parse_args()
            runner = ClusterRunner(args)
            assert runner.config.nodes == 5
