"""
Unit Tests: cluster.collective_intelligence — CollectiveIntelligence Phase 3.3
Tests for cluster global workspace, attention competition, proposal voting, and SuperBrain fusion.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from cosmic_mycelium.cluster.collective_intelligence import (
    ClusterWorkspaceState,
    CollectiveIntelligence,
)
from cosmic_mycelium.cluster.consensus import Consensus


class MockSuperBrain:
    """Minimal SuperBrain mock for integration tests."""

    def __init__(self):
        self.regions = {
            "sensory": MagicMock(activation=0.0, working_memory=[]),
            "predictor": MagicMock(activation=0.0, working_memory=[]),
            "planner": MagicMock(activation=0.0, working_memory=[]),
            "executor": MagicMock(activation=0.0, working_memory=[]),
            "meta": MagicMock(activation=0.0, working_memory=[]),
        }


class TestCollectiveIntelligenceInitialization:
    """Construction and defaults."""

    def test_default_initial_state(self):
        ci = CollectiveIntelligence(node_id="node-1")
        assert ci.node_id == "node-1"
        assert isinstance(ci.consensus, Consensus)
        assert ci.proposals == {}
        assert ci.workspace is None
        assert ci.workspace_history == []
        assert ci._iteration == 0

    def test_custom_consensus_injected(self):
        consensus = Consensus(threshold=0.75)
        ci = CollectiveIntelligence(node_id="node-2", consensus=consensus)
        assert ci.consensus is consensus
        assert ci.consensus.threshold == 0.75

    def test_default_constants(self):
        ci = CollectiveIntelligence(node_id="test")
        assert ci.PROPOSAL_TIMEOUT == 30.0
        assert ci.BROADCAST_INTERVAL == 5.0
        assert ci.ATTENTION_TEMPERATURE == 1.0
        assert ci.MIN_ACTIVE_NODES == 2


class TestProposalManagement:
    """Creating, receiving, and tracking proposals."""

    def test_propose_creates_valid_proposal(self):
        ci = CollectiveIntelligence(node_id="node-a")
        pid = ci.propose(
            region="sensory", content={"data": 123}, priority=0.8, activation=0.9
        )

        assert pid in ci.proposals
        proposal = ci.proposals[pid]
        assert proposal.node_id == "node-a"
        assert proposal.region == "sensory"
        assert proposal.content == {"data": 123}
        assert proposal.priority == 0.8
        assert proposal.activation == 0.9
        assert 0 <= proposal.timestamp <= time.time()

    def test_receive_proposal_adds_foreign_proposal(self):
        ci = CollectiveIntelligence(node_id="node-b")
        ci.receive_proposal(
            proposal_id="remote-1",
            node_id="node-a",
            region="planner",
            content={"cmd": "move"},
            priority=0.7,
            activation=0.6,
            timestamp=1000.0,
        )
        assert "remote-1" in ci.proposals
        p = ci.proposals["remote-1"]
        assert p.node_id == "node-a"
        assert p.region == "planner"

    def test_propose_and_vote_flow(self):
        ci = CollectiveIntelligence(node_id="voter-1")
        pid = ci.propose("executor", {"action": "test"}, 0.5, 0.5)

        # Vote for own proposal
        result = ci.vote_for_proposal(pid, vote=True)
        assert result is True  # threshold 0.5, 1/1 = 100%

        yes, no = ci.get_proposal_votes(pid)
        assert yes == 1
        assert no == 0

    def test_vote_rejects_unknown_proposal(self):
        ci = CollectiveIntelligence(node_id="node-x")
        assert ci.vote_for_proposal("fake-id", True) is False
        yes, no = ci.get_proposal_votes("fake-id")
        assert yes == 0
        assert no == 0


class TestAttentionCompetition:
    """Attention score computation and winner selection."""

    def setup_method(self):
        self.ci = CollectiveIntelligence(node_id="selector")
        # Create proposals with varying activation*priority
        self.p1 = self.ci.propose(
            "sensory", {"v": 1}, priority=0.9, activation=0.9
        )  # 0.81
        self.p2 = self.ci.propose(
            "planner", {"v": 2}, priority=0.5, activation=0.5
        )  # 0.25
        self.p3 = self.ci.propose(
            "executor", {"v": 3}, priority=0.3, activation=0.3
        )  # 0.09

    def test_compute_attention_scores_normalized(self):
        scores = self.ci.compute_attention_scores()
        total = sum(scores.values())
        assert pytest.approx(total, abs=0.001) == 1.0  # normalized sum

    def test_compute_attention_scores_filters_expired(self):
        # Expire p1 manually
        expired_id = self.p1
        self.ci.proposals[expired_id].timestamp = time.time() - 100  # way past timeout
        scores = self.ci.compute_attention_scores()
        assert expired_id not in scores

    def test_compute_attention_scores_empty_when_none_valid(self):
        ci_empty = CollectiveIntelligence(node_id="empty")
        ci_empty.proposals = {}
        assert ci_empty.compute_attention_scores() == {}

    def test_select_winner_greedy_when_temperature_low(self):
        # Greedy selection occurs when _attention_temp < 0.1.
        # With Sprint 3 dynamic adjustment, few proposals (<=2) target TEMP_MIN (0.1),
        # keeping temperature low enough for greedy mode even after adjustment.
        # Reduce to 2 proposals so adjustment (0.8*temp + 0.2*target) stays < 0.1.
        self.ci.proposals = {}
        self.p1 = self.ci.propose("sensory", {"v": 1}, priority=0.9, activation=0.9)
        self.p2 = self.ci.propose("planner", {"v": 2}, priority=0.5, activation=0.5)
        self.ci._attention_temp = 0.01  # start very low
        winner = self.ci.select_winner(force=True)
        assert winner is not None
        # p1 has highest raw score (0.81)
        assert winner.proposal_id == self.p1

    def test_select_winner_none_when_too_soon(self):
        # First call sets _last_selection_time
        self.ci.select_winner(force=True)
        # Second call without force returns None
        assert self.ci.select_winner(force=False) is None

    def test_select_winner_force_overrides_interval(self):
        winner1 = self.ci.select_winner(force=True)
        winner2 = self.ci.select_winner(force=True)  # immediate re-select
        assert winner1 is not None
        assert winner2 is not None


class TestClusterWorkspaceBroadcast:
    """Workspace state updates and history."""

    def setup_method(self):
        self.ci = CollectiveIntelligence(node_id="broadcaster")
        self.pid = self.ci.propose("meta", {"insight": "cluster-wide"}, 0.9, 0.8)

    def test_broadcast_winner_creates_workspace_state(self):
        winner = self.ci.proposals[self.pid]
        state = self.ci.broadcast_winner(winner)

        assert state.content == {"insight": "cluster-wide"}
        assert state.source_node == "broadcaster"
        assert state.source_region == "meta"
        assert state.priority == 0.9
        assert state.iteration == 1

    def test_broadcast_updates_current_workspace(self):
        winner = self.ci.proposals[self.pid]
        state = self.ci.broadcast_winner(winner)
        assert self.ci.workspace is state
        assert self.ci.workspace == state

    def test_broadcast_appends_to_history(self):
        # step() runs full cycle: consensus selection and broadcast
        # Need to achieve consensus first
        pid = self.ci.propose("meta", {"insight": "cluster-wide"}, 0.9, 0.8)
        self.ci.consensus.vote(pid, "node-b", True)
        self.ci.consensus.vote(pid, "node-c", True)
        self.ci.step()
        assert len(self.ci.workspace_history) >= 1

    def test_broadcast_records_symbiosis(self):
        winner = self.ci.proposals[self.pid]
        self.ci.broadcast_winner(winner)
        # Consensus should record symbiosis between broadcaster and cluster
        assert self.ci.consensus.is_symbiotic("broadcaster", "cluster")


class TestStepCycle:
    """Full collective intelligence step()."""

    def test_step_cleans_expired_and_selects_consensus_winner(self):
        ci = CollectiveIntelligence(node_id="cycler")
        # Add one fresh, one expired
        fresh = ci.propose("sensory", {"fresh": True}, 0.9, 0.9)
        old = ci.propose("planner", {"old": True}, 0.9, 0.9)
        ci.proposals[old].timestamp = time.time() - 100  # expired

        # Simulate votes from other nodes to reach consensus on fresh
        ci.consensus.vote(fresh, "node-b", True)
        ci.consensus.vote(fresh, "node-c", True)

        state = ci.step()

        assert state is not None  # consensus winner selected
        assert state.content == {"fresh": True}
        assert old not in ci.proposals  # expired removed
        # Executed proposal removed from active proposals
        assert fresh not in ci.proposals
        # Workspace history updated
        assert len(ci.workspace_history) == 1
        assert ci.workspace_history[0].content == {"fresh": True}

    def test_step_returns_none_when_no_valid_proposals(self):
        ci = CollectiveIntelligence(node_id="empty")
        ci.proposals = {}  # ensure empty
        assert ci.step() is None

    def test_step_returns_none_when_no_consensus(self):
        # Proposal exists but insufficient votes for consensus
        ci = CollectiveIntelligence(node_id="cycler")
        prop = ci.propose("sensory", {"data": 1}, 0.9, 0.9)
        # Only one yes vote (total=1 < 2 required)
        ci.consensus.vote(prop, "node-b", True)

        state = ci.step()
        assert state is None
        # Proposal remains in active list (not executed)
        assert prop in ci.proposals


class TestSuperBrainIntegration:
    """Fusing cluster workspace into local SuperBrain."""

    def test_integrate_cluster_workspace_boosts_meta_region(self):
        ci = CollectiveIntelligence(node_id="node-x")
        ci.workspace = ClusterWorkspaceState(
            content={"type": "decision", "value": 42},
            source_node="node-y",
            source_region="planner",
            priority=0.8,
            timestamp=time.time(),
            iteration=1,
        )
        sb = MockSuperBrain()

        result = ci.integrate_cluster_workspace(sb)

        assert result is True
        # meta region activation boosted
        assert sb.regions["meta"].activation >= 0.3
        # cluster_workspace entry appended to meta working_memory (real list)
        assert len(sb.regions["meta"].working_memory) == 1
        entry = sb.regions["meta"].working_memory[0]
        assert "cluster_workspace" in entry
        cw = entry["cluster_workspace"]
        assert cw["source_node"] == "node-y"
        assert cw["iteration"] == 1

    def test_integrate_returns_false_when_no_workspace(self):
        ci = CollectiveIntelligence(node_id="node-z")
        sb = MockSuperBrain()
        assert ci.integrate_cluster_workspace(sb) is False

    def test_integrate_boosts_source_region_too(self):
        ci = CollectiveIntelligence(node_id="node-a")
        ci.workspace = ClusterWorkspaceState(
            content={},
            source_node="node-b",
            source_region="predictor",
            priority=0.8,
            timestamp=time.time(),
        )
        sb = MockSuperBrain()
        sb.regions["predictor"].activation = 0.0

        ci.integrate_cluster_workspace(sb)

        # source region also boosted (activation capped at 1.0)
        assert sb.regions["predictor"].activation >= 0.2

    def test_create_proposal_from_superbrain_requires_activation_threshold(self):
        ci = CollectiveIntelligence(node_id="node-c")
        sb = MagicMock()
        sb.regions = {
            "low": MagicMock(activation=0.2),  # below 0.3 threshold
            "high": MagicMock(activation=0.5),  # above threshold
        }

        pid_low = ci.create_proposal_from_superbrain(sb, "low", {"x": 1})
        pid_high = ci.create_proposal_from_superbrain(sb, "high", {"y": 2})

        assert pid_low is None
        assert pid_high is not None
        assert pid_high in ci.proposals

    def test_create_proposal_from_unknown_region_returns_none(self):
        ci = CollectiveIntelligence(node_id="node-d")
        sb = MagicMock()
        sb.regions = {}
        assert ci.create_proposal_from_superbrain(sb, "ghost", {}) is None


class TestClusterStatus:
    """Status reporting and history management."""

    def test_get_cluster_status_snapshot(self):
        ci = CollectiveIntelligence(node_id="status-node")
        ci.propose("sensory", {}, 0.5, 0.5)
        ci.propose("planner", {}, 0.6, 0.6)
        # Expire one
        next(iter(ci.proposals.values())).timestamp = time.time() - 100

        status = ci.get_cluster_status()

        assert status["node_id"] == "status-node"
        assert status["active_proposals"] == 1  # only non-expired
        assert status["total_proposals"] == 2
        assert status["workspace_active"] is False
        assert status["iteration"] == 0

    def test_clear_history_trims_old_entries(self):
        ci = CollectiveIntelligence(node_id="hist-node")
        # Manually populate history
        ci.workspace_history = [MagicMock() for _ in range(150)]
        ci.clear_history(keep_last=100)
        assert len(ci.workspace_history) == 100
        assert ci.workspace_history[-1] is not None  # last kept

    def test_clear_history_noop_when_under_limit(self):
        ci = CollectiveIntelligence(node_id="small-hist")
        ci.workspace_history = [MagicMock() for _ in range(10)]
        ci.clear_history(keep_last=100)
        assert len(ci.workspace_history) == 10


# -------------------------------------------------------------------------
# Sprint 3: Voting Weight & Dynamic Temperature & Pattern Mining
# -------------------------------------------------------------------------

class TestVotingWeightSystem:
    """Sprint 3: Contribution-based node voting weights."""

    def test_default_node_weight_is_one(self):
        ci = CollectiveIntelligence(node_id="node-1")
        assert ci.get_node_weight("node-1") == 1.0

    def test_weight_increases_with_contributions(self):
        ci = CollectiveIntelligence(node_id="winner")
        # Simulate 5 proposal wins
        for _ in range(5):
            ci._update_node_contribution("winner")
        weight = ci.get_node_weight("winner")
        assert weight > 1.0
        assert weight < 2.0  # diminishing returns

    def test_weight_logarithmic_growth(self):
        ci = CollectiveIntelligence(node_id="node")
        w1 = ci.get_node_weight("node")
        ci._update_node_contribution("node")
        w2 = ci.get_node_weight("node")
        ci._update_node_contribution("node", delta=99)  # 100 total
        w100 = ci.get_node_weight("node")
        # w100 - w1 should be less than 100 * (w2 - w1)  (sub-linear)
        assert (w100 - w1) < 100 * (w2 - w1) + 0.1

    def test_broadcast_winner_updates_contribution(self):
        ci = CollectiveIntelligence(node_id="broadcaster")
        pid = ci.propose("meta", {"type": "insight"}, 0.9, 0.8)
        winner = ci.proposals[pid]
        ci.broadcast_winner(winner)
        assert ci.get_node_weight("broadcaster") > 1.0
        assert ci._node_contributions["broadcaster"] == 1

    def test_contribution_leaderboard_sorted_desc(self):
        ci = CollectiveIntelligence(node_id="node-a")
        ci._update_node_contribution("node-a", 5)
        ci._update_node_contribution("node-b", 3)
        ci._update_node_contribution("node-c", 7)
        leaderboard = ci.get_contribution_leaderboard(limit=10)
        # Sorted desc by contribution count: node-c(7) > node-a(5) > node-b(3)
        assert leaderboard[0][0] == "node-c"
        assert leaderboard[0][1] == 7
        assert leaderboard[1][0] == "node-a"
        assert leaderboard[1][1] == 5
        assert leaderboard[2][0] == "node-b"
        assert leaderboard[2][1] == 3


class TestDynamicAttentionTemperature:
    """Sprint 3: Temperature adjusts based on proposal count."""

    def setup_method(self):
        self.ci = CollectiveIntelligence(node_id="temp-node")
        self.ci._attention_temp = 1.0  # reset

    def test_temperature_lowers_with_few_proposals(self):
        # With 2 proposals, should trend toward _TEMP_MIN (0.1)
        for _ in range(10):
            self.ci._adjust_temperature(num_proposals=2)
        assert self.ci._attention_temp < 0.5

    def test_temperature_rises_with_many_proposals(self):
        # With 15 proposals, should trend toward higher values
        for _ in range(10):
            self.ci._adjust_temperature(num_proposals=15)
        assert self.ci._attention_temp > 1.0

    def test_temperature_stable_at_moderate_count(self):
        # With ~5 proposals, should stabilize near 1.0
        for _ in range(20):
            self.ci._adjust_temperature(num_proposals=5)
        assert 0.8 <= self.ci._attention_temp <= 1.2

    def test_temperature_bounded_by_limits(self):
        # Stress with extreme proposal counts
        for _ in range(50):
            self.ci._adjust_temperature(num_proposals=100)
        assert self.ci._attention_temp <= self.ci._TEMP_MAX
        self.ci._attention_temp = 1.0
        for _ in range(50):
            self.ci._adjust_temperature(num_proposals=0)
        assert self.ci._attention_temp >= self.ci._TEMP_MIN


class TestWorkspaceHistoryMining:
    """Sprint 3: Pattern extraction from workspace_history."""

    def test_mine_patterns_empty_history(self):
        ci = CollectiveIntelligence(node_id="miner")
        patterns = ci.mine_patterns()
        assert patterns["total_entries"] == 0
        assert patterns["type_distribution"] == {}

    def test_mine_patterns_counts_type_distribution(self):
        ci = CollectiveIntelligence(node_id="node-1")
        # Build fake history
        ci.workspace_history = [
            ClusterWorkspaceState(
                content={"type": "decision", "x": 1},
                source_node="node-a",
                source_region="planner",
                priority=0.9,
                timestamp=1.0,
                iteration=1,
            ),
            ClusterWorkspaceState(
                content={"type": "decision", "y": 2},
                source_node="node-b",
                source_region="sensory",
                priority=0.7,
                timestamp=2.0,
                iteration=2,
            ),
            ClusterWorkspaceState(
                content={"type": "alert", "z": 3},
                source_node="node-a",
                source_region="meta",
                priority=0.8,
                timestamp=3.0,
                iteration=3,
            ),
        ]
        patterns = ci.mine_patterns(top_k=5)

        assert patterns["type_distribution"]["decision"] == 2
        assert patterns["type_distribution"]["alert"] == 1
        assert patterns["region_distribution"]["planner"] == 1
        assert patterns["region_distribution"]["sensory"] == 1
        assert patterns["region_distribution"]["meta"] == 1
        assert patterns["source_frequency"]["node-a"] == 2
        assert patterns["source_frequency"]["node-b"] == 1
        assert patterns["avg_priority_by_type"]["decision"] == pytest.approx(0.8)
        assert patterns["total_entries"] == 3

    def test_mine_patterns_respects_top_k(self):
        ci = CollectiveIntelligence(node_id="node-2")
        ci.workspace_history = [
            ClusterWorkspaceState(
                content={"type": f"type{i}"},
                source_node=f"node-{i}",
                source_region="sensory",
                priority=0.5,
                timestamp=float(i),
                iteration=i,
            )
            for i in range(20)
        ]
        patterns = ci.mine_patterns(top_k=5)
        # All 20 types are unique, but top_k limits output
        assert len(patterns["type_distribution"]) <= 5
        assert len(patterns["region_distribution"]) <= 5
        assert len(patterns["source_frequency"]) <= 5

