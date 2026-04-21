"""
Layer 6 — Symbiosis Interface Tests
Tests partner perception, proposal handling, human/machine explanations, mode management.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.infant.core.layer_6_symbiosis_interface import (
    SymbiosisInterface,
    InteractionMode,
    Partner,
)


class TestSymbiosisInitialization:
    """Tests for interface construction."""

    def test_default_mode_is_silent(self):
        """Initial mode is SILENT (no external interaction)."""
        interface = SymbiosisInterface("node-1")
        assert interface.mode == InteractionMode.SILENT

    def test_partners_starts_empty(self):
        """No partners initially."""
        interface = SymbiosisInterface("node-1")
        assert len(interface.partners) == 0

    def test_inbox_outbox_empty(self):
        """Message queues start empty."""
        interface = SymbiosisInterface("node-1")
        assert len(interface.inbox) == 0
        assert len(interface.outbox) == 0


class TestModeManagement:
    """Tests for mode transitions."""

    def test_set_mode_listening(self):
        """set_mode() changes mode to LISTENING."""
        interface = SymbiosisInterface("node-1")
        interface.set_mode(InteractionMode.LISTENING)
        assert interface.mode == InteractionMode.LISTENING

    def test_set_mode_dialogue(self):
        """set_mode() changes mode to DIALOGUE."""
        interface = SymbiosisInterface("node-1")
        interface.set_mode(InteractionMode.DIALOGUE)
        assert interface.mode == InteractionMode.DIALOGUE

    def test_set_mode_silent(self):
        """set_mode() changes mode back to SILENT."""
        interface = SymbiosisInterface("node-1")
        interface.set_mode(InteractionMode.DIALOGUE)
        interface.set_mode(InteractionMode.SILENT)
        assert interface.mode == InteractionMode.SILENT

    def test_mode_transition_logs_event(self):
        """Mode changes are logged in internal history."""
        interface = SymbiosisInterface("node-1")
        interface.set_mode(InteractionMode.DIALOGUE)
        interface.set_mode(InteractionMode.SILENT)

        assert len(interface.history) >= 2


class TestPartnerPerception:
    """Tests for perceive_partner()."""

    def test_perceive_partner_registers_new_partner(self):
        """Unknown partner creates Partner entry."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("partner-42", trust=0.7, mode=InteractionMode.LISTENING)

        assert "partner-42" in interface.partners
        p = interface.partners["partner-42"]
        assert p.trust == pytest.approx(0.7)
        assert p.mode == InteractionMode.LISTENING

    def test_perceive_partner_updates_existing(self):
        """Perceiving same partner again updates trust and mode."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("known", trust=0.5, mode=InteractionMode.SILENT)
        interface.perceive_partner("known", trust=0.8, mode=InteractionMode.DIALOGUE)

        p = interface.partners["known"]
        assert p.trust == pytest.approx(0.8)
        assert p.mode == InteractionMode.DIALOGUE

    def test_perceive_partner_records_last_seen(self):
        """last_seen timestamp is updated."""
        import time
        interface = SymbiosisInterface("node-1")
        before = time.time()
        interface.perceive_partner("p", trust=0.5)
        after = time.time()

        p = interface.partners["p"]
        assert before <= p.last_seen <= after


class TestProposalHandling:
    """Tests for propose() and accept_proposal()."""

    def test_propose_creates_outbox_message(self):
        """propose() adds message to outbox."""
        interface = SymbiosisInterface("node-1")
        interface.propose(
            proposal_type="energy_share",
            content={"amount": 10.0},
            recipient="node-2",
        )

        assert len(interface.outbox) == 1
        msg = interface.outbox[0]
        assert msg["type"] == "proposal"
        assert msg["content"]["amount"] == 10.0

    def test_propose_targets_specific_recipient(self):
        """Proposal has specific recipient (not broadcast)."""
        interface = SymbiosisInterface("node-1")
        interface.propose("share", {"x": 1}, recipient="node-X")
        assert interface.outbox[0]["recipient"] == "node-X"

    def test_accept_proposal_updates_partner_trust(self):
        """accept_proposal increases partner trust."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.4, mode=InteractionMode.LISTENING)
        interface.accept_proposal("p", increase=0.2)

        assert interface.partners["p"].trust == pytest.approx(0.6)

    def test_reject_proposal_decreases_trust(self):
        """reject_proposal decreases partner trust."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.6)
        interface.reject_proposal("p", decrease=0.1)

        assert interface.partners["p"].trust == pytest.approx(0.5)

    def test_trust_clamped_between_0_1(self):
        """Trust values stay in [0.0, 1.0] range."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.9)
        interface.accept_proposal("p", increase=0.3)  # Would go to 1.2
        assert interface.partners["p"].trust == 1.0

        interface.reject_proposal("p", decrease=0.5)  # 1.0 - 0.5 = 0.5
        assert interface.partners["p"].trust == 0.5

        # Clamp lower bound
        interface.reject_proposal("p", decrease=0.6)  # 0.5 - 0.6 = -0.1
        assert interface.partners["p"].trust == 0.0


class TestMessageProcessing:
    """Tests for process_inbox()."""

    def test_process_inbox_handles_query(self):
        """QUERY messages generate response and log."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "QUERY", "content": "status?"}]

        interface.process_inbox()

        assert len(interface.outbox) == 1
        assert interface.outbox[0]["type"] == "RESPONSE"

    def test_process_inbox_handles_suspend_request(self):
        """SUSPEND_REQUEST triggers internal caution increase."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "SUSPEND_REQUEST", "from": "node-2"}]

        interface.process_inbox()

        assert any("suspend" in e.lower() for e in interface.history)

    def test_process_inbox_handles_unknown_type(self):
        """Unknown message types are logged and ignored."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "UNKNOWN", "data": 123}]

        interface.process_inbox()

        assert len(interface.outbox) == 0

    def test_inbox_cleared_after_processing(self):
        """process_inbox clears the inbox."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "QUERY"}]

        interface.process_inbox()

        assert len(interface.inbox) == 0


class TestExplanationFormatters:
    """Tests for explain_state() and explain_decision()."""

    def test_explain_state_returns_string(self):
        """explain_state() returns human-readable string."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.7)
        explanation = interface.explain_state()
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_explain_state_contains_partner_info(self):
        """Explanation includes partner trust and mode."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.8, mode=InteractionMode.DIALOGUE)
        explanation = interface.explain_state()
        assert "partner" in explanation.lower() or "trust" in explanation.lower()

    def test_explain_decision_returns_string(self):
        """explain_decision() returns human-readable string."""
        interface = SymbiosisInterface("node-1")
        explanation = interface.explain_decision({"action": "move"})
        assert isinstance(explanation, str)
        assert len(explanation) > 0


class TestStatus:
    """Tests for get_status()."""

    def test_status_includes_mode(self):
        """Status includes current mode."""
        interface = SymbiosisInterface("node-1")
        interface.set_mode(InteractionMode.DIALOGUE)
        status = interface.get_status()
        assert status["mode"] == "DIALOGUE"

    def test_status_includes_partner_count(self):
        """Status reports number of known partners."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p1", trust=0.5)
        interface.perceive_partner("p2", trust=0.6)
        status = interface.get_status()
        assert status["partner_count"] == 2

    def test_status_includes_queue_lengths(self):
        """Status reports inbox/outbox lengths."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [1, 2, 3]
        interface.outbox = [{"a": 1}]
        status = interface.get_status()
        assert status["inbox_len"] == 3
        assert status["outbox_len"] == 1

    def test_status_includes_partner_details(self):
        """Status contains partner details when partners exist."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.9, mode=InteractionMode.LISTENING)
        status = interface.get_status()
        assert "partners" in status
        assert "p" in status["partners"]
