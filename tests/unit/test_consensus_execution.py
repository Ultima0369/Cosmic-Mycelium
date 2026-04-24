"""
Unit tests for consensus execution (Phase 3 P2).

Tests that when a proposal reaches the consensus threshold, the agreed
action is executed cluster-wide via callback/broadcast.

TDD coverage:
- Consensus threshold crossing detection
- Execution callback invocation (once per proposal)
- Broadcast of "consensus_achieved" message to cluster
- Idempotency (no double-execution)
- Cleanup after execution (proposal archived)
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
from cosmic_mycelium.cluster.consensus import ProposalConsensus


@pytest.fixture
def ci_with_voting():
    """Create CI with auto-voting enabled and mock network."""
    ci = CollectiveIntelligence(node_id="node-a")
    ci.hic = MagicMock()
    ci.hic.value_vector = {"mutual_benefit": 0.8, "caution": 0.2}
    ci.hic.energy = 100.0
    # Mock network for broadcast
    ci.network = MagicMock()
    return ci


class TestConsensusExecution:
    """Tests for distributed decision execution via consensus."""

    def test_consensus_threshold_crossing_triggers_execution(self, ci_with_voting):
        """When yes votes reach threshold (66%), execution callback fires."""
        ci = ci_with_voting
        proposal_id = ci.propose(region="sensory", content={"action": "sync_breath"}, priority=0.7, activation=0.7)

        # Simulate votes from other nodes (via receive_proposal auto-vote or manual)
        # Need 2 out of 3 for 66% threshold
        ci.consensus.vote(proposal_id, "node-b", True)
        ci.consensus.vote(proposal_id, "node-c", True)

        # Step collective — should detect consensus and execute
        result = ci.step()

        assert result is not None
        assert result.content == {"action": "sync_breath"}
        assert result.source_node == "node-a"

    def test_consensus_broadcasts_decision_to_cluster(self, ci_with_voting):
        """Consensus achieved → 'consensus_achieved' message broadcast to all nodes."""
        ci = ci_with_voting
        proposal_id = ci.propose(region="planner", content={"decision": "increase_sync"}, priority=0.9, activation=0.9)

        # Votes from two other nodes reach 66% (2/3)
        ci.consensus.vote(proposal_id, "node-b", True)
        ci.consensus.vote(proposal_id, "node-c", True)

        ci.step()

        # Verify broadcast called with consensus_achieved message
        ci.network.broadcast.assert_called()
        call_kwargs = ci.network.broadcast.call_args[1]
        assert call_kwargs["value_payload"]["type"] == "consensus_achieved"
        assert call_kwargs["value_payload"]["proposal_id"] == proposal_id

    def test_consensus_execution_idempotent(self, ci_with_voting):
        """Consensus execution fires only once even with multiple step() calls."""
        ci = ci_with_voting
        proposal_id = ci.propose(region="executor", content={"action": "test"}, priority=0.7, activation=0.7)
        ci.consensus.vote(proposal_id, "node-b", True)
        ci.consensus.vote(proposal_id, "node-c", True)

        # First step executes consensus
        result1 = ci.step()
        assert result1 is not None

        # Second step should NOT execute same proposal again
        result2 = ci.step()
        assert result2 is None  # No new winner

    def test_consensus_not_reached_no_execution(self, ci_with_voting):
        """Below threshold votes → no execution."""
        ci = ci_with_voting
        proposal_id = ci.propose(region="sensory", content={"action": "test"}, priority=0.5, activation=0.5)
        # Only 1 yes vote out of 3 = 33% < 66%
        ci.consensus.vote(proposal_id, "node-b", True)

        result = ci.step()
        assert result is None  # No winner selected

    def test_consensus_cleanup_after_execution(self, ci_with_voting):
        """Executed proposal removed from active proposals dict."""
        ci = ci_with_voting
        proposal_id = ci.propose(region="meta", content={}, priority=0.8, activation=0.8)
        ci.consensus.vote(proposal_id, "node-b", True)
        ci.consensus.vote(proposal_id, "node-c", True)

        ci.step()

        # Proposal should be cleaned up (expired or removed)
        assert proposal_id not in ci.proposals

    def test_consensus_execution_with_multiple_proposals(self, ci_with_voting):
        """Winner selection picks highest score; only winner executes."""
        ci = ci_with_voting
        # Proposal A: high priority + activation
        id_a = ci.propose(region="sensory", content={"id": "A"}, priority=0.9, activation=0.9)
        # Proposal B: lower
        id_b = ci.propose(region="sensory", content={"id": "B"}, priority=0.5, activation=0.5)

        # Vote YES on both
        ci.consensus.vote(id_a, "node-b", True)
        ci.consensus.vote(id_b, "node-c", True)
        ci.consensus.vote(id_b, "node-d", True)  # B gets more votes

        result = ci.step()

        # B should win (higher net score: 0.5*0.5=0.25 * 2/3 votes vs 0.9*0.9=0.81 * 1/3)
        assert result is not None
        assert result.content["id"] == "B"
