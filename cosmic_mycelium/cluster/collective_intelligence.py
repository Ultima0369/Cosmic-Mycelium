"""
Cluster Collective Intelligence — Phase 3.3
Coordinates distributed global workspace and attention competition across nodes.

Integrates with:
- SuperBrain (local attention & workspace)
- MyceliumNetwork (message routing)
- Consensus (voting)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

import numpy as np

from cosmic_mycelium.cluster.consensus import Consensus, Proposal


@dataclass
class WorkspaceProposal:
    """A node's candidate for cluster global workspace."""

    proposal_id: str
    node_id: str
    region: str
    content: dict[str, Any]
    priority: float
    activation: float
    timestamp: float = field(default_factory=time.time)
    votes: int = 0


@dataclass
class ClusterWorkspaceState:
    """Current cluster-wide global workspace entry."""

    content: dict[str, Any]
    source_node: str
    source_region: str
    priority: float
    timestamp: float
    iteration: int = 0  # broadcast generation counter


class CollectiveIntelligence:
    """
    Coordinates collective cognition across multiple infant nodes.

    Phase 3.3 Features:
    - Cluster global workspace: shared broadcast channel across nodes
    - Distributed attention: competition among node proposals
    - Collective decision: consensus-driven workspace updates
    - SuperBrain integration: local + cluster workspace fusion
    """

    # Configuration
    PROPOSAL_TIMEOUT: float = 30.0  # Seconds proposals remain valid
    BROADCAST_INTERVAL: float = 5.0  # How often to select new winner
    ATTENTION_TEMPERATURE: float = 1.0  # Softmax temperature for attention
    MIN_ACTIVE_NODES: int = 2  # Min nodes for cluster decisions
    VOTE_COST: float = 2.0  # Energy cost for auto-vote evaluation
    VOTE_COOLDOWN: float = 1.0  # Minimum seconds between votes by this node

    # Sprint 3: Dynamic temperature bounds
    _TEMP_MIN: float = 0.1  # Greedy selection lower bound
    _TEMP_MAX: float = 2.0  # High exploration upper bound

    def __init__(
        self,
        node_id: str,
        consensus: Consensus | None = None,
        network: Any | None = None,  # MyceliumNetwork (avoid circular import)
        hic: Any | None = None,  # HIC instance for auto-vote heuristics
    ):
        """
        Initialize collective intelligence for a node.

        Args:
            node_id: This node's ID
            consensus: Shared consensus module (or create new)
            network: Optional network for broadcasting proposals
            hic: Optional HIC instance for auto-vote energy/value checks
        """
        self.node_id = node_id
        self.consensus = consensus or Consensus(threshold=0.5)
        self.network = network
        self.hic = hic  # for auto-vote energy/value_vector access
        self.logger = logging.getLogger(f"CollectiveIntelligence[{node_id}]")

        # Pending proposals from all nodes
        self.proposals: dict[str, WorkspaceProposal] = {}

        # Current cluster workspace state (latest winner)
        self.workspace: ClusterWorkspaceState | None = None

        # Local attention state
        self._local_attention_weights: dict[str, float] = {}
        self._last_selection_time = 0.0
        self._iteration = 0

        # History for analysis
        self.workspace_history: list[ClusterWorkspaceState] = []

        # Sprint 3: Voting weight system — per-node contribution-based weights
        self._node_weights: dict[str, float] = {}
        self._node_contributions: dict[str, int] = {}

        # Sprint 3: Dynamic attention temperature (starts at class default)
        self._attention_temp: float = self.ATTENTION_TEMPERATURE

        # Phase 3 P2: Auto-voting state
        self._voted_proposals: set[str] = set()
        self._last_vote_time: dict[str, float] = {}

        # Sprint 5: thread-safety lock for shared state
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Proposal Management
    # ------------------------------------------------------------------
    def propose(
        self,
        region: str,
        content: dict[str, Any],
        priority: float,
        activation: float,
    ) -> str:
        """
        Propose content for cluster global workspace.

        Args:
            region: Source region name (e.g., "sensory", "planner")
            content: Payload dict
            priority: Urgency [0, 1]
            activation: Region activation level [0, 1]

        Returns:
            proposal_id for tracking
        """
        with self._lock:
            proposal_id = f"prop-{uuid.uuid4().hex[:8]}"

            proposal = WorkspaceProposal(
                proposal_id=proposal_id,
                node_id=self.node_id,
                region=region,
                content=content,
                priority=priority,
                activation=activation,
            )
            self.proposals[proposal_id] = proposal

            # Also register with consensus so votes can be cast
            consensus_proposal = Proposal(
                proposal_id=proposal_id,
                proposer=self.node_id,
                type="workspace",
                payload=content,
            )
            self.consensus.propose(consensus_proposal)

        self.logger.debug(f"Proposed workspace entry: {proposal_id} from {region}")

        # Broadcast proposal to cluster via network (if attached)
        if self.network is not None:
            try:
                self.network.broadcast(
                    source_id=self.node_id,
                    value_payload={
                        "type": "cluster_proposal",
                        "proposal_id": proposal_id,
                        "node_id": self.node_id,
                        "region": region,
                        "content": content,
                        "priority": priority,
                        "activation": activation,
                        "timestamp": proposal.timestamp,
                    },
                )
            except Exception as e:
                self.logger.warning(f"Failed to broadcast proposal: {e}")

        return proposal_id

    def receive_proposal(
        self,
        proposal_id: str,
        node_id: str,
        region: str,
        content: dict[str, Any],
        priority: float,
        activation: float,
        timestamp: float,
    ) -> None:
        """Handle proposal received from another node."""
        with self._lock:
            # Only store if new; idempotent on duplicates
            if proposal_id not in self.proposals:
                self.proposals[proposal_id] = WorkspaceProposal(
                    proposal_id=proposal_id,
                    node_id=node_id,
                    region=region,
                    content=content,
                    priority=priority,
                    activation=activation,
                    timestamp=timestamp,
                )
                # Register with consensus so this node can vote on it
                consensus_proposal = Proposal(
                    proposal_id=proposal_id,
                    proposer=node_id,
                    type="workspace",
                    payload=content,
                )
                self.consensus.propose(consensus_proposal)

            # Phase 3 P2: Auto-vote on received proposal (if not already voted)
            self._auto_vote(proposal_id)

        self.logger.debug(f"Received proposal {proposal_id} from {node_id}/{region}")

    # ------------------------------------------------------------------
    # Phase 3 P2: Auto-voting
    # ------------------------------------------------------------------
    def _auto_vote(self, proposal_id: str) -> bool:
        """
        Automatically evaluate and cast vote on a received proposal.

        Heuristic:
        - Skip if already voted on this proposal
        - Skip if node energy < VOTE_COST
        - Skip if cooldown not elapsed since last vote on any proposal
        - Evaluate: mutual_benefit content key → yes if > 0.5, else no
        - High caution (>= 0.8) → default NO regardless
        - Self-proposal → abstain

        Returns:
            True if vote cast, False otherwise.
        """
        now = time.time()

        # Already voted?
        if proposal_id in self._voted_proposals:
            return False

        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False

        # Self-proposal abstain
        if proposal.node_id == self.node_id:
            self._voted_proposals.add(proposal_id)
            self._last_vote_time[proposal_id] = now
            return False

        # Energy check (requires hic)
        if not hasattr(self, 'hic') or self.hic is None:
            return False
        if self.hic.energy < self.VOTE_COST:
            return False

        # Cooldown check: enforce minimum time between our votes
        if self._last_vote_time:
            last_vote = max(self._last_vote_time.values())
            if now - last_vote < self.VOTE_COOLDOWN:
                return False

        # Extract mutual_benefit from content (if present)
        mb = proposal.content.get("mutual_benefit", proposal.priority * proposal.activation)
        caution = self.hic.value_vector.get("caution", 0.5)

        # Decision: high caution overrides moderate benefit
        vote_yes = False if caution >= 0.8 else mb > 0.5

        # Cast vote via consensus
        self.consensus.vote(proposal_id, self.node_id, vote_yes)
        self._voted_proposals.add(proposal_id)
        self._last_vote_time[proposal_id] = now

        self.logger.debug(
            f"Auto-vote {'YES' if vote_yes else 'NO'} on {proposal_id} "
            f"(mb={mb:.2f}, caution={caution:.2f})"
        )
        return True

    def vote_for_proposal(self, proposal_id: str, vote: bool = True) -> bool:
        """Cast vote for a proposal via consensus module."""
        with self._lock:
            return self.consensus.vote(proposal_id, self.node_id, vote)

    def get_proposal_votes(self, proposal_id: str) -> tuple[int, int]:
        """Get (yes, no) vote counts for a proposal."""
        with self._lock:
            return self.consensus.get_vote_counts(proposal_id)

    # ------------------------------------------------------------------
    # Sprint 3: Voting Weight System
    # ------------------------------------------------------------------
    def get_node_weight(self, node_id: str) -> float:
        """
        Get current voting weight for a node.

        Weight starts at 1.0 and increases with each successful proposal adoption.
        """
        with self._lock:
            return self._node_weights.get(node_id, 1.0)

    def _update_node_contribution(self, node_id: str, delta: int = 1) -> None:
        """
        Record a contribution (proposal adopted into cluster workspace).

        Args:
            node_id: Contributing node
            delta: Change in contribution count (default +1)
        """
        self._node_contributions[node_id] = self._node_contributions.get(node_id, 0) + delta
        # Weight = 1.0 + 0.2 * log(1 + contributions)  (diminishing returns)
        contribs = self._node_contributions[node_id]
        self._node_weights[node_id] = 1.0 + 0.2 * np.log(1.0 + float(contribs))

    def get_contribution_leaderboard(self, limit: int = 10) -> list[tuple[str, int, float]]:
        """
        Return top contributing nodes.

        Returns:
            List of (node_id, contribution_count, weight) sorted by contribution desc
        """
        with self._lock:
            sorted_nodes = sorted(
                self._node_contributions.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            return [
                (node_id, count, self._node_weights.get(node_id, 1.0))
                for node_id, count in sorted_nodes[:limit]
            ]

    # ------------------------------------------------------------------
    # Sprint 3: Dynamic Attention Temperature
    # ------------------------------------------------------------------
    def get_attention_temperature(self) -> float:
        """Current attention temperature."""
        return self._attention_temp

    def _adjust_temperature(self, num_proposals: int) -> None:
        """
        Dynamically adjust attention temperature based on competition density.

        Strategy:
        - Few proposals (< 3): lower temp → greedy selection (exploitation)
        - Many proposals (> 10): raise temp → more exploration
        - Otherwise: maintain near default (1.0)
        """
        if num_proposals <= 2:
            # Very few choices — be greedy
            target = self._TEMP_MIN
        elif num_proposals >= 10:
            # High competition — increase exploration
            target = min(self._TEMP_MAX, 1.0 + (num_proposals - 10) * 0.1)
        else:
            # Moderate — slowly trend toward 1.0
            target = 1.0

        # Smooth adjustment (exponential moving average)
        self._attention_temp = 0.8 * self._attention_temp + 0.2 * target



    # ------------------------------------------------------------------
    # Attention Competition & Winner Selection
    # ------------------------------------------------------------------
    def compute_attention_scores(self) -> dict[str, float]:
        """
        Compute attention scores for all pending proposals.
        Uses softmax over (activation * priority) with temperature.
        """
        now = time.time()
        scores = {}
        total = 0.0

        # Filter valid (non-expired) proposals
        valid_proposals = [
            p
            for p in self.proposals.values()
            if now - p.timestamp < self.PROPOSAL_TIMEOUT
        ]

        if not valid_proposals:
            return {}

        for proposal in valid_proposals:
            # Combined score: activation * priority
            raw = proposal.activation * proposal.priority
            scores[proposal.proposal_id] = raw
            total += raw

        if total == 0:
            return {}

        # Normalize
        for pid in scores:
            scores[pid] /= total

        return scores

    def select_winner(self, force: bool = False) -> WorkspaceProposal | None:
        """
        Run attention competition to select winning proposal for cluster workspace.

        Args:
            force: If True, select even if no new proposals

        Returns:
            Winning WorkspaceProposal or None
        """
        now = time.time()
        if not force and now - self._last_selection_time < self.BROADCAST_INTERVAL:
            return None  # not yet time for new selection

        with self._lock:
            # Filter valid proposals first (for count & score computation)
            valid_proposals = [
                p
                for p in self.proposals.values()
                if now - p.timestamp < self.PROPOSAL_TIMEOUT
            ]

            # Sprint 3: Dynamically adjust temperature based on competition density
            self._adjust_temperature(len(valid_proposals))

            if not valid_proposals:
                return None

            scores = {}
            total = 0.0
            for proposal in valid_proposals:
                raw = proposal.activation * proposal.priority
                scores[proposal.proposal_id] = raw
                total += raw

            if total == 0:
                return {}

            for pid in scores:
                scores[pid] /= total

            # Softmax-weighted selection (or greedy if temperature low)
            proposal_ids = list(scores.keys())
            proposal_scores = np.array([scores[pid] for pid in proposal_ids])

            if self._attention_temp < 0.1:
                winner_idx = int(np.argmax(proposal_scores))
            else:
                exp_scores = np.exp(proposal_scores / self._attention_temp)
                probs = exp_scores / np.sum(exp_scores)
                winner_idx = int(np.random.choice(len(proposal_ids), p=probs))

            winner_id = proposal_ids[winner_idx]
            winner = self.proposals.get(winner_id)

            if winner:
                self._last_selection_time = now
                self.logger.info(
                    f"Cluster attention winner: {winner_id} from {winner.node_id} "
                    f"(score={scores[winner_id]:.3f}, temp={self._attention_temp:.2f})"
                )

            return winner

    def broadcast_winner(self, winner: WorkspaceProposal, *, via_consensus: bool = False) -> ClusterWorkspaceState:
        """
        Broadcast winning proposal to cluster global workspace.

        Args:
            winner: Selected proposal
            via_consensus: True if winner selected via consensus threshold (not attention)

        Returns:
            New ClusterWorkspaceState
        """
        with self._lock:
            self._iteration += 1
            state = ClusterWorkspaceState(
                content=winner.content,
                source_node=winner.node_id,
                source_region=winner.region,
                priority=winner.priority,
                timestamp=time.time(),
                iteration=self._iteration,
            )
            self.workspace = state
            self.workspace_history.append(state)

            # Record symbiosis relationship
            self.consensus.record_symbiosis(winner.node_id, "cluster")

            # Sprint 3: Update contribution-based voting weight
            self._update_node_contribution(winner.node_id, delta=1)

            # Phase 3 P2: Consensus execution cleanup & notification
            if via_consensus:
                # Remove executed proposal from active set
                self.proposals.pop(winner.proposal_id, None)
                self._voted_proposals.discard(winner.proposal_id)
                self._last_vote_time.pop(winner.proposal_id, None)
                # Broadcast consensus_achieved message to all nodes
                if self.network is not None:
                    try:
                        self.network.broadcast(
                            source_id=self.node_id,
                            value_payload={
                                "type": "consensus_achieved",
                                "proposal_id": winner.proposal_id,
                                "content": winner.content,
                                "source_node": winner.node_id,
                                "iteration": self._iteration,
                            },
                        )
                        self.logger.info(f"Consensus executed: {winner.proposal_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to broadcast consensus_achieved: {e}")

        self.logger.info(
            f"Cluster workspace updated by {winner.node_id}/{winner.region}: "
            f"{winner.content.get('type', 'unknown')}"
        )
        return state

    def step(self) -> ClusterWorkspaceState | None:
        """
        Run one collective intelligence cycle.

        Phase 3 P2 behavior: only proposals achieving consensus threshold
        become cluster workspace updates. Attention-based selection disabled.

        Returns:
            New workspace state if consensus winner selected, else None
        """
        with self._lock:
            # Clean expired proposals first
            now = time.time()
            expired = [
                pid
                for pid, p in self.proposals.items()
                if now - p.timestamp > self.PROPOSAL_TIMEOUT
            ]
            for pid in expired:
                del self.proposals[pid]

            # Phase 3 P2: Consensus-only selection
            consensus_winner = self._select_by_consensus()
            if consensus_winner:
                return self.broadcast_winner(consensus_winner, via_consensus=True)

        return None

    # ------------------------------------------------------------------
    # Phase 3 P2: Consensus-based decision execution
    # ------------------------------------------------------------------
    def _select_by_consensus(self) -> WorkspaceProposal | None:
        """
        Check all valid proposals for consensus threshold crossing.

        Returns:
            First proposal reaching consensus threshold, or None.
        """
        now = time.time()
        for proposal in self.proposals.values():
            if now - proposal.timestamp > self.PROPOSAL_TIMEOUT:
                continue
            yes, no = self.consensus.get_vote_counts(proposal.proposal_id)
            total = yes + no
            if total >= 2 and (yes / total) >= self.consensus.threshold:
                self.logger.info(
                    f"Consensus achieved on {proposal.proposal_id}: "
                    f"{yes}/{total} yes votes ({yes/total:.1%})"
                )
                return proposal
        return None

    # ------------------------------------------------------------------
    # Integration with SuperBrain
    # ------------------------------------------------------------------
    def integrate_cluster_workspace(
        self,
        superbrain: Any,  # SuperBrain type (avoid circular import)
    ) -> bool:
        """
        Fuse cluster workspace into ALL brain regions (Phase 3 P2 subscription).

        Each region receives the cluster content in working_memory with
        appropriate activation boost: meta +0.3, source +0.2, others +0.1.

        Args:
            superbrain: Local SuperBrain instance

        Returns:
            True if integration performed
        """
        with self._lock:
            if not self.workspace:
                return False

            content = self.workspace.content
            source_node = self.workspace.source_node
            source_region = self.workspace.source_region
            timestamp = self.workspace.timestamp
            iteration = self.workspace.iteration

            # Notify every region — cluster workspace is globally relevant
            for name, region in superbrain.regions.items():
                # Determine boost amount
                if name == "meta":
                    boost = 0.3  # meta integrates cluster-level perspective
                elif name == source_region:
                    boost = 0.2  # source region gets extra attention
                else:
                    boost = 0.1  # baseline awareness for all other regions

                region.activation = min(1.0, region.activation + boost)
                # Store full workspace state under 'cluster_workspace' key
                region.working_memory.append(
                    {
                        "cluster_workspace": {
                            "content": content,
                            "source_node": source_node,
                            "source_region": source_region,
                            "priority": self.workspace.priority,
                            "timestamp": timestamp,
                            "iteration": iteration,
                        }
                    }
                )
                # Maintain activation history
                region.activation_history.append(region.activation)
                if len(region.activation_history) > 100:
                    region.activation_history.pop(0)

        return True

    def create_proposal_from_superbrain(
        self,
        superbrain: Any,
        region_name: str,
        content: dict[str, Any],
    ) -> str | None:
        """
        Create cluster proposal from a local SuperBrain region activation.

        Args:
            superbrain: Local SuperBrain
            region_name: Region proposing content
            content: Proposal content

        Returns:
            proposal_id if created, None if region not found/low activation
        """
        if region_name not in superbrain.regions:
            return None

        region = superbrain.regions[region_name]
        if region.activation < 0.3:
            return None  # Not activated enough to propose

        return self.propose(
            region=region_name,
            content=content,
            priority=region.activation,
            activation=region.activation,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def get_cluster_status(self) -> dict[str, Any]:
        """Cluster intelligence state snapshot."""
        with self._lock:
            now = time.time()
            valid_proposals = [
                p
                for p in self.proposals.values()
                if now - p.timestamp < self.PROPOSAL_TIMEOUT
            ]

            return {
                "node_id": self.node_id,
                "active_proposals": len(valid_proposals),
                "total_proposals": len(self.proposals),
                "workspace_active": self.workspace is not None,
                "workspace_source": self.workspace.source_node if self.workspace else None,
                "iteration": self._iteration,
            }

    def clear_history(self, keep_last: int = 100) -> None:
        """Trim workspace history to last N entries."""
        with self._lock:
            if len(self.workspace_history) > keep_last:
                self.workspace_history = self.workspace_history[-keep_last:]

    # ------------------------------------------------------------------
    # Sprint 3: Workspace History Pattern Mining
    # ------------------------------------------------------------------
    def mine_patterns(self, top_k: int = 5) -> dict[str, Any]:
        """
        Analyze workspace_history to extract common patterns.

        Args:
            top_k: Number of top patterns to return per category

        Returns:
            Dict with pattern statistics:
            {
                "type_distribution": {type_str: count, ...},
                "region_distribution": {region_str: count, ...},
                "source_frequency": {node_id: count, ...},
                "avg_priority_by_type": {type_str: avg_priority, ...},
                "total_entries": int,
            }
        """
        with self._lock:
            result: dict[str, Any] = {
                "type_distribution": {},
                "region_distribution": {},
                "source_frequency": {},
                "avg_priority_by_type": {},
                "total_entries": 0,
            }

            if not self.workspace_history:
                return result

            from collections import Counter

            type_counts = Counter()
            region_counts = Counter()
            source_counts = Counter()
            priority_by_type: dict[str, list[float]] = {}

            for entry in self.workspace_history:
                content_type = entry.content.get("type", "unknown")
                type_counts[content_type] += 1
                region_counts[entry.source_region] += 1
                source_counts[entry.source_node] += 1

                if content_type not in priority_by_type:
                    priority_by_type[content_type] = []
                priority_by_type[content_type].append(entry.priority)

            # Compute averages
            avg_priority_by_type = {
                t: sum(priors) / len(priors) for t, priors in priority_by_type.items()
            }

            result["type_distribution"] = dict(type_counts.most_common(top_k))
            result["region_distribution"] = dict(region_counts.most_common(top_k))
            result["source_frequency"] = dict(source_counts.most_common(top_k))
            result["avg_priority_by_type"] = avg_priority_by_type
            result["total_entries"] = len(self.workspace_history)

            return result

