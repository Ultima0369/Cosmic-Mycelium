"""
Unit Tests: cluster.consensus — Consensus Layer
Tests for ProposalConsensus (voting) and ValueAlignment (resonance).
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.cluster.consensus import Proposal, ProposalConsensus, ValueAlignment


# ============================================================================
# ProposalConsensus Tests (original consensus logic, renamed)
# ============================================================================

class TestProposalConsensusInitialization:
    """ProposalConsensus constructor tests."""

    def test_default_threshold(self):
        """Default consensus threshold is 0.66 (66%)."""
        pc = ProposalConsensus()
        assert pc.threshold == 0.66

    def test_custom_threshold(self):
        """Custom threshold accepted."""
        pc = ProposalConsensus(threshold=0.51)
        assert pc.threshold == 0.51

    def test_initial_state_empty(self):
        """New ProposalConsensus starts with no active proposals."""
        pc = ProposalConsensus()
        assert pc.active_proposals == {}
        assert pc.agreed_paths == []


class TestProposalConsensusLifecycle:
    """Propose, vote, consensus."""

    def test_propose_creates_entry(self):
        """propose() stores proposal and returns its ID."""
        pc = ProposalConsensus()
        prop = Proposal(
            proposal_id="prop-1",
            proposer="node-a",
            type="value_shift",
            payload={"delta": 0.1},
        )
        pid = pc.propose(prop)
        assert pid == "prop-1"
        assert pc.active_proposals["prop-1"] is prop

    def test_vote_on_unknown_proposal_returns_false(self):
        """vote on non-existent proposal returns False."""
        pc = ProposalConsensus()
        assert pc.vote("unknown", "voter-1", True) is False

    def test_vote_records_and_checks_consensus(self):
        """vote records vote and triggers consensus check."""
        pc = ProposalConsensus(threshold=0.6)
        prop = Proposal("prop-1", "node-a", "symbiosis", {})
        pc.propose(prop)

        # 2 out of 3 = 0.67 > 0.6 → consensus
        pc.vote("prop-1", "voter-1", True)
        pc.vote("prop-1", "voter-2", True)
        pc.vote("prop-1", "voter-3", False)

        assert pc._check_consensus(prop) is True

    def test_consensus_requires_threshold(self):
        """Consensus not reached if ratio below threshold."""
        pc = ProposalConsensus(threshold=0.8)
        prop = Proposal("prop-1", "node-a", "symbiosis", {})
        pc.propose(prop)

        pc.vote("prop-1", "v1", True)
        pc.vote("prop-1", "v2", False)  # 1/2 = 0.5
        assert pc._check_consensus(prop) is False

        pc.vote("prop-1", "v3", True)  # 2/3 = 0.67
        assert pc._check_consensus(prop) is False

    def test_single_voter_consensus_impossible(self):
        """With 1 voter, threshold check handles gracefully."""
        pc = ProposalConsensus(threshold=0.66)
        prop = Proposal("prop-1", "node-a", "path_share", {})
        pc.propose(prop)
        pc.vote("prop-1", "v1", True)
        # 1/1 = 1.0 >= 0.66 → consensus reached
        assert pc._check_consensus(prop) is True


class TestProposalConsensusSymbiosis:
    """Symbiotic relationship tracking."""

    def test_is_symbiotic_detects_agreed_path(self):
        """is_symbiotic returns True for recorded path."""
        pc = ProposalConsensus()
        pc.record_symbiosis("node-a", "node-b")
        assert pc.is_symbiotic("node-a", "node-b") is True

    def test_is_symbiotic_rejects_unknown_pair(self):
        """is_symbiotic returns False for unrecorded pair."""
        pc = ProposalConsensus()
        assert pc.is_symbiotic("node-x", "node-y") is False

    def test_record_symbiosis_idempotent(self):
        """record_symbiosis does not duplicate entries."""
        pc = ProposalConsensus()
        pc.record_symbiosis("node-a", "node-b")
        pc.record_symbiosis("node-a", "node-b")
        assert len(pc.agreed_paths) == 1
        assert pc.agreed_paths[0] == "node-a<->node-b"

    def test_record_symbiosis_bidirectional(self):
        """Path stored in canonical A<->B form (order-independent)."""
        pc = ProposalConsensus()
        pc.record_symbiosis("node-b", "node-a")  # reversed order
        assert pc.is_symbiotic("node-a", "node-b") is True
        assert pc.is_symbiotic("node-b", "node-a") is True


# ============================================================================
# ValueAlignment Tests (IMP-06)
# ============================================================================

class TestValueAlignmentInitialization:
    """ValueAlignment constructor tests."""

    def test_default_parameters(self):
        """Default values are reasonable."""
        va = ValueAlignment()
        assert va.alignment_rate == 0.01
        assert va.distance_threshold == 0.3
        assert va.resonance_bonus == 0.05

    def test_custom_parameters(self):
        """Custom parameters accepted."""
        va = ValueAlignment(alignment_rate=0.05, distance_threshold=0.5)
        assert va.alignment_rate == 0.05
        assert va.distance_threshold == 0.5


class TestValueAlignmentDistance:
    """Tests for compute_distance()."""

    def test_identical_vectors_zero_distance(self):
        """Identical vectors have distance 0."""
        va = ValueAlignment()
        v = {"caution": 0.5, "curiosity": 1.2, "efficiency": 0.8}
        assert va.compute_distance(v, v) == 0.0

    def test_orthogonal_vectors_max_distance(self):
        """Completely different keys yields distance 1.0."""
        va = ValueAlignment()
        v1 = {"caution": 0.5}
        v2 = {"curiosity": 1.0}
        assert va.compute_distance(v1, v2) == 1.0

    def test_partial_overlap_distance_scales_with_difference(self):
        """Distance increases as values diverge."""
        va = ValueAlignment()
        v1 = {"caution": 0.5, "curiosity": 0.5}
        v2_close = {"caution": 0.6, "curiosity": 0.6}
        v2_far = {"caution": 1.5, "curiosity": 1.5}

        d_close = va.compute_distance(v1, v2_close)
        d_far = va.compute_distance(v1, v2_far)
        assert d_close < d_far
        assert d_far > 0.5


class TestValueAlignmentAlign:
    """Tests for align()."""

    def test_align_close_values_resonates(self):
        """Distance < threshold →微量对齐 and resonance bonus."""
        va = ValueAlignment(distance_threshold=0.5)
        my = {"caution": 0.5, "curiosity": 0.5, "mutual_benefit": 0.0}
        other = {"caution": 0.55, "curiosity": 0.45}

        new_vec, resonated = va.align(my, other)

        assert resonated is True
        # Caution moved slightly toward 0.55: 0.5 + (0.05 * 0.01) = 0.5005
        assert new_vec["caution"] > my["caution"] and new_vec["caution"] < 0.55
        # Curiosity moved toward 0.45: 0.5 + (-0.05 * 0.01) = 0.4995
        assert new_vec["curiosity"] < my["curiosity"] and new_vec["curiosity"] > 0.45
        # Resonance bonus added
        assert new_vec["mutual_benefit"] > 0.0

    def test_align_distant_values_no_resonance_increases_caution(self):
        """Distance ≥ threshold → caution increases, no vector shift."""
        va = ValueAlignment(distance_threshold=0.1)
        my = {"caution": 0.5, "curiosity": 0.5}
        other = {"caution": 1.5, "curiosity": 1.5}  # Very different

        new_vec, resonated = va.align(my, other)

        assert resonated is False
        # No alignment shift, just caution bump
        assert new_vec["caution"] == my["caution"] + 0.05
        assert new_vec["curiosity"] == my["curiosity"]

    def test_align_respects_value_bounds(self):
        """Values stay in [0.1, 2.0] after alignment."""
        va = ValueAlignment(distance_threshold=0.5, alignment_rate=1.0)  # aggressive
        my = {"caution": 1.95}
        other = {"caution": 2.0}  # Would push to 2.05 without clamping

        new_vec, _ = va.align(my, other)
        assert new_vec["caution"] <= 2.0
        assert new_vec["caution"] >= 0.1
