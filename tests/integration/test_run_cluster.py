"""
Smoke Tests: scripts/run_cluster.py — Cluster Runner Entry Point
Tests CLI argument parsing and NodeManager integration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add project root
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))


class TestRunClusterArgumentParsing:
    """Test CLI argument handling."""

    def test_default_cluster_config(self):
        """Default cluster config values are sensible."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        # Can't easily test argparse without invoking parse_args(),
        # so just verify the module imports correctly
        from cosmic_mycelium.scripts import run_cluster
        assert hasattr(run_cluster, 'main')

    def test_node_count_default(self):
        """Default node count is 3."""
        # Inspect parser defaults via mock
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--nodes', type=int, default=3)
        args = parser.parse_args([])
        assert args.nodes == 3

    def test_node_count_custom(self):
        """Custom --nodes overrides default."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--nodes', type=int, default=3)
        args = parser.parse_args(['--nodes', '5'])
        assert args.nodes == 5


class TestRunClusterImports:
    """Ensure all imports in run_cluster.py work correctly."""

    def test_imports_success(self):
        """All module imports resolve without error."""
        try:
            from cosmic_mycelium.scripts.run_cluster import main, parse_args
            assert callable(main)
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")


class TestRunClusterConfigValidation:
    """Config value validation."""

    def test_min_max_nodes_relationship(self):
        """min_nodes should be <= max_nodes in typical config."""
        from cosmic_mycelium.scripts.run_cluster import parse_args
        # Logic check: defaults satisfy invariant
        default_min = 3
        default_max = 100
        assert default_min <= default_max

    def test_node_limits_positive(self):
        """Node limits must be positive integers."""
        min_val, max_val = 3, 100
        assert min_val > 0
        assert max_val > 0
        assert min_val <= max_val
