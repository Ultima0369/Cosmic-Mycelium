"""
Consensus — The "和而不同" Value Alignment Protocol & Proposal Voting

Two-layer consensus:
1. ProposalConsensus: traditional majority voting for proposals (66% threshold)
2. ValueAlignment:  value vector resonance with diversity preservation
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ============================================================================
# Layer 1: Proposal Consensus (original voting mechanism, renamed)
# ============================================================================

@dataclass
class Proposal:
    """A consensus proposal for cluster-level decision."""

    proposal_id: str
    proposer: str
    type: str  # "symbiosis", "value_shift", "path_share"
    payload: dict
    votes: dict[str, bool] = None

    def __post_init__(self):
        if self.votes is None:
            self.votes = {}


class ProposalConsensus:
    """
    Original consensus layer for "1+1>2" decision making.

    Nodes propose symbiotic relationships, value adjustments, or path sharing.
    Other nodes vote; consensus emerges when threshold is crossed.
    """

    def __init__(self, threshold: float = 0.66):
        self.threshold = threshold
        self.active_proposals: dict[str, Proposal] = {}
        self.agreed_paths: list[str] = []

    def propose(self, proposal: Proposal) -> str:
        """Submit a new proposal."""
        self.active_proposals[proposal.proposal_id] = proposal
        return proposal.proposal_id

    def vote(self, proposal_id: str, voter: str, in_favor: bool) -> bool:
        """Cast a vote on a proposal."""
        proposal = self.active_proposals.get(proposal_id)
        if not proposal:
            return False
        proposal.votes[voter] = in_favor
        return self._check_consensus(proposal)

    def _check_consensus(self, proposal: Proposal) -> bool:
        """Check if consensus reached."""
        if not proposal.votes:
            return False
        total = len(proposal.votes)
        in_favor = sum(1 for v in proposal.votes.values() if v)
        ratio = in_favor / total
        return ratio >= self.threshold

    def is_symbiotic(self, node_a: str, node_b: str) -> bool:
        """Check if two nodes have a symbiotic relationship."""
        path_ab = f"{node_a}<->{node_b}"
        path_ba = f"{node_b}<->{node_a}"
        return path_ab in self.agreed_paths or path_ba in self.agreed_paths

    def record_symbiosis(self, node_a: str, node_b: str) -> None:
        """Record a new symbiotic relationship."""
        path = f"{node_a}<->{node_b}"
        if path not in self.agreed_paths:
            self.agreed_paths.append(path)

    def get_vote_counts(self, proposal_id: str) -> tuple[int, int]:
        """Return (yes_votes, no_votes) for a proposal."""
        proposal = self.active_proposals.get(proposal_id)
        if not proposal or not proposal.votes:
            return (0, 0)
        yes = sum(1 for v in proposal.votes.values() if v)
        no = sum(1 for v in proposal.votes.values() if not v)
        return (yes, no)


# ============================================================================
# Layer 2: Value Alignment (resonance without assimilation)
# ============================================================================

@dataclass
class ValueAlignment:
    """
    Value vector alignment protocol — "和而不同".

    Core principle: value resonance != value assimilation.
    - Value distance < threshold ->微量对齐，产生共振 (+mutual_benefit)
    - Value distance >= threshold ->保持自我，增加 caution

    Preserves individuality while enabling cluster harmony.
    """

    alignment_rate: float = 0.01  # 微量对齐速率 (1% shift toward partner)
    distance_threshold: float = 0.3  # 价值距离阈值
    resonance_bonus: float = 0.05  # 共振奖励增量

    def compute_distance(self, v1: dict[str, float], v2: dict[str, float]) -> float:
        """
        Compute normalized Euclidean distance between two value vectors.

        Returns:
            Distance in [0, 1]: 0 = identical, 1 = completely orthogonal.
        """
        keys = set(v1.keys()) & set(v2.keys())
        if not keys:
            return 1.0

        squared_diff = sum((v1[k] - v2[k]) ** 2 for k in keys)
        # Normalize by number of dimensions and max per-dim range (~2.0)
        max_per_dim = 2.0
        return float(np.sqrt(squared_diff) / max_per_dim)

    def align(
        self, my_vector: dict[str, float], other_vector: dict[str, float]
    ) -> tuple[dict[str, float], bool]:
        """
        Attempt value alignment with another node's value vector.

        Args:
            my_vector: Local value vector.
            other_vector: Partner's value vector.

        Returns:
            (new_vector, resonated): Updated vector + whether resonance occurred.
        """
        distance = self.compute_distance(my_vector, other_vector)

        if distance < self.distance_threshold:
            # Values are close →微量对齐 + 共振奖励
            new_vector = my_vector.copy()
            shared_keys = set(my_vector.keys()) & set(other_vector.keys())
            for key in shared_keys:
                diff = other_vector[key] - my_vector[key]
                adjustment = diff * self.alignment_rate
                new_vector[key] = max(0.1, min(2.0, new_vector[key] + adjustment))
            # Add resonance bonus to mutual_benefit dimension
            new_vector["mutual_benefit"] = new_vector.get("mutual_benefit", 0.0) + self.resonance_bonus
            new_vector["mutual_benefit"] = max(0.1, min(2.0, new_vector["mutual_benefit"]))
            return new_vector, True
        else:
            # Values diverge -> keep self, increase caution
            new_vector = my_vector.copy()
            new_vector["caution"] = min(2.0, new_vector.get("caution", 0.5) + 0.05)
            return new_vector, False


# Backward compatibility: existing code imports `Consensus`
Consensus = ProposalConsensus
