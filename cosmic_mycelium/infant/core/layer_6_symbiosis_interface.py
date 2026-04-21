"""
Layer 6 — Symbiosis Interface (Carbon-Silicon Symbiosis Layer)
Interaction interface with humans, external systems, and the world.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time


class InteractionMode(Enum):
    """Modes of interaction."""
    SILENT = "silent"       # Observe only
    LISTENING = "listening" # Passive reception
    QUERY = "query"         # Ask questions
    DIALOGUE = "dialogue"   # Two-way conversation
    PROPOSE = "propose"     # Offer suggestions
    COLLABORATE = "collaborate"  # Work together


@dataclass
class Partner:
    """A symbiotic partner (external node/human)."""
    partner_id: str
    trust: float = 0.5
    mode: InteractionMode = InteractionMode.SILENT
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0


@dataclass
class Interaction:
    """An interaction event."""
    mode: InteractionMode
    content: Dict[str, Any]
    timestamp: float
    partner_id: Optional[str] = None
    requires_response: bool = False


class SymbiosisInterface:
    """
    Layer 6: Carbon-Silicon Symbiosis.

    Handles all interaction with external world:
    - Human-friendly explanations
    - API endpoints for other nodes
    - Value negotiation (1+1>2)
    - Trust establishment via physical fingerprint
    """

    def __init__(self, infant_id: str):
        self.infant_id = infant_id
        self._mode: InteractionMode = InteractionMode.SILENT
        self.partners: Dict[str, Partner] = {}
        self.inbox: List[Dict] = []
        self.outbox: List[Dict] = []
        self.history: List[str] = []
        self.pending_requests: List[Interaction] = []

    @property
    def mode(self) -> InteractionMode:
        """Current interaction mode."""
        return self._mode

    def set_mode(self, mode: InteractionMode) -> None:
        """Change interaction mode and log the transition."""
        self._mode = mode
        self.history.append(f"Mode -> {mode.value}")

    def perceive_partner(self, partner_id: str, trust: float = 0.5,
                        mode: InteractionMode = InteractionMode.SILENT,
                        capability: Optional[Dict] = None) -> None:
        """
        Learn about a potential partner or update existing partner info.
        Creates or updates a Partner entry with the latest trust and mode.
        """
        now = time.time()
        if partner_id in self.partners:
            partner = self.partners[partner_id]
            partner.trust = max(0.0, min(1.0, trust))
            partner.mode = mode
            partner.last_seen = now
            partner.interaction_count += 1
        else:
            self.partners[partner_id] = Partner(
                partner_id=partner_id,
                trust=max(0.0, min(1.0, trust)),
                mode=mode,
                first_seen=now,
                last_seen=now,
                interaction_count=1,
            )
        self.history.append(f"Perceived partner {partner_id} (trust={trust:.2f}, mode={mode.value})")

    def propose(self, proposal_type: str, content: Dict, recipient: str) -> Dict:
        """Propose a symbiotic relationship (1+1>2)."""
        msg = {
            "type": "proposal",
            "proposal_type": proposal_type,
            "content": content,
            "from": self.infant_id,
            "recipient": recipient,
            "timestamp": time.time(),
        }
        self.outbox.append(msg)
        self.history.append(f"Proposed {proposal_type} to {recipient}")
        return msg

    def accept_proposal(self, partner_id: str, increase: float = 0.1) -> Dict:
        """Accept a symbiosis proposal, increasing trust."""
        if partner_id not in self.partners:
            partner = Partner(partner_id=partner_id)
            self.partners[partner_id] = partner
        else:
            partner = self.partners[partner_id]
        partner.trust = max(0.0, min(1.0, partner.trust + increase))
        self.history.append(f"Accepted proposal from {partner_id}, trust now {partner.trust:.2f}")
        return {"status": "accepted", "partner": partner_id, "trust": partner.trust}

    def reject_proposal(self, partner_id: str, decrease: float = 0.1) -> Dict:
        """Reject a symbiosis proposal, decreasing trust."""
        if partner_id not in self.partners:
            partner = Partner(partner_id=partner_id)
            self.partners[partner_id] = partner
        else:
            partner = self.partners[partner_id]
        partner.trust = max(0.0, partner.trust - decrease)
        self.history.append(f"Rejected proposal from {partner_id}, trust now {partner.trust:.2f}")
        return {"status": "rejected", "partner": partner_id, "trust": partner.trust}

    def process_inbox(self) -> None:
        """Process all pending inbox messages."""
        for msg in self.inbox:
            msg_type = msg.get("type", "UNKNOWN")
            if msg_type == "QUERY":
                response = {
                    "type": "RESPONSE",
                    "to": msg.get("from"),
                    "content": {"status": "ok", "energy": 100.0},
                }
                self.outbox.append(response)
                self.history.append("Processed QUERY, sent RESPONSE")
            elif msg_type == "SUSPEND_REQUEST":
                self.history.append("Observed SUSPEND_REQUEST — increasing caution")
            else:
                self.history.append(f"Ignored unknown message type: {msg_type}")
        self.inbox.clear()

    def explain_state(self) -> str:
        """Generate human-readable explanation of current state."""
        partner_info = []
        for pid, p in self.partners.items():
            partner_info.append(f"{pid} (trust={p.trust:.2f}, {p.mode.value})")
        partners_str = ", ".join(partner_info) if partner_info else "none"
        return (
            f"I am in {self._mode.value} mode. "
            f"Known partners: {partners_str}. "
            f"Inbox: {len(self.inbox)}, Outbox: {len(self.outbox)}."
        )

    def explain_decision(self, action: Dict) -> str:
        """Explain why a particular action was chosen."""
        return f"Action '{action.get('type', 'unknown')}' selected based on current mode {self._mode.value} and {len(self.partners)} known partners."

    def get_status(self) -> Dict:
        """Return interface status."""
        return {
            "mode": self._mode.name,  # Return uppercase enum name
            "partners": {
                pid: {
                    "trust": round(p.trust, 3),
                    "mode": p.mode.name,
                    "interactions": p.interaction_count,
                }
                for pid, p in self.partners.items()
            },
            "partner_count": len(self.partners),
            "inbox_len": len(self.inbox),
            "outbox_len": len(self.outbox),
            "history_len": len(self.history),
        }
