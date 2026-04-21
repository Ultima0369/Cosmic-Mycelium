"""
Unit Tests: cluster.consensus — Consensus Layer
Tests for symbiotic consensus and proposal voting.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.cluster.consensus import Consensus, Proposal


class TestConsensusInitialization:
    """Consensus constructor tests."""

    def test_default_threshold(self):
        """Default consensus threshold is 0.66 (66%)."""
        c = Consensus()
        assert c.threshold == 0.66

    def test_custom_threshold(self):
        """Custom threshold accepted."""
        c = Consensus(threshold=0.51)
        assert c.threshold == 0.51

    def test_initial_state_empty(self):
        """New Consensus starts with no active proposals."""
        c = Consensus()
        assert c.active_proposals == {}
        assert c.agreed_paths == []


class TestConsensusProposalLifecycle:
    """Propose, vote, consensus."""

    def test_propose_creates_entry(self):
        """propose() stores proposal and returns its ID."""
        c = Consensus()
        prop = Proposal(
            proposal_id="prop-1",
            proposer="node-a",
            type="value_shift",
            payload={"delta": 0.1},
        )
        pid = c.propose(prop)
        assert pid == "prop-1"
        assert c.active_proposals["prop-1"] is prop

    def test_vote_on_unknown_proposal_returns_false(self):
        """vote on non-existent proposal returns False."""
        c = Consensus()
        assert c.vote("unknown", "voter-1", True) is False

    def test_vote_records_and_checks_consensus(self):
        """vote records vote and triggers consensus check."""
        c = Consensus(threshold=0.6)
        prop = Proposal("prop-1", "node-a", "symbiosis", {})
        c.propose(prop)

        # 2 out of 3 = 0.67 > 0.6 → consensus
        c.vote("prop-1", "voter-1", True)
        c.vote("prop-1", "voter-2", True)
        c.vote("prop-1", "voter-3", False)

        assert c._check_consensus(prop) is True

    def test_consensus_requires_threshold(self):
        """Consensus not reached if ratio below threshold."""
        c = Consensus(threshold=0.8)
        prop = Proposal("prop-1", "node-a", "symbiosis", {})
        c.propose(prop)

        c.vote("prop-1", "v1", True)
        c.vote("prop-1", "v2", False)  # 1/2 = 0.5
        assert c._check_consensus(prop) is False

        c.vote("prop-1", "v3", True)   # 2/3 = 0.67
        assert c._check_consensus(prop) is False

    def test_single_voter_consensus_impossible(self):
        """With 1 voter, threshold check handles gracefully."""
        c = Consensus(threshold=0.66)
        prop = Proposal("prop-1", "node-a", "path_share", {})
        c.propose(prop)
        c.vote("prop-1", "v1", True)
        # 1/1 = 1.0 >= 0.66 → consensus reached
        assert c._check_consensus(prop) is True


class TestConsensusSymbiosis:
    """Symbiotic relationship tracking."""

    def test_is_symbiotic_detects_agreed_path(self):
        """is_symbiotic returns True for recorded path."""
        c = Consensus()
        c.record_symbiosis("node-a", "node-b")
        assert c.is_symbiotic("node-a", "node-b") is True

    def test_is_symbiotic_rejects_unknown_pair(self):
        """is_symbiotic returns False for unrecorded pair."""
        c = Consensus()
        assert c.is_symbiotic("node-x", "node-y") is False

    def test_record_symbiosis_idempotent(self):
        """record_symbiosis does not duplicate entries."""
        c = Consensus()
        c.record_symbiosis("node-a", "node-b")
        c.record_symbiosis("node-a", "node-b")
        assert len(c.agreed_paths) == 1
        assert c.agreed_paths[0] == "node-a<->node-b"

    def test_record_symbiosis_bidirectional(self):
        """Path stored in canonical A<->B form (order-independent)."""
        c = Consensus()
        c.record_symbiosis("node-b", "node-a")  # reversed order
        assert c.is_symbiotic("node-a", "node-b") is True
        assert c.is_symbiotic("node-b", "node-a") is True
