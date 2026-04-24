"""
Unit tests for NegotiationSkill — value-based inter-infant negotiation.

TDD coverage:
- Offer proposal generation from value alignment
- Mutual benefit calculation
- Negotiation state tracking (pending/accepted/rejected)
- Convergence detection
- Dependency on consensus/value_alignment
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cosmic_mycelium.infant.skills.base import InfantSkill, SkillContext
from cosmic_mycelium.infant.skills.collective.negotiation import NegotiationSkill, NegotiationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_negotiation_registry():
    """Reset singleton state between tests."""
    # NegotiationSkill uses class-level state, clear it
    if hasattr(NegotiationSkill, '_negotiations'):
        del NegotiationSkill._negotiations
    yield
    if hasattr(NegotiationSkill, '_negotiations'):
        del NegotiationSkill._negotiations


# ---------------------------------------------------------------------------
# Test: NegotiationState dataclass
# ---------------------------------------------------------------------------

class TestNegotiationState:
    """Tests for NegotiationState value object."""

    def test_negotiation_state_attributes(self):
        state = NegotiationState(
            negotiation_id="neg-001",
            proposer="infant-a",
            responder="infant-b",
            offer={"mutual_benefit": 0.8, "caution": 0.3},
            status="pending",
            rounds=0,
        )
        assert state.negotiation_id == "neg-001"
        assert state.proposer == "infant-a"
        assert state.responder == "infant-b"
        assert state.status == "pending"
        assert state.rounds == 0


# ---------------------------------------------------------------------------
# Test: NegotiationSkill Initialization & Lifecycle
# ---------------------------------------------------------------------------

class TestNegotiationSkillInitialization:
    """Tests for NegotiationSkill construction and protocol compliance."""

    def test_skill_has_required_attributes(self):
        skill = NegotiationSkill()
        assert skill.name == "negotiation"
        assert skill.version == "1.0.0"
        assert skill.dependencies == []  # components injected, not skill deps
        assert isinstance(skill.description, str)

    def test_initialize_sets_ready(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        skill.initialize(context)
        assert skill._initialized is True

    def test_shutdown_clears_state(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        # Populate class-level negotiations dict
        NegotiationSkill._negotiations["dummy"] = MagicMock()
        skill.shutdown()
        assert skill._initialized is False
        # Class dict should be cleared (fixture will delete after test)
        assert len(NegotiationSkill._negotiations) == 0


# ---------------------------------------------------------------------------
# Test: can_activate gating
# ---------------------------------------------------------------------------

class TestNegotiationSkillActivation:
    """Tests for can_activate() energy and state gating."""

    def test_activate_requires_energy(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=2.0)
        assert skill.can_activate(context) is False

    def test_activate_requires_initialized(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = False
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        assert skill.can_activate(context) is False

    def test_activate_success(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=50)
        skill._initialized = True
        assert skill.can_activate(context) is True


# ---------------------------------------------------------------------------
# Test: execute() negotiation flow
# ---------------------------------------------------------------------------

class TestNegotiationSkillExecution:
    """Tests for execute() — offer creation, response handling, convergence."""

    def test_execute_proposes_without_response(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill.value_alignment = MagicMock()
        skill.value_alignment.compute_distance = MagicMock(return_value=0.2)  # mutual_benefit = 0.8
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.8, "caution": 0.2}
        skill._infant_id = "test-infant"

        result = skill.execute({"partner_id": "infant-b"})

        assert result["status"] == "proposed"
        assert "negotiation_id" in result
        assert result["energy_cost"] == pytest.approx(3.0, abs=0.5)

    def test_execute_responds_to_pending_offer(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill.value_alignment = MagicMock()
        skill.value_alignment.compute_distance = MagicMock(return_value=0.1)
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.8, "caution": 0.2}
        skill._infant_id = "test-infant"
        skill._cooldown = 0.0  # disable for test

        # Propose first and capture negotiation_id
        result1 = skill.execute({"partner_id": "infant-b"})
        neg_id = result1["negotiation_id"]

        # Respond to same offer
        result2 = skill.execute({
            "negotiation_id": neg_id,
            "accept": True,
        })

        assert result2["status"] == "accepted"
        assert result2["negotiation_id"] == neg_id

    def test_execute_rejects_when_benefit_below_threshold(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill.value_alignment = MagicMock()
        skill.value_alignment.compute_distance = MagicMock(return_value=0.9)  # mutual_benefit = 0.1
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.2, "caution": 0.8}
        skill._infant_id = "test"

        result = skill.execute({"partner_id": "infant-b"})
        # Mutual benefit too low, negotiation rejected immediately
        assert result["status"] == "rejected"
        assert result["reason"] == "value_distance_too_large"

    def test_execute_cooldown_prevents_spam(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill.value_alignment = MagicMock()
        skill.value_alignment.compute_distance = MagicMock(return_value=0.1)
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.9, "caution": 0.1}
        skill._last_execution = 0.0
        skill._infant_id = "test"

        # First execute
        skill.execute({"partner_id": "infant-b"})

        # Immediate second execute should be blocked by cooldown
        result = skill.execute({"partner_id": "infant-b"})
        assert result["status"] == "cooldown"

    def test_execute_cleans_up_stale_negotiations(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill.value_alignment = MagicMock()
        skill.value_alignment.compute_distance = MagicMock(return_value=0.1)
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.9}
        skill._infant_id = "test"

        import time
        now = time.time()
        # Set class-level negotiations directly
        stale = MagicMock(status="proposed", last_update=now - 400)
        fresh = MagicMock(status="proposed", last_update=now - 10)
        NegotiationSkill._negotiations = {"stale": stale, "fresh": fresh}

        skill.execute({})  # triggers prune
        # Stale negotiation should be pruned (status set to expired and removed after)
        # Actually _prune_expired removes from dict, not just status
        assert "stale" not in NegotiationSkill._negotiations
        assert "fresh" in NegotiationSkill._negotiations


# ---------------------------------------------------------------------------
# Test: get_resource_usage & get_status
# ---------------------------------------------------------------------------

class TestNegotiationSkillMonitoring:
    """Tests for resource reporting and status."""

    def test_get_resource_usage(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        usage = skill.get_resource_usage()
        assert "energy_cost" in usage
        assert usage["energy_cost"] == pytest.approx(3.0, abs=0.5)
        assert "duration_s" in usage
        assert "memory_mb" in usage

    def test_get_status(self, fresh_negotiation_registry):
        skill = NegotiationSkill()
        skill._initialized = True
        skill._execution_count = 5
        status = skill.get_status()
        assert status["name"] == "negotiation"
        assert status["initialized"] is True
        assert status["execution_count"] == 5
        assert "active_negotiations" in status
