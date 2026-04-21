"""
Consensus — The "1+1>2" Agreement Layer
Implements symbiotic consensus among nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from cosmic_mycelium.common.data_packet import CosmicPacket


@dataclass
class Proposal:
    """A consensus proposal."""
    proposal_id: str
    proposer: str
    type: str  # "symbiosis", "value_shift", "path_share"
    payload: Dict
    votes: Dict[str, bool] = None

    def __post_init__(self):
        if self.votes is None:
            self.votes = {}


class Consensus:
    """
    Consensus layer for "1+1>2" decision making.

    Nodes can propose symbiotic relationships, value adjustments,
    or path sharing. Other nodes vote, and consensus emerges.
    """

    def __init__(self, threshold: float = 0.66):
        self.threshold = threshold  # 66% agreement needed
        self.active_proposals: Dict[str, Proposal] = {}
        self.agreed_paths: List[str] = []

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
        """Check if two nodes have a symbiotic (1+1>2) relationship."""
        # Check both orderings — symbiosis is bidirectional
        path_ab = f"{node_a}<->{node_b}"
        path_ba = f"{node_b}<->{node_a}"
        return path_ab in self.agreed_paths or path_ba in self.agreed_paths

    def record_symbiosis(self, node_a: str, node_b: str) -> None:
        """Record a new symbiotic relationship."""
        path = f"{node_a}<->{node_b}"
        if path not in self.agreed_paths:
            self.agreed_paths.append(path)
