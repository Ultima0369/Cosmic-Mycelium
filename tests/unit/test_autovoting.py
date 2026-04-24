"""
Unit tests for automatic consensus voting (Phase 3 P2).

Tests that nodes automatically evaluate and vote on received cluster proposals
based on value alignment, energy state, and heuristic rules.

TDD coverage:
- Auto-vote triggered on proposal receive
- Vote decision based on mutual_benefit, caution, energy
- Energy threshold gating (vote_cost = 2.0)
- Cooldown prevents vote spam on same proposal
- Vote cast via consensus.vote() updates tally
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
from cosmic_mycelium.cluster.consensus import ProposalConsensus


@pytest.fixture
def fresh_autovote_state():
    """Reset any module-level state between tests."""
    yield
    # No singleton cleanup needed; each CI gets fresh instance


class TestAutoVoting:
    """Tests for automatic proposal voting."""

    def test_auto_vote_accepts_high_mutual_benefit(self, fresh_autovote_state):
        """Proposal with high mutual_benefit should auto-vote YES."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.9, "caution": 0.1}
        ci.hic.energy = 80.0

        # Simulate receiving a proposal with high mutual_benefit content
        ci.receive_proposal(
            proposal_id="prop-001",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share", "mutual_benefit": 0.8},
            priority=0.7,
            activation=0.7,
            timestamp=0.0,
        )

        # Node should have auto-voted YES
        yes, no = ci.get_proposal_votes("prop-001")
        assert yes == 1
        assert no == 0

    def test_auto_vote_rejects_low_mutual_benefit(self, fresh_autovote_state):
        """Proposal with low mutual_benefit should auto-vote NO."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.2, "caution": 0.8}
        ci.hic.energy = 80.0

        ci.receive_proposal(
            proposal_id="prop-002",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share", "mutual_benefit": 0.1},
            priority=0.3,
            activation=0.3,
            timestamp=0.0,
        )

        yes, no = ci.get_proposal_votes("prop-002")
        assert yes == 0
        assert no == 1

    def test_auto_vote_respects_energy_threshold(self, fresh_autovote_state):
        """Voting requires energy >= VOTE_COST (2.0)."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.9}
        ci.hic.energy = 1.0  # Below vote cost

        ci.receive_proposal(
            proposal_id="prop-003",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share"},
            priority=0.7,
            activation=0.7,
            timestamp=0.0,
        )

        yes, no = ci.get_proposal_votes("prop-003")
        assert yes == 0
        assert no == 0  # No vote cast due to low energy

    def test_auto_vote_cautious_when_caution_high(self, fresh_autovote_state):
        """High caution value flips vote to NO even with moderate benefit."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.6, "caution": 0.9}
        ci.hic.energy = 80.0

        ci.receive_proposal(
            proposal_id="prop-004",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share", "mutual_benefit": 0.5},
            priority=0.6,
            activation=0.6,
            timestamp=0.0,
        )

        yes, no = ci.get_proposal_votes("prop-004")
        assert no == 1  # Caution overrides benefit

    def test_auto_vote_does_not_duplicate(self, fresh_autovote_state):
        """Auto-vote is idempotent — multiple receives don't double vote."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.8}
        ci.hic.energy = 80.0

        # Receive same proposal twice (e.g., network duplicate)
        ci.receive_proposal(
            proposal_id="prop-005",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share", "mutual_benefit": 0.8},
            priority=0.7,
            activation=0.7,
            timestamp=0.0,
        )
        ci.receive_proposal(
            proposal_id="prop-005",
            node_id="node-b",
            region="sensory",
            content={"type": "info_share", "mutual_benefit": 0.8},
            priority=0.7,
            activation=0.7,
            timestamp=0.0,
        )

        yes, no = ci.get_proposal_votes("prop-005")
        assert yes == 1  # Only one vote
        assert no == 0

    def test_auto_vote_self_proposal_abstains(self, fresh_autovote_state):
        """Node does not vote on its own proposal."""
        ci = CollectiveIntelligence(node_id="node-a")
        ci.hic = MagicMock()
        ci.hic.value_vector = {"mutual_benefit": 0.9}
        ci.hic.energy = 80.0

        # Node proposes locally, then receives its own broadcast
        local_id = ci.propose(region="sensory", content={}, priority=0.7, activation=0.7)
        # Simulate receiving own proposal back from network
        ci.receive_proposal(
            proposal_id=local_id,
            node_id="node-a",  # same node
            region="sensory",
            content={},
            priority=0.7,
            activation=0.7,
            timestamp=0.0,
        )

        yes, no = ci.get_proposal_votes(local_id)
        assert yes == 0
        assert no == 0  # Abstain on self
