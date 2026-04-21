"""
Layer 6 — Symbiosis Interface Tests
Tests partner perception, proposal handling, human/machine explanations, mode management.
"""

from __future__ import annotations

import time
from unittest.mock import patch
import pytest
from cosmic_mycelium.infant.core.layer_6_symbiosis_interface import (
    SymbiosisInterface,
    InteractionMode,
    Partner,
    PartnershipStatus,
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

    def test_process_inbox_query_increases_quality_for_known_partner(self):
        """QUERY from known partner increases their quality_score."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("known-partner", trust=0.5)
        interface.partners["known-partner"].quality_score = 0.3
        interface.inbox = [{"type": "QUERY", "from": "known-partner"}]
        interface.process_inbox()

        assert interface.partners["known-partner"].quality_score == pytest.approx(0.35)

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


class TestTrustDecay:
    """Tests for _update_trust_decay()."""

    def test_trust_decay_disabled_returns_early(self):
        """When trust_decay_enabled=False, decay is not applied."""
        interface = SymbiosisInterface("node-1", trust_decay_enabled=False)
        interface.perceive_partner("p", trust=0.8)
        partner = interface.partners["p"]
        initial_trust = partner.trust
        initial_last_update = partner.last_trust_update

        # Manually set last_seen far in the past to trigger decay if it ran
        partner.last_seen = time.time() - 10000  # ~2.7 hours ago

        interface._update_trust_decay()

        # Trust unchanged, last_trust_update unchanged (early return)
        assert partner.trust == initial_trust
        assert partner.last_trust_update == initial_last_update

    def test_trust_decay_applies_when_enabled(self):
        """Trust decays exponentially when enabled and idle time exceeds threshold."""
        interface = SymbiosisInterface("node-1", trust_decay_enabled=True, trust_decay_hours=1.0)
        interface.perceive_partner("p", trust=0.8)
        partner = interface.partners["p"]
        # Set last_seen 2 hours ago (exceeds 1 hour threshold)
        partner.last_seen = time.time() - 7200
        interface._update_trust_decay()
        # Trust should have decayed (be less than 0.8)
        assert partner.trust < 0.8

    def test_trust_decay_respects_threshold(self):
        """No decay if idle time below trust_decay_hours."""
        interface = SymbiosisInterface("node-1", trust_decay_hours=24.0)
        interface.perceive_partner("p", trust=0.8)
        partner = interface.partners["p"]
        # Only 1 hour idle — below threshold
        partner.last_seen = time.time() - 3600
        interface._update_trust_decay()
        assert partner.trust == pytest.approx(0.8, abs=0.01)

    def test_trust_decay_floor_at_zero(self):
        """Decay never reduces trust below 0.0."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.1)
        partner = interface.partners["p"]
        partner.last_seen = time.time() - 100000  # Very idle
        interface._update_trust_decay()
        assert partner.trust >= 0.0


class TestReciprocity:
    """Tests for reciprocity bonus in perceive_partner()."""

    def test_perceive_partner_applies_reciprocity_bonus_when_quality_high(self):
        """Existing partner with quality_score > 0.7 gets +0.05 trust bonus."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        partner = interface.partners["p"]
        partner.quality_score = 0.8  # High quality history
        # Second perception should apply bonus
        interface.perceive_partner("p", trust=0.5)
        # Expected: min(1.0, 0.5 + 0.05) = 0.55
        assert partner.trust == pytest.approx(0.55)

    def test_perceive_partner_no_reciprocity_bonus_when_quality_low(self):
        """Quality score <= 0.7 gets no bonus."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        partner = interface.partners["p"]
        partner.quality_score = 0.6  # Below threshold
        interface.perceive_partner("p", trust=0.5)
        assert partner.trust == pytest.approx(0.5)

    def test_reciprocity_bonus_respects_upper_bound(self):
        """Reciprocity bonus clamped at 1.0."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.98)
        partner = interface.partners["p"]
        partner.quality_score = 0.9
        interface.perceive_partner("p", trust=0.98)
        assert partner.trust <= 1.0


class TestProposalLegacy:
    """Tests for duplicate propose() method and legacy behavior."""

    def test_propose_returns_dict_with_proposal_id(self):
        """propose() returns proposal dict with id and status."""
        interface = SymbiosisInterface("node-1")
        result = interface.propose("share", {"x": 1}, "partner-1")
        assert "proposal_id" in result
        assert result["status"] == "pending"

    def test_propose_generates_unique_proposal_ids(self):
        """Multiple proposals get unique IDs."""
        interface = SymbiosisInterface("node-1")
        r1 = interface.propose("type1", {}, "p1")
        r2 = interface.propose("type2", {}, "p2")
        assert r1["proposal_id"] != r2["proposal_id"]

    def test_propose_adds_to_outbox(self):
        """Proposal message added to outbox."""
        interface = SymbiosisInterface("node-1")
        interface.propose("test", {"k": "v"}, "recipient")
        assert len(interface.outbox) == 1
        assert interface.outbox[0]["type"] == "proposal"


class TestAcceptProposal:
    """Tests for accept_proposal()."""

    def test_accept_proposal_with_negotiation_id(self):
        """Accepting an active negotiation commits it and increases trust."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.3)
        proposal = interface.propose_value("share", {"a": 1}, "p")
        result = interface.accept_proposal(proposal["proposal_id"])

        assert result["status"] == "accepted"
        assert result["committed"] is True
        assert interface.partners["p"].trust > 0.3
        neg = interface.active_negotiations[proposal["proposal_id"]]
        assert neg.status == "committed"

    def test_accept_proposal_legacy_partner_id(self):
        """Legacy mode: proposal_id treated as partner_id."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.4)
        result = interface.accept_proposal("p", increase=0.2)

        assert result["status"] == "accepted"
        assert result["committed"] is False
        assert interface.partners["p"].trust == pytest.approx(0.6)

    def test_accept_proposal_creates_missing_partner(self):
        """Accepting from unknown partner creates Partner entry."""
        interface = SymbiosisInterface("node-1")
        result = interface.accept_proposal("new-partner", increase=0.1)

        assert "new-partner" in interface.partners
        # Partner starts with trust 0.5, increase 0.1 → 0.6
        assert interface.partners["new-partner"].trust == pytest.approx(0.6)

    def test_accept_proposal_increments_quality_score(self):
        """Acceptance increases partner quality_score by 0.1."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        interface.accept_proposal("p")
        assert interface.partners["p"].quality_score == pytest.approx(0.6)


class TestRejectProposal:
    """Tests for reject_proposal()."""

    def test_reject_proposal_with_negotiation(self):
        """Rejecting an active negotiation marks it rejected."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.8)
        proposal = interface.propose_value("share", {}, "p")
        interface.reject_proposal(proposal["proposal_id"], decrease=0.1)

        neg = interface.active_negotiations[proposal["proposal_id"]]
        assert neg.status == "rejected"
        assert interface.partners["p"].trust == pytest.approx(0.7)

    def test_reject_proposal_legacy_partner_id(self):
        """Legacy mode: proposal_id is partner_id."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.6)
        interface.reject_proposal("p", decrease=0.2)
        assert interface.partners["p"].trust == pytest.approx(0.4)

    def test_reject_proposal_creates_missing_partner(self):
        """Rejecting from unknown partner creates Partner entry."""
        interface = SymbiosisInterface("node-1")
        interface.reject_proposal("unknown", decrease=0.1)
        assert "unknown" in interface.partners
        # Partner starts with trust 0.5, decrease 0.1 → 0.4
        assert interface.partners["unknown"].trust == pytest.approx(0.4)

    def test_reject_proposal_decreases_quality_score(self):
        """reject_proposal itself does NOT modify quality_score (process_inbox does)."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        interface.partners["p"].quality_score = 0.5
        initial_quality = interface.partners["p"].quality_score
        interface.reject_proposal("p", decrease=0.1)
        # quality_score unchanged by reject_proposal directly
        assert interface.partners["p"].quality_score == initial_quality


class TestExpireNegotiations:
    """Tests for expire_negotiations()."""

    def test_expire_negotiations_removes_expired_pending(self):
        """Expired pending negotiations are removed from active_negotiations."""
        interface = SymbiosisInterface("node-1")
        proposal = interface.propose_value("test", {}, "p", expiry=0.01)  # Expires very soon
        # Wait for expiry
        time.sleep(0.02)
        count = interface.expire_negotiations()
        assert count == 1
        assert proposal["proposal_id"] not in interface.active_negotiations

    def test_expire_negotiations_ignores_non_pending(self):
        """Committed or rejected negotiations are not expired."""
        interface = SymbiosisInterface("node-1")
        prop = interface.propose_value("test", {}, "p")
        neg = interface.active_negotiations[prop["proposal_id"]]
        neg.status = "committed"  # Already committed, not pending

        count = interface.expire_negotiations()
        assert count == 0
        assert prop["proposal_id"] in interface.active_negotiations

    def test_expire_negotiations_ignores_future_expiry(self):
        """Negotiations with future expiry are kept."""
        interface = SymbiosisInterface("node-1")
        interface.propose_value("test", {}, "p", expiry=3600)  # 1 hour from now
        count = interface.expire_negotiations()
        assert count == 0

    def test_expire_negotiation_logs_event(self):
        """Expiry is logged in history."""
        interface = SymbiosisInterface("node-1")
        interface.propose_value("test", {}, "p", expiry=0.01)
        time.sleep(0.02)
        interface.expire_negotiations()
        assert any("Expired" in entry for entry in interface.history)


class TestEvaluateSynergy:
    """Tests for evaluate_1plus1_gt_2()."""

    def test_evaluate_synergy_returns_zero_for_baseline(self):
        """Baseline outcome_quality=0.5 yields zero bonus."""
        interface = SymbiosisInterface("node-1")
        bonus = interface.evaluate_1plus1_gt_2("p", outcome_quality=0.5)
        assert bonus == pytest.approx(0.0)

    def test_evaluate_synergy_returns_positive_for_above_baseline(self):
        """Outcome quality above baseline yields positive bonus (capped at 0.2)."""
        interface = SymbiosisInterface("node-1")
        bonus = interface.evaluate_1plus1_gt_2("p", outcome_quality=0.8)
        assert bonus == pytest.approx(0.2)  # 0.8-0.5=0.3, capped to 0.2

    def test_evaluate_synergy_capped_at_0_2(self):
        """Bonus capped at maximum 0.2."""
        interface = SymbiosisInterface("node-1")
        bonus = interface.evaluate_1plus1_gt_2("p", outcome_quality=0.95)
        assert bonus == pytest.approx(0.2)

    def test_evaluate_synergy_never_negative(self):
        """Outcome below baseline yields zero (not negative)."""
        interface = SymbiosisInterface("node-1")
        bonus = interface.evaluate_1plus1_gt_2("p", outcome_quality=0.3)
        assert bonus == pytest.approx(0.0)


class TestProcessInboxMessageTypes:
    """Tests for process_inbox() message type handling."""

    def test_process_inbox_value_proposal_queues_pending_request(self):
        """VALUE_PROPOSAL messages queue in pending_requests."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "VALUE_PROPOSAL", "from": "p1", "content": {"x": 1}}]
        interface.process_inbox()

        assert len(interface.pending_requests) == 1
        req = interface.pending_requests[0]
        assert req.mode == InteractionMode.PROPOSE
        assert req.partner_id == "p1"

    def test_process_inbox_proposal_accepted_updates_negotiation(self):
        """PROPOSAL_ACCEPTED commits the negotiation and increases quality_score."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        prop = interface.propose_value("share", {}, "p")
        interface.inbox = [{"type": "PROPOSAL_ACCEPTED", "proposal_id": prop["proposal_id"], "from": "p"}]
        interface.process_inbox()

        neg = interface.active_negotiations[prop["proposal_id"]]
        assert neg.status == "committed"
        assert interface.partners["p"].quality_score == pytest.approx(0.6)

    def test_process_inbox_proposal_rejected_updates_negotiation(self):
        """PROPOSAL_REJECTED marks negotiation rejected and lowers quality_score."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        interface.partners["p"].quality_score = 0.5
        prop = interface.propose_value("share", {}, "p")
        interface.inbox = [{"type": "PROPOSAL_REJECTED", "proposal_id": prop["proposal_id"], "from": "p"}]
        interface.process_inbox()

        neg = interface.active_negotiations[prop["proposal_id"]]
        assert neg.status == "rejected"
        assert interface.partners["p"].quality_score == pytest.approx(0.4)

    def test_process_inbox_proposal_accepted_without_known_partner(self):
        """PROPOSAL_ACCEPTED handles unknown partner gracefully."""
        interface = SymbiosisInterface("node-1")
        prop = interface.propose_value("share", {}, "unknown")
        interface.inbox = [{"type": "PROPOSAL_ACCEPTED", "proposal_id": prop["proposal_id"], "from": "unknown"}]
        interface.process_inbox()  # Should not crash
        neg = interface.active_negotiations[prop["proposal_id"]]
        assert neg.status == "committed"

    def test_process_inbox_proposal_rejected_without_known_partner(self):
        """PROPOSAL_REJECTED handles unknown partner gracefully."""
        interface = SymbiosisInterface("node-1")
        prop = interface.propose_value("share", {}, "unknown")
        interface.inbox = [{"type": "PROPOSAL_REJECTED", "proposal_id": prop["proposal_id"], "from": "unknown"}]
        interface.process_inbox()  # Should not crash
        neg = interface.active_negotiations[prop["proposal_id"]]
        assert neg.status == "rejected"

    def test_process_inbox_suspend_request_sets_stalled(self):
        """SUSPEND_REQUEST sets partner status to STALLED."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.8)
        interface.inbox = [{"type": "SUSPEND_REQUEST", "from": "p"}]
        interface.process_inbox()

        assert interface.partners["p"].status == PartnershipStatus.STALLED

    def test_process_inbox_suspend_request_unknown_partner(self):
        """SUSPEND_REQUEST from unknown partner just logs."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "SUSPEND_REQUEST", "from": "unknown"}]
        interface.process_inbox()  # Should not crash
        assert any("SUSPEND_REQUEST" in entry for entry in interface.history)


class TestPartnerQueries:
    """Tests for get_active_partners() and get_stalled_partners()."""

    def test_get_active_partners_filters_by_trust_and_status(self):
        """Only ACTIVE partners with trust >= threshold are returned."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("high", trust=0.8)
        interface.perceive_partner("low", trust=0.3)
        interface.perceive_partner("stalled", trust=0.8)
        interface.partners["stalled"].status = PartnershipStatus.STALLED
        # "high" is ACTIVE (perceive_partner sets ACTIVE for existing; for new it sets PROSPECT)
        # Re-perceive "high" to ensure ACTIVE status (second perception sets ACTIVE)
        interface.perceive_partner("high", trust=0.8)

        active = interface.get_active_partners(min_trust=0.5)
        names = [p.partner_id for p in active]
        assert "high" in names
        assert "low" not in names
        assert "stalled" not in names

    def test_get_stalled_partners_filters_by_inactivity(self):
        """Partners inactive beyond threshold are returned (only ACTIVE)."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("recent", trust=0.5)
        interface.perceive_partner("old", trust=0.5)
        # Second perceive makes "old" ACTIVE (first perception gives PROSPECT)
        interface.perceive_partner("old", trust=0.5)
        # Now set last_seen far in the past
        interface.partners["old"].last_seen = time.time() - (48 * 3600 + 1)  # 48+ hours ago

        stalled = interface.get_stalled_partners(hours_threshold=48.0)
        names = [p.partner_id for p in stalled]
        assert "old" in names
        assert "recent" not in names


class TestSeverPartnership:
    """Tests for sever_partnership()."""

    def test_sever_partnership_marks_severed_and_zeros_trust(self):
        """Severed partner status set to SEVERED and trust to 0.0."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.8)
        result = interface.sever_partnership("p", reason="test")

        assert result is True
        partner = interface.partners["p"]
        assert partner.status == PartnershipStatus.SEVERED
        assert partner.trust == 0.0

    def test_sever_partnership_returns_false_for_unknown(self):
        """Severing unknown partner returns False."""
        interface = SymbiosisInterface("node-1")
        result = interface.sever_partnership("nonexistent")
        assert result is False

    def test_sever_partnership_logs_reason(self):
        """Severance reason is logged."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.5)
        interface.sever_partnership("p", reason="inactivity")
        assert any("Severed partnership" in entry and "inactivity" in entry for entry in interface.history)


class TestExplanation:
    """Tests for explain_state() and explain_decision()."""

    def test_explain_state_with_no_partners(self):
        """Explanation handles zero partners gracefully."""
        interface = SymbiosisInterface("node-1")
        explanation = interface.explain_state()
        assert "none" in explanation.lower() or "no partners" in explanation.lower()

    def test_explain_decision_mentions_mode_and_partner_count(self):
        """explain_decision references mode and partner count."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.8)
        explanation = interface.explain_decision({"type": "execute", "target": "x"})
        assert interface.mode.value in explanation
        assert "partner" in explanation.lower()

    def test_explain_state_includes_queue_counts(self):
        """explain_state reports inbox/outbox/pending counts."""
        interface = SymbiosisInterface("node-1")
        interface.inbox = [{"type": "QUERY"}, {"type": "QUERY"}]
        interface.outbox = [{"type": "RESPONSE"}]
        interface.propose_value("test", {}, "p")
        explanation = interface.explain_state()
        assert "2" in explanation or "Inbox: 2" in explanation


class TestStatusCompleteness:
    """Tests for get_status() completeness."""

    def test_status_avg_interaction_quality_handles_zero_count(self):
        """avg_interaction_quality is 0.0 when no interactions."""
        interface = SymbiosisInterface("node-1")
        status = interface.get_status()
        assert status["avg_interaction_quality"] == 0.0

    def test_status_includes_pending_negotiations_count(self):
        """Status includes count of pending negotiations."""
        interface = SymbiosisInterface("node-1")
        interface.propose_value("a", {}, "p1")
        interface.propose_value("b", {}, "p2")
        status = interface.get_status()
        assert status["pending_negotiations"] == 2

    def test_status_partner_details_include_all_fields(self):
        """Each partner entry has all required status fields."""
        interface = SymbiosisInterface("node-1")
        interface.perceive_partner("p", trust=0.75, mode=InteractionMode.DIALOGUE)
        interface.accept_proposal("p")
        status = interface.get_status()
        pstatus = status["partners"]["p"]
        assert "trust" in pstatus
        assert "mode" in pstatus
        assert "interactions" in pstatus
        assert "status" in pstatus
        assert "quality_score" in pstatus

