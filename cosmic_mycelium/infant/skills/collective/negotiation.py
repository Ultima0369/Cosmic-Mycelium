"""
NegotiationSkill — Value-based Inter-Infant Negotiation

Enables infants to negotiate resource sharing, task allocation, or proposal
support based on value vector alignment. Uses ValueAlignment.compute_distance()
to assess mutual benefit potential and generate fair offers.

Phase: Epic 2 (Skill Plugin System — Built-in Skills)
"""

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext, SkillExecutionError

if TYPE_CHECKING:
    from cosmic_mycelium.cluster.consensus import ValueAlignment


@dataclass
class NegotiationState:
    """
    Tracks a single negotiation session between two infants.

    Lifecycle:
    1. proposed — offer sent, awaiting response
    2. counter   — counter-offer sent
    3. accepted — agreement reached
    4. rejected  — negotiation terminated without agreement
    5. expired   — timeout without resolution
    """

    negotiation_id: str
    proposer: str
    responder: str
    offer: dict[str, float]  # value_vector adjustments offered
    status: str = "proposed"  # proposed, counter, accepted, rejected, expired
    rounds: int = 0
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)


class NegotiationSkill(InfantSkill):
    """
    Value-based negotiation skill for inter-infant coordination.

    Core principle (from consensus.py): "和而不同" — value resonance ≠ assimilation.
    Negotiation finds局部最大收益点 where both parties benefit without full alignment.

    Workflow:
    1. Proposer calls execute({"partner_id": X, "offer": {...}, "intent": "share"})
    2. Responder calls execute({"negotiation_id": Y, "accept": True/False, "counter": {...}})
    3. Skill converges when offer value distance < threshold or rounds exhausted.

    Configuration via execute params:
    - partner_id: str          — negotiating partner infant ID
    - offer: dict[str, float]  — proposed value vector adjustments
    - intent: str              — "share", "delegate", "collaborate"
    - accept: bool             — (responder) accept the offer
    - counter: dict            — (responder) counter-offer
    - negotiation_id: str      — (responder) ID of offer being responded to

    Dependencies:
    - value_alignment: ValueAlignment consensus module (injected at init)
    """

    name = "negotiation"
    version = "1.0.0"
    description = "Value-based negotiation for inter-infant coordination"
    dependencies = []  # components injected, not skill deps
    parallelism_policy = ParallelismPolicy.ISOLATED  # Sprint 5: thread-safe with class-level lock

    # Configuration constants
    MAX_ROUNDS = 3
    OFFER_TIMEOUT = 60.0  # seconds before proposal expires
    VALUE_DISTANCE_THRESHOLD = 0.3  # convergence threshold

    # Class-level shared negotiation table (all infants see same state)
    _negotiations: dict[str, NegotiationState] = {}
    _lock = threading.RLock()  # Sprint 5: protects class-level shared state

    def __init__(
        self,
        value_alignment: ValueAlignment | None = None,
        hic: Any | None = None,
    ):
        self.value_alignment = value_alignment
        self.hic = hic
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0
        self._cooldown: float = 10.0
        # Ensure class-level negotiations dict exists (fixture may have deleted it)
        if not hasattr(self.__class__, "_negotiations"):
            self.__class__._negotiations = {}

    # -------------------------------------------------------------------------
    # InfantSkill Protocol
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """Initialize skill and store infant ID."""
        self._initialized = True
        self._infant_id = context.infant_id

    def can_activate(self, context: SkillContext) -> bool:
        """
        Negotiation activation conditions:
        - Initialized
        - Energy >= 10 (negotiation overhead)
        - Cooldown elapsed since last execution
        """
        if not self._initialized:
            return False
        if context.energy_available < 10:
            return False
        now = time.time()
        if now - self._last_execution < self._cooldown:
            return False
        return True

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one negotiation step.

        Args:
            params:
                - partner_id: str        — partner infant ID (proposer)
                - offer: dict            — proposed value adjustments (proposer)
                - intent: str            — negotiation intent ("share", "delegate")
                - negotiation_id: str    — offer being responded to (responder)
                - accept: bool           — accept offer (responder)
                - counter: dict          — counter-offer (responder)

        Returns:
            {
                "status": "proposed" | "accepted" | "rejected" | "countered" | "cooldown" | "error",
                "negotiation_id": str,
                "partner_id": str | None,
                "mutual_benefit": float | None,
                "rounds": int,
                "energy_cost": float,
            }
        """
        if not self._initialized:
            raise SkillExecutionError("NegotiationSkill not initialized")

        now = time.time()
        partner_id = params.get("partner_id")
        offer = params.get("offer", {})
        intent = params.get("intent", "share")
        negotiation_id = params.get("negotiation_id")
        accept = params.get("accept", False)
        counter = params.get("counter")

        # Cooldown check
        if now - self._last_execution < self._cooldown:
            return {"status": "cooldown", "energy_cost": 0.5}

        # Clean up expired negotiations
        with self.__class__._lock:
            self._prune_expired()

        # Responder path: handle incoming offer
        if negotiation_id is not None:
            return self._respond_to_offer(negotiation_id, accept, counter, partner_id)

        # Proposer path: create new offer
        if not partner_id:
            return {"status": "error", "error": "partner_id required for new negotiation"}

        return self._propose_new(partner_id, offer, intent)

    def get_resource_usage(self) -> dict[str, float]:
        """Negotiation consumes moderate energy for value computation."""
        return {"energy_cost": 3.0, "duration_s": 0.05, "memory_mb": 2.0}

    def shutdown(self) -> None:
        """Cleanup negotiation state."""
        with self.__class__._lock:
            self.__class__._negotiations.clear()
        self._initialized = False

    def get_status(self) -> dict[str, Any]:
        """Return negotiation skill health."""
        with self.__class__._lock:
            negs = self.__class__._negotiations
            active = [n for n in negs.values() if n.status in ("proposed", "counter")]
            return {
                "name": self.name,
                "version": self.version,
                "initialized": self._initialized,
                "execution_count": self._execution_count,
                "last_execution": self._last_execution,
                "active_negotiations": len(active),
                "total_negotiations": len(negs),
            }

    # -------------------------------------------------------------------------
    # Internal: Proposer path
    # -------------------------------------------------------------------------

    def _propose_new(self, partner_id: str, offer: dict[str, float], intent: str) -> dict[str, Any]:
        """Create a new negotiation proposal."""
        with self.__class__._lock:
            # Calculate mutual benefit using own value vector + offer
            if self.hic is None or self.value_alignment is None:
                return {"status": "error", "error": "hic or value_alignment not available"}

            my_values = self.hic.value_vector
            # Simulate partner receiving offer: their values shift toward offer
            simulated_partner = dict(my_values)  # placeholder: in reality would query partner
            for k, v in offer.items():
                simulated_partner[k] = simulated_partner.get(k, 0.0) + v * 0.5  # partial adoption

            distance = self.value_alignment.compute_distance(my_values, simulated_partner)
            mutual_benefit = 1.0 - distance

            if mutual_benefit < 0.2:
                # Too divergent — negotiation unlikely to succeed
                return {
                    "status": "rejected",
                    "reason": "value_distance_too_large",
                    "distance": distance,
                    "energy_cost": 1.0,
                }

            # Create negotiation record
            neg_id = f"neg-{uuid.uuid4().hex[:8]}"
            state = NegotiationState(
                negotiation_id=neg_id,
                proposer=self._get_my_infant_id(),
                responder=partner_id,
                offer=offer,
                status="proposed",
                rounds=1,
            )
            self.__class__._negotiations[neg_id] = state

        self._last_execution = time.time()
        self._execution_count += 1

        return {
            "status": "proposed",
            "negotiation_id": neg_id,
            "partner_id": partner_id,
            "mutual_benefit": round(mutual_benefit, 3),
            "value_distance": round(distance, 3),
            "intent": intent,
            "energy_cost": 3.0,
        }

    # -------------------------------------------------------------------------
    # Internal: Responder path
    # -------------------------------------------------------------------------

    def _respond_to_offer(
        self,
        negotiation_id: str,
        accept: bool,
        counter: dict[str, float] | None,
        responder_id: str | None,
    ) -> dict[str, Any]:
        """Respond to an existing proposal."""
        with self.__class__._lock:
            state = self._negotiations.get(negotiation_id)
            if state is None:
                return {"status": "error", "error": "negotiation not found"}

            if state.status not in ("proposed", "counter"):
                return {"status": "error", "error": f"negotiation {state.status} cannot be responded to"}

            if accept:
                # Accept — convergence achieved
                state.status = "accepted"
                state.last_update = time.time()
                self._last_execution = time.time()
                self._execution_count += 1

                # Trigger workspace update via collective if available
                # (The actual proposal broadcast is handled by CollectiveIntelligence)

                return {
                    "status": "accepted",
                    "negotiation_id": negotiation_id,
                    "rounds": state.rounds,
                    "energy_cost": 1.0,
                }

            if counter is not None:
                # Counter-offer — continue negotiation
                state.offer = counter
                state.status = "counter"
                state.rounds += 1
                state.last_update = time.time()

                if state.rounds >= self.MAX_ROUNDS:
                    state.status = "rejected"
                    return {
                        "status": "rejected",
                        "reason": "max_rounds_exceeded",
                        "negotiation_id": negotiation_id,
                        "rounds": state.rounds,
                        "energy_cost": 1.5,
                    }

                self._last_execution = time.time()
                self._execution_count += 1

                return {
                    "status": "countered",
                    "negotiation_id": negotiation_id,
                    "rounds": state.rounds,
                    "energy_cost": 2.0,
                }

            # Plain reject
            state.status = "rejected"
            state.last_update = time.time()
            self._last_execution = time.time()
            self._execution_count += 1

            return {
                "status": "rejected",
                "negotiation_id": negotiation_id,
                "energy_cost": 1.0,
            }

    # -------------------------------------------------------------------------
    # Internal: Maintenance
    # -------------------------------------------------------------------------

    def _prune_expired(self) -> None:
        """Remove negotiations older than OFFER_TIMEOUT."""
        now = time.time()
        with self.__class__._lock:
            to_remove = [
                nid
                for nid, state in self.__class__._negotiations.items()
                if now - state.last_update > self.OFFER_TIMEOUT
                and state.status in ("proposed", "counter")
            ]
            for nid in to_remove:
                state = self.__class__._negotiations.pop(nid, None)
                if state:
                    state.status = "expired"

    def _get_my_infant_id(self) -> str:
        """Get this infant's ID from initialize context."""
        return getattr(self, "_infant_id", "unknown")
