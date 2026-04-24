"""
Unit Tests: cluster.node_manager — NodeManager Enhanced
Tests for Phase 3.1 NodeManager with health monitoring, discovery, and recovery.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from cosmic_mycelium.cluster.node_manager import (
    NodeManager,
    NodeStatus,
)


# Mock SiliconInfant for testing (no-op, just for tests)
class MockHIC:
    """Mock HIC matching real interface: energy as property reading _energy."""

    def __init__(self, energy_max=100.0):
        self._energy = energy_max

    @property
    def energy(self):
        return self._energy

    @energy.setter
    def energy(self, value):
        self._energy = value


class MockInfantForTest:
    """Minimal mock infant with hic attribute."""

    def __init__(self, infant_id: str):
        self.infant_id = infant_id
        self.hic = MockHIC(energy_max=100.0)


def make_mock_infant(infant_id: str):
    """Create a mock SiliconInfant for testing."""
    return MockInfantForTest(infant_id)


class TestNodeManagerInitialization:
    """NodeManager construction and defaults."""

    def test_default_parameters(self):
        nm = NodeManager()
        assert nm.min_nodes == 3
        assert nm.max_nodes == 100
        assert not nm.running
        assert nm.enable_auto_recovery is True

    def test_custom_parameters(self):
        nm = NodeManager(min_nodes=1, max_nodes=10, enable_auto_recovery=False)
        assert nm.min_nodes == 1
        assert nm.max_nodes == 10
        assert not nm.enable_auto_recovery


class TestNodeManagerNodeLifecycle:
    """Node registration/unregistration operations."""

    def test_register_node_success(self):
        nm = NodeManager(max_nodes=5)
        mock_infant = make_mock_infant("node-001")
        node_id = nm.register_node(mock_infant, address="node-001:8000")

        assert node_id == "node-001"
        assert "node-001" in nm.nodes
        node = nm.nodes["node-001"]
        assert node.node_id == "node-001"
        assert node.address == "node-001:8000"
        assert node.status == NodeStatus.ACTIVE
        assert node.infant is mock_infant

    def test_register_node_with_metadata(self):
        nm = NodeManager()
        mock_infant = make_mock_infant("node-x")
        metadata = {"version": "1.0", "capabilities": ["vibration", "temp"]}
        nm.register_node(mock_infant, metadata=metadata)

        assert nm.nodes["node-x"].metadata == metadata

    def test_register_node_fails_at_max_capacity(self):
        nm = NodeManager(max_nodes=2)
        nm.register_node(make_mock_infant("node-001"))
        nm.register_node(make_mock_infant("node-002"))

        with pytest.raises(RuntimeError, match="maximum capacity"):
            nm.register_node(make_mock_infant("node-003"))

    def test_register_node_duplicate_raises(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("node-dup"))

        with pytest.raises(ValueError, match="already registered"):
            nm.register_node(make_mock_infant("node-dup"))

    def test_unregister_node_graceful(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("node-001"))
        result = nm.unregister_node("node-001", graceful=True)

        assert result is True
        # Sync path removes immediately; async cleanup runs only if loop active
        assert "node-001" not in nm.nodes

    def test_unregister_node_nonexistent(self):
        nm = NodeManager()
        result = nm.unregister_node("does-not-exist")
        assert result is False


class TestNodeManagerHealthMonitoring:
    """Health check and heartbeat tracking."""

    def test_record_heartbeat_updates_last_seen(self):
        nm = NodeManager()
        mock_infant = make_mock_infant("node-hb")
        nm.register_node(mock_infant)

        initial_seen = nm.nodes["node-hb"].last_seen
        time.sleep(0.1)
        nm.record_heartbeat("node-hb")

        assert nm.nodes["node-hb"].last_seen > initial_seen
        assert nm.nodes["node-hb"].status == NodeStatus.ACTIVE

    def test_record_heartbeat_unknown_node_returns_false(self):
        nm = NodeManager()
        result = nm.record_heartbeat("ghost-node")
        assert result is False

    def test_get_node_health_returns_metrics(self):
        nm = NodeManager()
        mock_infant = make_mock_infant("node-health")
        nm.register_node(mock_infant)
        nm.record_heartbeat("node-health", {"energy": 75.0})

        health = nm.get_node_health("node-health")
        assert health["node_id"] == "node-health"
        assert health["status"] == "active"
        assert 0.0 <= health["health_score"] <= 1.0
        assert "uptime_seconds" in health
        assert health["failure_count"] == 0

    def test_get_node_health_unknown_returns_none(self):
        nm = NodeManager()
        assert nm.get_node_health("ghost") is None

    def test_get_cluster_health_aggregates_metrics(self):
        nm = NodeManager()
        for i in range(3):
            nm.register_node(make_mock_infant(f"node-{i}"))

        cluster_health = nm.get_cluster_health()

        assert cluster_health["total_nodes"] == 3
        assert cluster_health["active_nodes"] == 3
        assert cluster_health["total_energy"] == 300.0  # 3 * 100.0
        assert cluster_health["average_health"] == pytest.approx(1.0, abs=0.01)
        assert cluster_health["min_nodes_met"] is True

    def test_get_cluster_health_empty_cluster(self):
        nm = NodeManager()
        health = nm.get_cluster_health()
        assert health["total_nodes"] == 0
        assert health["active_nodes"] == 0
        assert health["total_energy"] == 0.0
        assert health["min_nodes_met"] is False


class TestNodeManagerFailureDetection:
    """Timeout-based failure detection."""

    def test_node_times_out_becomes_degraded(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("slow-node"))
        nm.HEARTBEAT_TIMEOUT = 0.5

        # Manually set last_seen to past timeout
        nm.nodes["slow-node"].last_seen = time.time() - 1.0

        # Trigger health check
        import asyncio

        asyncio.run(nm._check_all_nodes())

        node = nm.nodes["slow-node"]
        assert node.status == NodeStatus.DEGRADED
        assert node.health.score < 0.5

    def test_consecutive_failures_escalate_to_failed(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("bad-node"))
        nm.HEARTBEAT_TIMEOUT = 0.1
        nm.FAILURE_THRESHOLD = 2

        node = nm.nodes["bad-node"]
        current = time.time()

        # First timeout
        node.last_seen = current - 1.0
        asyncio.run(nm._check_all_nodes())
        assert node.status == NodeStatus.DEGRADED
        assert node.health.consecutive_failures == 1

        # Second consecutive timeout
        node.last_seen = current - 2.0
        asyncio.run(nm._check_all_nodes())
        assert node.status == NodeStatus.FAILED
        assert node.health.consecutive_failures == 2

    def test_failure_propagates_to_flow_router(self):
        """When a node is marked FAILED, FlowRouter.mark_node_failed is called."""
        from unittest.mock import MagicMock, patch

        nm = NodeManager()
        # Replace flow_router with a mock
        mock_fr = MagicMock()
        nm.flow_router = mock_fr

        nm.register_node(make_mock_infant("failing-node"))
        nm.HEARTBEAT_TIMEOUT = 0.1
        nm.FAILURE_THRESHOLD = 2

        node = nm.nodes["failing-node"]
        current = time.time()

        # First timeout -> DEGRADED, no call
        node.last_seen = current - 1.0
        asyncio.run(nm._check_all_nodes())
        mock_fr.mark_node_failed.assert_not_called()

        # Second timeout -> FAILED, should call mark_node_failed
        node.last_seen = current - 2.0
        asyncio.run(nm._check_all_nodes())
        mock_fr.mark_node_failed.assert_called_once_with("failing-node")


class TestNodeManagerRecovery:
    """Auto-recovery orchestration."""

    @pytest.mark.asyncio
    async def test_recover_node_waits_grace_period(self):
        nm = NodeManager(enable_auto_recovery=True)
        nm.register_node(make_mock_infant("recover-me"))
        nm.HEARTBEAT_TIMEOUT = 0.1
        nm.FAILURE_THRESHOLD = 1
        nm.RECOVERY_GRACE_PERIOD = 0.2

        node = nm.nodes["recover-me"]
        node.last_seen = time.time() - 1.0
        await nm._check_all_nodes()

        assert node.status == NodeStatus.FAILED

        # Wait for recovery task
        await asyncio.sleep(0.25)

        # Node should still be failed (no spontaneous recovery)
        assert node.status == NodeStatus.FAILED

    @pytest.mark.asyncio
    async def test_recover_node_spontaneous_recovery(self):
        nm = NodeManager(enable_auto_recovery=True)
        nm.register_node(make_mock_infant("lucky-node"))
        nm.HEARTBEAT_TIMEOUT = 0.1
        nm.FAILURE_THRESHOLD = 1
        nm.RECOVERY_GRACE_PERIOD = 0.2

        node = nm.nodes["lucky-node"]
        node.last_seen = time.time() - 1.0
        await nm._check_all_nodes()
        assert node.status == NodeStatus.FAILED

        # Simulate spontaneous heartbeat during grace period
        async def delayed_heartbeat():
            await asyncio.sleep(0.15)
            nm.record_heartbeat("lucky-node")

        asyncio.create_task(
            delayed_heartbeat()
        )  # noqa: RUF006 - task runs in background, awaited via sleep
        await asyncio.sleep(0.25)

        assert node.status == NodeStatus.ACTIVE
        assert node.health.consecutive_failures == 0


class TestNodeManagerDiscovery:
    """Gossip-based node discovery."""

    def test_get_neighbors_returns_active_nodes(self):
        nm = NodeManager()
        for i in range(5):
            nm.register_node(make_mock_infant(f"node-{i}"))

        neighbors = nm.get_neighbors("node-0")
        assert len(neighbors) == 4
        assert "node-0" not in neighbors

    def test_get_neighbors_excludes_failed_nodes(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("node-a"))
        nm.register_node(make_mock_infant("node-b"))
        nm.register_node(make_mock_infant("node-c"))

        nm.nodes["node-b"].status = NodeStatus.FAILED

        neighbors = nm.get_neighbors("node-a")
        assert "node-b" not in neighbors
        assert "node-c" in neighbors

    def test_get_neighbors_unknown_node_returns_empty(self):
        nm = NodeManager()
        assert nm.get_neighbors("ghost") == []


class TestNodeManagerQueries:
    """Node listing and info retrieval."""

    def test_get_node_ids_returns_all(self):
        nm = NodeManager()
        for i in range(3):
            nm.register_node(make_mock_infant(f"node-{i}"))

        ids = nm.get_node_ids()
        assert set(ids) == {"node-0", "node-1", "node-2"}

    def test_get_active_node_ids_filters_only_active(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("active-1"))
        nm.register_node(make_mock_infant("active-2"))
        nm.register_node(make_mock_infant("failed-1"))

        nm.nodes["failed-1"].status = NodeStatus.FAILED

        active = nm.get_active_node_ids()
        assert set(active) == {"active-1", "active-2"}

    def test_get_node_info_returns_full_metadata(self):
        nm = NodeManager()
        mock_infant = make_mock_infant("info-node")
        nm.register_node(mock_infant, metadata={"region": "us-west"})
        nm.record_heartbeat("info-node")

        info = nm.get_node_info("info-node")
        assert info["node_id"] == "info-node"
        assert info["status"] == "active"
        assert info["energy"] == 100.0  # Unchanged by heartbeat
        assert info["metadata"]["region"] == "us-west"
        assert "uptime" in info["health"]  # health.uptime is seconds since start

    def test_get_all_nodes_info_lists_everyone(self):
        nm = NodeManager()
        for i in range(2):
            nm.register_node(make_mock_infant(f"node-{i}"))

        all_info = nm.get_all_nodes_info()
        assert len(all_info) == 2
        assert all("node_id" in info for info in all_info)


class TestNodeManagerAutoScaling:
    """Minimum node guarantees and cleanup."""

    def test_ensure_min_nodes_spawns_placeholders(self):
        nm = NodeManager(min_nodes=3)
        nm.ensure_min_nodes()

        assert len(nm.nodes) >= 3
        # Placeholder nodes are active by default
        active = nm.get_active_node_ids()
        assert len(active) >= 3

    def test_prune_dead_nodes_removes_stale_failed(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("old-fail"))
        node = nm.nodes["old-fail"]
        node.status = NodeStatus.FAILED
        node.joined_at = time.time() - 4000  # Very old

        pruned = nm.prune_dead_nodes(max_age_seconds=3600)
        assert pruned == 1
        assert "old-fail" not in nm.nodes

    def test_prune_dead_nodes_keeps_recent_failed(self):
        nm = NodeManager()
        nm.register_node(make_mock_infant("recent-fail"))
        node = nm.nodes["recent-fail"]
        node.status = NodeStatus.FAILED
        node.joined_at = time.time() - 100  # Recent

        pruned = nm.prune_dead_nodes(max_age_seconds=3600)
        assert pruned == 0
        assert "recent-fail" in nm.nodes


class TestNodeManagerAsyncLifecycle:
    """Async start/stop with background tasks."""

    @pytest.mark.asyncio
    async def test_start_async_launches_monitoring(self):
        nm = NodeManager()
        await nm.start_async()

        assert nm.running is True
        assert nm._monitor_task is not None
        assert not nm._monitor_task.done()

        nm.stop()
        await asyncio.sleep(0.1)
        assert nm.running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_background_tasks(self):
        nm = NodeManager()
        await nm.start_async()

        nm.stop()
        # Give tasks a moment to process cancellation
        await asyncio.sleep(0.1)

        # Tasks should be done (either cancelled or naturally exited)
        assert nm._monitor_task.done()
        assert nm._discovery_task.done()
