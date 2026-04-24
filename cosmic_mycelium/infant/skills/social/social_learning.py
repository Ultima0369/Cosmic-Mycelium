"""
SocialLearningSkill — Observational Peer Learning

Enables infants to learn by observing peers in the cluster, imitate
successful strategies, and build social bonds that facilitate future
knowledge transfer. Part of the cultural transmission system.

Phase: Epic 2 (Skill Plugin System — Built-in Skills)
"""

from __future__ import annotations

import time
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext, SkillExecutionError

if TYPE_CHECKING:
    from cosmic_mycelium.cluster.consensus import CollectiveIntelligence
    from cosmic_mycelium.infant.hic import HIC


@dataclass
class ObservedBehavior:
    """
    A single observed behavior from a peer infant.

    Captures: who did what, in what context, with what outcome.
    Used for strategy imitation and cultural learning.
    """

    behavior_id: str
    source_infant: str
    behavior_type: str  # "proposal_vote", "energy_action", "exploration", etc.
    context: dict[str, float]  # state at time of action
    outcome: dict[str, Any]  # result of action
    timestamp: float
    tags: list[str] = field(default_factory=list)


@dataclass
class SocialBond:
    """
    Bilateral relationship metadata with a peer.

    Trust accumulates through successful interactions and shared value alignment.
    High trust enables direct knowledge requests (bypassing public workspace).
    """

    peer_id: str
    trust: float = 0.5  # [0.0, 1.0] — initial neutral
    interactions: int = 0
    last_interaction: float = field(default_factory=time.time)
    value_alignment: float = 0.5  # cached value distance score


class SocialLearningSkill(InfantSkill):
    """
    Observational learning from cluster peers.

    Learning modes:
    1. Observation — passively watch peer actions in CollectiveIntelligence workspace
    2. Imitation — replicate a successful observed behavior
    3. Bond-strengthening — increase trust with frequently-interacted peers

    Activation triggers:
    - HIC curiosity > threshold (drive to explore others' strategies)
    - Low energy (learn节能策略 from peers)
    - Recent failed experiment (seek alternative approaches)

    Dependencies:
    - collective_intelligence: access to shared workspace entries
    """

    name = "social_learning"
    version = "1.0.0"
    description = "Learn by observing and imitating peer infants in the cluster"
    dependencies = ["collective_intelligence"]
    parallelism_policy = ParallelismPolicy.ISOLATED  # Sprint 5: thread-safe with class-level lock

    # Class-level shared observation database (all infants contribute)
    _observed_behaviors: dict[str, ObservedBehavior] = {}
    _social_bonds: dict[str, SocialBond] = {}
    _lock = threading.RLock()  # Sprint 5: protects class-level shared state

    # Configuration
    OBSERVATION_WINDOW = 50  # max recent behaviors to keep in memory
    BOND_DECAY_RATE = 0.01  # trust decay per hour of inactivity
    IMPRESSIONABLE_THRESHOLD = 0.7  # minimum trust to accept direct knowledge request
    IMITATION_SUCCESS_RATE = 0.8  # estimated probability imitation works

    def __init__(
        self,
        collective: CollectiveIntelligence | None = None,
        hic: HIC | None = None,
    ):
        self.collective = collective
        self.hic = hic
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0
        self._observation_history: list[str] = []
        self._imitation_candidates: list[str] = []
        self._cooldown: float = 30.0
        # Ensure class-level shared state exists (fixture may have deleted it)
        if not hasattr(self.__class__, "_observed_behaviors"):
            self.__class__._observed_behaviors = {}
        if not hasattr(self.__class__, "_social_bonds"):
            self.__class__._social_bonds = {}

    # -------------------------------------------------------------------------
    # InfantSkill Protocol
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """Initialize social learning skill."""
        self._initialized = True
        self._infant_id = context.infant_id

    def can_activate(self, context: SkillContext) -> bool:
        """
        Social learning activation conditions:
        - Initialized
        - Energy >= 8 (observation is cheap, imitation costs more)
        - Cooldown elapsed
        - CollectiveIntelligence workspace available
        """
        if not self._initialized:
            return False
        if context.energy_available < 8:
            return False
        if time.time() - self._last_execution < self._cooldown:
            return False
        if self.collective is None or self.collective.workspace is None:
            return False
        return True

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one social learning cycle.

        Args:
            params:
                - observe_only: bool   — only observe, don't imitate (default False)
                - imitate: str         — behavior_id to imitate
                - peer_filter: str     — only observe from this peer
                - strengthen_bond: str — peer_id to bond with

        Returns:
            {
                "status": "observed" | "imitated" | "bond_strengthened" | "skipped_low_trust" | "cooldown",
                "behaviors_observed": int,
                "behavior_id": str | None,
                "peer_id": str | None,
                "energy_cost": float,
            }
        """
        if not self._initialized:
            raise SkillExecutionError("SocialLearningSkill not initialized")

        now = time.time()
        if now - self._last_execution < self._cooldown:
            return {"status": "cooldown", "energy_cost": 0.1}

        observe_only = params.get("observe_only", False)
        imitate_id = params.get("imitate")
        peer_filter = params.get("peer_filter")
        strengthen_peer = params.get("strengthen_bond")

        # Observation phase: scan workspace for recent peer behaviors
        observed = self._scan_workspace(peer_filter)
        if not observed:
            return {"status": "no_peers_observed", "energy_cost": 0.5}

        base_cost = 2.0

        # Imitation phase (if requested)
        if imitate_id:
            if imitate_id not in self._observed_behaviors:
                return {"status": "behavior_not_known", "energy_cost": 0.5}
            result = self._imitate_behavior(imitate_id)
            result["energy_cost"] = base_cost + result.get("imitation_cost", 0.0)
            return result

        # Bond strengthening (explicit)
        if strengthen_peer:
            result = self._strengthen_bond(strengthen_peer)
            result["energy_cost"] = base_cost + result.get("bond_cost", 0.0)
            return result

        # Pure observation
        self._last_execution = now
        self._execution_count += 1
        return {
            "status": "observed",
            "behaviors_observed": len(observed),
            "peers": list({b.source_infant for b in observed}),
            "energy_cost": base_cost,
        }

    def get_resource_usage(self) -> dict[str, float]:
        """Social learning is moderately expensive (imitation adaptation cost)."""
        return {"energy_cost": 2.0, "duration_s": 0.08, "memory_mb": 5.0}

    def shutdown(self) -> None:
        """Cleanup social learning state."""
        with self.__class__._lock:
            self.__class__._observed_behaviors.clear()
            self.__class__._social_bonds.clear()
        self._initialized = False

    def get_status(self) -> dict[str, Any]:
        """Return social learning skill health."""
        with self.__class__._lock:
            return {
                "name": self.name,
                "version": self.version,
                "initialized": self._initialized,
                "execution_count": self._execution_count,
                "last_execution": self._last_execution,
                "observed_behaviors": len(self.__class__._observed_behaviors),
                "social_bonds": len(self.__class__._social_bonds),
                "imitation_candidates": len(self._imitation_candidates),
            }

    # -------------------------------------------------------------------------
    # Internal: Observation
    # -------------------------------------------------------------------------

    def _scan_workspace(self, peer_filter: str | None) -> list[ObservedBehavior]:
        """
        Scan CollectiveIntelligence workspace for recent peer behaviors.

        Filters:
        - Excludes self
        - Only entries with behavior_type metadata
        - Trust-filter: skip peers with bond.trust < 0.3 (unless no others)
        """
        if self.collective is None or self.collective.workspace is None:
            return []

        with self.__class__._lock:
            ws = self.collective.workspace
            entries = ws.get_recent_entries(limit=self.OBSERVATION_WINDOW)

            behaviors: list[ObservedBehavior] = []
            for entry in entries:
                meta = entry.metadata or {}
                behavior_type = meta.get("behavior_type")
                source = entry.source_infant

                if not behavior_type or source == self._infant_id:
                    continue
                if peer_filter and source != peer_filter:
                    continue

                # Trust filter
                bond = self._social_bonds.get(source)
                if bond and bond.trust < 0.3:
                    continue  # distrusted peer

                behavior = ObservedBehavior(
                    behavior_id=entry.entry_id,
                    source_infant=source,
                    behavior_type=behavior_type,
                    context=meta.get("context", {}),
                    outcome=meta.get("outcome", {}),
                    timestamp=entry.timestamp,
                    tags=meta.get("tags", []),
                )
                behaviors.append(behavior)

                # Record in global observation database
                self.__class__._observed_behaviors[entry.entry_id] = behavior

                # Add to imitation candidates if outcome positive
                outcome = behavior.outcome
                if isinstance(outcome, dict) and outcome.get("success", False):
                    self._imitation_candidates.append(entry.entry_id)

                # Strengthen bond with successful interaction peer
                self._update_bond(source, success=True)

            # Decay old bonds
            self._decay_bonds()
            return behaviors

    def _update_bond(self, peer_id: str, success: bool) -> None:
        """Create or update social bond with peer."""
        with self.__class__._lock:
            bond = self._social_bonds.get(peer_id)
            if bond is None:
                bond = SocialBond(peer_id=peer_id, trust=0.5, interactions=0)
                self._social_bonds[peer_id] = bond

            bond.interactions += 1
            bond.last_interaction = time.time()
            delta = 0.05 if success else -0.02
            bond.trust = max(0.0, min(1.0, bond.trust + delta))

    def _decay_bonds(self) -> None:
        """Apply time-based decay to bond trust for inactive peers."""
        now = time.time()
        decay_interval = 3600.0  # 1 hour
        with self.__class__._lock:
            for bond in self._social_bonds.values():
                inactive = now - bond.last_interaction
                if inactive > decay_interval:
                    decay = self.BOND_DECAY_RATE * (inactive / decay_interval)
                    bond.trust = max(0.0, bond.trust - decay)

    # -------------------------------------------------------------------------
    # Internal: Imitation
    # -------------------------------------------------------------------------

    def _imitate_behavior(self, behavior_id: str) -> dict[str, Any]:
        """
        Attempt to replicate an observed behavior.

        Success probability depends on:
        - Source peer trust level (higher trust → higher success chance)
        - Behavioral complexity (context size)
        - Value alignment with source (shared values → easier imitation)
        """
        with self.__class__._lock:
            behavior = self.__class__._observed_behaviors.get(behavior_id)
            if behavior is None:
                return {"status": "error", "error": "behavior not found"}

            peer_bond = self._social_bonds.get(behavior.source_infant)
            base_prob = self.IMITATION_SUCCESS_RATE
            trust_bonus = (peer_bond.trust - 0.5) * 0.4 if peer_bond else 0.0
            success_prob = min(0.95, base_prob + trust_bonus)

            # Simulate imitation outcome (in full impl would actually replicate strategy)
            import random
            success = random.random() < success_prob

            # Update bond based on imitation outcome
            self._update_bond(behavior.source_infant, success)

        self._last_execution = time.time()
        self._execution_count += 1

        return {
            "status": "imitated" if success else "imitation_failed",
            "behavior_id": behavior_id,
            "source_infant": behavior.source_infant,
            "behavior_type": behavior.behavior_type,
            "trust_bonus": round(trust_bonus, 3),
            "adaptation_note": "adapted to local context" if success else "strategy incompatible",
            "imitation_cost": 5.0,
        }

    # -------------------------------------------------------------------------
    # Internal: Bond Strengthening
    # -------------------------------------------------------------------------

    def _strengthen_bond(self, peer_id: str) -> dict[str, Any]:
        """
        Explicitly strengthen social bond with a peer.

        Costs energy but increases trust ceiling and future collaboration success rate.
        """
        with self.__class__._lock:
            bond = self._social_bonds.get(peer_id)
            if bond is None:
                bond = SocialBond(peer_id=peer_id, trust=0.5)
                self._social_bonds[peer_id] = bond

            bond.trust = min(1.0, bond.trust + 0.1)
            bond.interactions += 1
            bond.last_interaction = time.time()

        self._last_execution = time.time()
        self._execution_count += 1

        return {
            "status": "bond_strengthened",
            "peer_id": peer_id,
            "new_trust": round(bond.trust, 3),
            "bond_cost": 2.0,
        }
