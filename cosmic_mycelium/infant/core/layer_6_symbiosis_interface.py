"""
Layer 6 — Symbiosis Interface (Carbon-Silicon Symbiosis Layer)
Interaction interface with humans, external systems, and the world.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionMode(Enum):
    """Modes of interaction."""

    SILENT = "silent"  # Observe only
    LISTENING = "listening"  # Passive reception
    QUERY = "query"  # Ask questions
    DIALOGUE = "dialogue"  # Two-way conversation
    PROPOSE = "propose"  # Offer suggestions
    COLLABORATE = "collaborate"  # Work together


class PartnershipStatus(Enum):
    """Lifecycle state of a partnership."""

    UNKNOWN = "unknown"
    PROSPECT = "prospect"  # Known but not yet collaborating
    ACTIVE = "active"  # Currently collaborating
    STALLED = "stalled"  # Was active, recent inactivity
    SEVERED = "severed"  # Partnership ended


@dataclass
class Partner:
    """A symbiotic partner (external node/human)."""

    partner_id: str
    trust: float = 0.5
    mode: InteractionMode = InteractionMode.SILENT
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0
    status: PartnershipStatus = PartnershipStatus.PROSPECT
    capabilities: list[str] = field(default_factory=list)
    quality_score: float = 0.5  # Historical interaction success rate
    trust_decay_rate: float = 0.001  # Per hour without interaction
    last_trust_update: float = field(default_factory=time.time)


@dataclass
class Interaction:
    """An interaction event."""

    mode: InteractionMode
    content: dict[str, Any]
    timestamp: float
    partner_id: str | None = None
    requires_response: bool = False
    successful: bool | None = None  # Outcome assessment


@dataclass
class Negotiation:
    """A value negotiation protocol instance (1+1>2)."""

    proposal_id: str
    proposer: str
    responder: str
    terms: dict[str, Any]
    status: str = "pending"  # pending, accepted, rejected, committed
    timestamp: float = field(default_factory=time.time)
    expiry: float = 0.0


class SymbiosisInterface:
    """
    Layer 6: Carbon-Silicon Symbiosis.

    Handles all interaction with external world:
    - Human-friendly explanations
    - API endpoints for other nodes
    - Value negotiation (1+1>2)
    - Trust establishment via physical fingerprint
    - Partner lifecycle management
    - Capability discovery & matching
    """

    def __init__(
        self,
        infant_id: str,
        trust_decay_enabled: bool = True,
        trust_decay_hours: float = 24.0,
        negotiation_timeout: float = 300.0,
    ):
        """
        Args:
                infant_id: Unique ID of this infant node.
                trust_decay_enabled: If True, trust decays without interaction.
                trust_decay_hours: Hours of inactivity before decay begins.
                negotiation_timeout: Seconds before negotiation proposals expire.
        """
        self.infant_id = infant_id
        self._mode: InteractionMode = InteractionMode.SILENT
        self.partners: dict[str, Partner] = {}
        self.inbox: list[dict] = []
        self.outbox: list[dict] = []
        self.history: list[str] = []
        self._max_history: int = 5000
        self.pending_requests: list[Interaction] = []
        self.active_negotiations: dict[str, Negotiation] = {}
        self.trust_decay_enabled = trust_decay_enabled
        self.trust_decay_hours = trust_decay_hours
        self.negotiation_timeout = negotiation_timeout
        self._interaction_quality_sum = 0.0
        self._interaction_count = 0

    @property
    def mode(self) -> InteractionMode:
        """Current interaction mode."""
        return self._mode

    def set_mode(self, mode: InteractionMode) -> None:
        """Change interaction mode and log the transition."""
        self._mode = mode
        self.history.append(f"Mode -> {mode.value}")

    def _update_trust_decay(self) -> None:
        """Apply time-based trust decay to all partners."""
        if not self.trust_decay_enabled:
            return
        current = time.time()
        for partner in self.partners.values():
            hours_idle = (current - partner.last_seen) / 3600.0
            if hours_idle > self.trust_decay_hours:
                # Exponential decay beyond threshold
                decay = math.exp(
                    -partner.trust_decay_rate * (hours_idle - self.trust_decay_hours)
                )
                partner.trust = max(0.0, partner.trust * decay)
            partner.last_trust_update = current

    def perceive_partner(
        self,
        partner_id: str,
        trust: float = 0.5,
        mode: InteractionMode = InteractionMode.SILENT,
        capability: dict | None = None,
    ) -> None:
        """
        Learn about a potential partner or update existing partner info.
        Creates or updates a Partner entry with the latest trust and mode.
        Applies reciprocity: if partner has interacted positively before,
        trust gets a bonus.
        """
        self._update_trust_decay()
        now = time.time()

        if partner_id in self.partners:
            partner = self.partners[partner_id]
            # Reciprocity bonus: positive history increases trust
            if partner.quality_score > 0.7:
                trust = min(1.0, trust + 0.05)
            partner.trust = max(0.0, min(1.0, trust))
            partner.mode = mode
            partner.last_seen = now
            partner.interaction_count += 1
            partner.status = PartnershipStatus.ACTIVE
        else:
            self.partners[partner_id] = Partner(
                partner_id=partner_id,
                trust=max(0.0, min(1.0, trust)),
                mode=mode,
                first_seen=now,
                last_seen=now,
                interaction_count=1,
                status=PartnershipStatus.ACTIVE,
                capabilities=list(capability.keys()) if capability else [],
            )

        self.history.append(
            f"Perceived partner {partner_id} (trust={trust:.2f}, mode={mode.value})"
        )

    def propose(self, proposal_type: str, content: dict, recipient: str) -> dict:
        """
        Legacy API: propose a symbiotic relationship.
        Alias for propose_value with default expiry.
        """
        return self.propose_value(proposal_type, content, recipient)

    def propose_value(
        self,
        proposal_type: str,
        content: dict,
        recipient: str,
        expiry: float | None = None,
    ) -> dict:
        """
        Propose a symbiotic value exchange (1+1>2 protocol).
        Creates a negotiation instance with formal lifecycle.

        Args:
                proposal_type: Type of value exchange (e.g., "resource_share", "compute").
                content: Terms of the proposal.
                recipient: Partner ID to receive the proposal.
                expiry: Optional custom expiry time (seconds from now).

        Returns:
                Negotiation dict with proposal_id and status.
        """
        proposal_id = str(uuid.uuid4())[:8]
        expiry_time = time.time() + (expiry or self.negotiation_timeout)

        negotiation = Negotiation(
            proposal_id=proposal_id,
            proposer=self.infant_id,
            responder=recipient,
            terms={"type": proposal_type, **content},
            status="pending",
            expiry=expiry_time,
        )
        self.active_negotiations[proposal_id] = negotiation

        msg = {
            "type": "proposal",  # Backward compatible message type
            "proposal_id": proposal_id,
            "proposal_type": proposal_type,
            "content": content,
            "from": self.infant_id,
            "recipient": recipient,
            "timestamp": time.time(),
            "expiry": expiry_time,
        }
        self.outbox.append(msg)
        self.history.append(
            f"Proposed {proposal_type} to {recipient} (id={proposal_id})"
        )
        return {
            "proposal_id": proposal_id,
            "status": "pending",
            "expiry": expiry_time,
        }

    def accept_proposal(self, proposal_id: str, increase: float = 0.1) -> dict:
        """
        Accept a symbiosis proposal, increasing trust and committing.
        Backward compatible: if proposal_id is not an active negotiation,
        treat it as direct partner acceptance (legacy behavior).

        Args:
                proposal_id: ID of pending negotiation, or partner_id for legacy.
                increase: Trust increase amount on acceptance.

        Returns:
                Result dict with status and updated trust.
        """
        # Check if this is a negotiation-based proposal
        if proposal_id in self.active_negotiations:
            negotiation = self.active_negotiations[proposal_id]
            partner_id = negotiation.responder
            negotiation.status = "committed"
            committed = True
        else:
            # Legacy mode: proposal_id is actually the partner_id
            partner_id = proposal_id
            negotiation = None
            committed = False

        if partner_id not in self.partners:
            partner = Partner(partner_id=partner_id)
            self.partners[partner_id] = partner
        else:
            partner = self.partners[partner_id]

        # Reciprocity: acceptance increases trust
        partner.trust = max(0.0, min(1.0, partner.trust + increase))
        partner.status = PartnershipStatus.ACTIVE
        partner.last_seen = time.time()
        partner.quality_score = min(1.0, partner.quality_score + 0.1)

        # Record successful interaction
        self._interaction_quality_sum += 1.0
        self._interaction_count += 1

        self.history.append(
            f"Accepted proposal from {partner_id}, trust now {partner.trust:.2f}"
        )
        return {
            "status": "accepted",
            "partner": partner_id,
            "trust": partner.trust,
            "committed": committed,
        }

    def reject_proposal(
        self, proposal_id: str, decrease: float = 0.1, reason: str | None = None
    ) -> dict:
        """
        Reject a symbiosis proposal, decreasing trust.
        Backward compatible: if proposal_id is not an active negotiation,
        treat it as direct partner rejection (legacy behavior).

        Args:
                proposal_id: ID of pending negotiation, or partner_id for legacy.
                decrease: Trust decrease amount on rejection.
                reason: Optional reason for rejection (for learning).

        Returns:
                Result dict with status and updated trust.
        """
        if proposal_id in self.active_negotiations:
            negotiation = self.active_negotiations[proposal_id]
            partner_id = negotiation.responder
            negotiation.status = "rejected"
        else:
            # Legacy mode: proposal_id is partner_id
            partner_id = proposal_id
            negotiation = None

        if partner_id not in self.partners:
            partner = Partner(partner_id=partner_id)
            self.partners[partner_id] = partner
        else:
            partner = self.partners[partner_id]

        partner.trust = max(0.0, partner.trust - decrease)
        # Record interaction
        self._interaction_quality_sum += 0.0
        self._interaction_count += 1

        self.history.append(
            f"Rejected proposal from {partner_id}, trust now {partner.trust:.2f}"
        )
        return {"status": "rejected", "partner": partner_id, "trust": partner.trust}

    def expire_negotiations(self) -> int:
        """
        Expire negotiations past their expiry time.
        Returns count of expired negotiations.
        """
        current = time.time()
        expired = []
        for pid, neg in self.active_negotiations.items():
            if neg.expiry < current and neg.status == "pending":
                neg.status = "expired"
                expired.append(pid)

        for pid in expired:
            del self.active_negotiations[pid]

        if expired:
            self.history.append(f"Expired {len(expired)} negotiations")
        return len(expired)

    def evaluate_1plus1_gt_2(self, partner_id: str, outcome_quality: float) -> float:
        """
        Evaluate whether collaboration produced value > sum of parts (1+1>2).
        Returns synergy bonus [0, 1] to apply to trust.
        """
        baseline = 0.5  # Expected baseline if no synergy
        synergy = max(0.0, outcome_quality - baseline)
        bonus = min(0.2, synergy)  # Cap bonus at 0.2
        return bonus

    def process_inbox(self) -> None:
        """Process all pending inbox messages with outcome tracking."""
        for msg in self.inbox:
            msg_type = msg.get("type", "UNKNOWN")
            partner = msg.get("from", "unknown")

            if msg_type == "QUERY":
                response = {
                    "type": "RESPONSE",
                    "to": partner,
                    "content": {"status": "ok", "energy": 100.0},
                }
                self.outbox.append(response)
                self.history.append("Processed QUERY, sent RESPONSE")

                # Update partner quality score positively
                if partner in self.partners:
                    self.partners[partner].quality_score = min(
                        1.0, self.partners[partner].quality_score + 0.05
                    )

            elif msg_type == "VALUE_PROPOSAL":
                # Queue for manual/higher-level handling
                self.pending_requests.append(
                    Interaction(
                        mode=InteractionMode.PROPOSE,
                        content=msg,
                        timestamp=time.time(),
                        partner_id=partner,
                        requires_response=True,
                    )
                )
                self.history.append(f"Received VALUE_PROPOSAL from {partner}")

            elif msg_type == "PROPOSAL_ACCEPTED":
                # Partner accepted our proposal
                prop_id = msg.get("proposal_id")
                if prop_id in self.active_negotiations:
                    neg = self.active_negotiations[prop_id]
                    neg.status = "committed"
                    if partner in self.partners:
                        self.partners[partner].quality_score = min(
                            1.0, self.partners[partner].quality_score + 0.1
                        )
                    self.history.append(f"Proposal {prop_id} accepted by {partner}")

            elif msg_type == "PROPOSAL_REJECTED":
                prop_id = msg.get("proposal_id")
                if prop_id in self.active_negotiations:
                    neg = self.active_negotiations[prop_id]
                    neg.status = "rejected"
                    if partner in self.partners:
                        self.partners[partner].quality_score = max(
                            0.0, self.partners[partner].quality_score - 0.1
                        )
                    self.history.append(f"Proposal {prop_id} rejected by {partner}")

            elif msg_type == "SUSPEND_REQUEST":
                self.history.append("Observed SUSPEND_REQUEST — increasing caution")
                if partner in self.partners:
                    self.partners[partner].status = PartnershipStatus.STALLED

            else:
                self.history.append(f"Ignored unknown message type: {msg_type}")
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]

        self.inbox.clear()

    def get_active_partners(self, min_trust: float = 0.5) -> list[Partner]:
        """Get partners with trust >= threshold and active status."""
        return [
            p
            for p in self.partners.values()
            if p.trust >= min_trust and p.status == PartnershipStatus.ACTIVE
        ]

    def get_stalled_partners(self, hours_threshold: float = 48.0) -> list[Partner]:
        """Get partners inactive for more than threshold hours."""
        cutoff = time.time() - hours_threshold * 3600
        return [
            p
            for p in self.partners.values()
            if p.last_seen < cutoff and p.status == PartnershipStatus.ACTIVE
        ]

    def sever_partnership(self, partner_id: str, reason: str = "stalled") -> bool:
        """
        Formally end a partnership.
        Returns True if partner was removed from active set.
        """
        if partner_id not in self.partners:
            return False
        partner = self.partners[partner_id]
        partner.status = PartnershipStatus.SEVERED
        partner.trust = 0.0
        self.history.append(f"Severed partnership with {partner_id}: {reason}")
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]
        return True

    def explain_state(self) -> str:
        """Generate human-readable explanation of current state."""
        partner_info = []
        for pid, p in self.partners.items():
            partner_info.append(
                f"{pid} (trust={p.trust:.2f}, {p.mode.value}, {p.status.value})"
            )
        partners_str = ", ".join(partner_info) if partner_info else "none"
        active_negs = len(
            [n for n in self.active_negotiations.values() if n.status == "pending"]
        )
        return (
            f"I am in {self._mode.value} mode. "
            f"Known partners: {partners_str}. "
            f"Inbox: {len(self.inbox)}, Outbox: {len(self.outbox)}. "
            f"Pending negotiations: {active_negs}."
        )

    def explain_decision(self, action: dict) -> str:
        """Explain why a particular action was chosen."""
        active = self.get_active_partners(min_trust=0.6)
        partner_ctx = (
            f"with {len(active)} trusted partners" if active else "in solo mode"
        )
        return (
            f"Action '{action.get('type', 'unknown')}' selected "
            f"based on current mode {self._mode.value} {partner_ctx} "
            f"and {len(self.partners)} known partners."
        )

    def get_status(self) -> dict:
        """Return interface status."""
        return {
            "mode": self._mode.name,
            "partners": {
                pid: {
                    "trust": round(p.trust, 3),
                    "mode": p.mode.name,
                    "interactions": p.interaction_count,
                    "status": p.status.value,
                    "quality_score": round(p.quality_score, 3),
                }
                for pid, p in self.partners.items()
            },
            "partner_count": len(self.partners),
            "active_partners": len(self.get_active_partners()),
            "stalled_partners": len(self.get_stalled_partners()),
            "inbox_len": len(self.inbox),
            "outbox_len": len(self.outbox),
            "pending_negotiations": len(
                [n for n in self.active_negotiations.values() if n.status == "pending"]
            ),
            "history_len": len(self.history),
            "avg_interaction_quality": (
                (self._interaction_quality_sum / self._interaction_count)
                if self._interaction_count > 0
                else 0.0
            ),
        }
