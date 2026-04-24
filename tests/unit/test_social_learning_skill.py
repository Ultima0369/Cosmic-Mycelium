"""
Unit tests for SocialLearningSkill — observational peer learning.

TDD coverage:
- Peer behavior observation and recording
- Strategy imitation with adaptation
- Social bond formation and trust tracking
- Cultural knowledge propagation
- Dependency on collective_intelligence
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.social.social_learning import (
    SocialLearningSkill,
    ObservedBehavior,
    SocialBond,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_social_learning():
    """Reset singleton state between tests."""
    if hasattr(SocialLearningSkill, '_observed_behaviors'):
        del SocialLearningSkill._observed_behaviors
    if hasattr(SocialLearningSkill, '_social_bonds'):
        del SocialLearningSkill._social_bonds
    yield
    if hasattr(SocialLearningSkill, '_observed_behaviors'):
        del SocialLearningSkill._observed_behaviors
    if hasattr(SocialLearningSkill, '_social_bonds'):
        del SocialLearningSkill._social_bonds


# ---------------------------------------------------------------------------
# Test: ObservedBehavior
# ---------------------------------------------------------------------------

class TestObservedBehavior:
    """Tests for ObservedBehavior value object."""

    def test_observed_behavior_attributes(self):
        obs = ObservedBehavior(
            behavior_id="beh-001",
            source_infant="infant-a",
            behavior_type="strategy_selection",
            context={"energy": 80.0, "curiosity": 1.2},
            outcome={"success": True, "reward": 5.0},
            timestamp=1234567890.0,
        )
        assert obs.behavior_id == "beh-001"
        assert obs.source_infant == "infant-a"
        assert obs.behavior_type == "strategy_selection"
        assert obs.outcome["success"] is True


# ---------------------------------------------------------------------------
# Test: SocialBond
# ---------------------------------------------------------------------------

class TestSocialBond:
    """Tests for SocialBond value object."""

    def test_social_bond_attributes(self):
        bond = SocialBond(
            peer_id="infant-b",
            trust=0.75,
            interactions=10,
            last_interaction=1234567890.0,
        )
        assert bond.peer_id == "infant-b"
        assert bond.trust == pytest.approx(0.75, abs=0.01)
        assert bond.interactions == 10


# ---------------------------------------------------------------------------
# Test: SocialLearningSkill Initialization & Lifecycle
# ---------------------------------------------------------------------------

class TestSocialLearningSkillInitialization:
    """Tests for SocialLearningSkill construction and protocol compliance."""

    def test_skill_has_required_attributes(self):
        skill = SocialLearningSkill()
        assert skill.name == "social_learning"
        assert skill.version == "1.0.0"
        assert "collective_intelligence" in skill.dependencies
        assert isinstance(skill.description, str)

    def test_initialize_sets_ready(self, fresh_social_learning):
        skill = SocialLearningSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        skill.initialize(context)
        assert skill._initialized is True

    def test_shutdown_clears_state(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        SocialLearningSkill._observed_behaviors = {"dummy": MagicMock()}
        SocialLearningSkill._social_bonds = {"dummy": MagicMock()}
        skill.shutdown()
        assert skill._initialized is False


# ---------------------------------------------------------------------------
# Test: can_activate gating
# ---------------------------------------------------------------------------

class TestSocialLearningSkillActivation:
    """Tests for can_activate() gating."""

    def test_activate_requires_energy(self, fresh_social_learning):
        skill = SocialLearningSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=2.0)
        assert skill.can_activate(context) is False

    def test_activate_requires_initialized(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = False
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        assert skill.can_activate(context) is False

    def test_activate_success(self, fresh_social_learning):
        skill = SocialLearningSkill()
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=50)
        skill._initialized = True
        skill.collective = MagicMock()
        skill.collective.workspace = MagicMock()  # workspace available
        assert skill.can_activate(context) is True


# ---------------------------------------------------------------------------
# Test: execute() observation and learning
# ---------------------------------------------------------------------------

class TestSocialLearningSkillExecution:
    """Tests for execute() — observation recording, imitation, bond strengthening."""

    def test_execute_observes_peer_behavior(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        skill._infant_id = "test-infant"  # set identity
        skill.collective = MagicMock()
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.8}

        # Mock workspace entry from another infant
        mock_entry = MagicMock()
        mock_entry.source_infant = "infant-a"
        mock_entry.metadata = {
            "behavior_type": "proposal_vote",
            "context": {"energy": 70.0},
            "outcome": {"accepted": True}
        }
        skill.collective.workspace = MagicMock()
        skill.collective.workspace.get_recent_entries = MagicMock(return_value=[mock_entry])

        result = skill.execute({"observe_only": True})

        assert result["status"] == "observed"
        assert result["behaviors_observed"] == 1
        assert result["energy_cost"] == pytest.approx(2.0, abs=0.5)

    def test_execute_imitates_successful_strategy(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        skill._infant_id = "test-infant"
        skill.collective = MagicMock()
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.9}

        # Provide one observed peer to satisfy _scan_workspace non-empty check
        mock_entry = MagicMock()
        mock_entry.source_infant = "peer-a"
        mock_entry.metadata = {"behavior_type": "some_behavior", "outcome": {"success": False}}
        skill.collective.workspace = MagicMock()
        skill.collective.workspace.get_recent_entries = MagicMock(return_value=[mock_entry])

        # Create a previously observed behavior with positive outcome
        import time
        from unittest.mock import patch
        obs = ObservedBehavior(
            behavior_id="beh-001",
            source_infant="infant-a",
            behavior_type="energy_conservation",
            context={"energy": 50.0},
            outcome={"success": True, "reward": 10.0},
            timestamp=time.time() - 100,
        )
        SocialLearningSkill._observed_behaviors = {"beh-001": obs}
        skill._imitation_candidates = ["beh-001"]

        # Patch random to guarantee imitation success
        with patch("random.random", return_value=0.5):
            result = skill.execute({"imitate": "beh-001"})

        assert result["status"] == "imitated"
        assert result["behavior_id"] == "beh-001"
        assert "adaptation_note" in result

    def test_execute_rejects_untrusted_peer(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        skill._infant_id = "test-infant"
        skill.collective = MagicMock()
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.3}

        # Pre-create a low-trust bond (< 0.3) for the peer
        low_bond = SocialBond(peer_id="untrusted-peer", trust=0.2, interactions=1)
        SocialLearningSkill._social_bonds = {"untrusted-peer": low_bond}

        mock_entry = MagicMock()
        mock_entry.source_infant = "untrusted-peer"
        mock_entry.metadata = {"behavior_type": "risky_behavior"}
        skill.collective.workspace = MagicMock()
        skill.collective.workspace.get_recent_entries = MagicMock(return_value=[mock_entry])

        result = skill.execute({"observe_only": True})
        # Low-trust peer is skipped → no behaviors observed
        assert result["status"] == "no_peers_observed"

    def test_execute_strengthens_bond_after_interaction(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        skill._infant_id = "test-infant"
        skill.collective = MagicMock()
        skill.hic = MagicMock()
        skill.hic.value_vector = {"mutual_benefit": 0.8}

        # Provide one observed peer so scan doesn't return empty
        mock_entry = MagicMock()
        mock_entry.source_infant = "infant-a"
        mock_entry.metadata = {"behavior_type": "good_action", "outcome": {"success": True}}
        skill.collective.workspace = MagicMock()
        skill.collective.workspace.get_recent_entries = MagicMock(return_value=[mock_entry])

        # Pre-existing bond with trust 0.5 and recent interaction (to avoid decay)
        import time
        bond = SocialBond(peer_id="infant-a", trust=0.5, interactions=5, last_interaction=time.time())
        SocialLearningSkill._social_bonds = {"infant-a": bond}

        result = skill.execute({"observe_only": True})
        # Bond trust should increase after successful observation
        bond_after = SocialLearningSkill._social_bonds["infant-a"]
        assert bond_after.trust > 0.5
        assert bond_after.interactions > 5


# ---------------------------------------------------------------------------
# Test: get_resource_usage & get_status
# ---------------------------------------------------------------------------

class TestSocialLearningSkillMonitoring:
    """Tests for resource reporting and status."""

    def test_get_resource_usage(self, fresh_social_learning):
        skill = SocialLearningSkill()
        usage = skill.get_resource_usage()
        assert usage["energy_cost"] == pytest.approx(2.0, abs=0.5)

    def test_get_status(self, fresh_social_learning):
        skill = SocialLearningSkill()
        skill._initialized = True
        skill._execution_count = 3
        status = skill.get_status()
        assert status["name"] == "social_learning"
        assert "observed_behaviors" in status
        assert "social_bonds" in status
