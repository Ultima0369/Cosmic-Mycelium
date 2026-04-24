"""
Unit tests for ProposalGenerator — automatic cluster proposal triggers.

TDD coverage:
- Rule matching (energy critical, energy recovery, curiosity thresholds)
- Cooldown enforcement
- Proposal content generation
- Integration with CollectiveIntelligence
- InfantSkill protocol compliance (initialize, can_activate, execute, etc.)
"""

from __future__ import annotations

import time
from unittest.mock import ANY, MagicMock

import pytest

from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.collective.proposal_generator import (
    ProposalGenerator,
    TriggerRule,
)


class TestTriggerRule:
    """Tests for TriggerRule dataclass and basic rule evaluation."""

    def test_rule_attributes(self):
        """TriggerRule stores all required fields."""
        rule = TriggerRule(
            name="test",
            region="somatic",
            metric="energy",
            threshold=30.0,
            comparison="lt",
            cooldown=120.0,
            priority=0.9,
        )
        assert rule.name == "test"
        assert rule.region == "somatic"
        assert rule.metric == "energy"
        assert rule.threshold == 30.0
        assert rule.comparison == "lt"
        assert rule.cooldown == 120.0
        assert rule.priority == 0.9
        assert rule.last_triggered <= time.time()

    def test_lt_trigger_fires_when_below_threshold(self):
        """lt comparison triggers when value < threshold."""
        rule = TriggerRule(
            name="energy_low",
            region="somatic",
            metric="energy",
            threshold=30.0,
            comparison="lt",
            cooldown=0,  # disable cooldown for test
        )
        state = {"energy": 25.0}
        # Check manually: value 25 < 30 → should trigger
        assert state["energy"] < rule.threshold

    def test_gt_trigger_fires_when_above_threshold(self):
        """gt comparison triggers when value > threshold."""
        rule = TriggerRule(
            name="energy_high",
            region="somatic",
            metric="energy",
            threshold=80.0,
            comparison="gt",
            cooldown=0,
        )
        state = {"energy": 85.0}
        assert state["energy"] > rule.threshold

    def test_eq_trigger_fires_when_approximately_equal(self):
        """eq comparison triggers when |value - threshold| < epsilon."""
        rule = TriggerRule(
            name="energy_exact",
            region="somatic",
            metric="energy",
            threshold=50.0,
            comparison="eq",
            cooldown=0,
        )
        # Within epsilon → should trigger
        assert abs(50.0 - rule.threshold) < 1e-3
        # Clearly outside epsilon → should not trigger
        assert abs(50.005 - rule.threshold) > 1e-3


class TestProposalGeneratorInitialization:
    """Tests for ProposalGenerator construction and rule management."""

    def test_default_rules_populated(self):
        """Generator starts with 6 built-in trigger rules (Sprint 3: planner/meta扩展)."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        assert len(gen.rules) == 6
        assert "energy_critical" in gen.rules
        assert "energy_recovery" in gen.rules
        assert "high_curiosity" in gen.rules
        assert "novelty_spike" in gen.rules
        assert "high_caution" in gen.rules
        assert "low_self_preservation" in gen.rules

    def test_custom_rules_merge_with_defaults(self):
        """Custom rules add to defaults, not replace."""
        mock_collective = MagicMock()
        custom = [
            TriggerRule(
                name="custom_rule",
                region="test",
                metric="test_metric",
                threshold=1.0,
                comparison="gt",
            )
        ]
        gen = ProposalGenerator(
            collective_intelligence=mock_collective, rules=custom
        )
        assert "custom_rule" in gen.rules
        assert "energy_critical" in gen.rules  # defaults preserved
        assert len(gen.rules) == 7  # 6 defaults + 1 custom

    def test_can_disable_generator(self):
        """Generator respects enabled flag."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        assert gen.enabled is True
        gen.enabled = False
        assert gen.enabled is False

    def test_add_rule_dynamically(self):
        """Can add rules at runtime via add_rule()."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        initial_count = len(gen.rules)

        new_rule = TriggerRule(
            name="dynamic",
            region="test",
            metric="x",
            threshold=0.5,
            comparison="gt",
        )
        gen.add_rule(new_rule)
        assert len(gen.rules) == initial_count + 1
        assert "dynamic" in gen.rules

    def test_remove_rule(self):
        """Can remove rules by name via remove_rule()."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.remove_rule("energy_critical")
        assert "energy_critical" not in gen.rules


class TestShouldPropose:
    """Tests for should_propose() trigger matching logic."""

    def test_energy_critical_rule_triggers(self):
        """energy < 30 triggers energy_critical rule."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Override defaults to ensure deterministic
        gen.rules = {
            "energy_critical": TriggerRule(
                name="energy_critical",
                region="somatic",
                metric="energy",
                threshold=30.0,
                comparison="lt",
                cooldown=0,
            )
        }

        state = {"energy": 25.0}
        triggered = gen.should_propose(state)
        assert triggered is not None
        assert triggered.name == "energy_critical"

    def test_energy_not_critical_no_trigger(self):
        """energy >= 30 does NOT trigger energy_critical."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.rules = {
            "energy_critical": TriggerRule(
                name="energy_critical",
                region="somatic",
                metric="energy",
                threshold=30.0,
                comparison="lt",
                cooldown=0,
            )
        }

        state = {"energy": 35.0}
        triggered = gen.should_propose(state)
        assert triggered is None

    def test_cooldown_prevents_rapid_retrigger(self):
        """Same rule cannot trigger again until cooldown expires."""
        mock_collective = MagicMock()
        rule = TriggerRule(
            name="test",
            region="somatic",
            metric="x",
            threshold=1.0,
            comparison="lt",
            cooldown=10.0,  # 10s cooldown
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective, rules=[rule])

        state = {"x": 0.5}
        # First call triggers
        t1 = gen.should_propose(state)
        assert t1 is rule
        # Second call within cooldown returns None
        t2 = gen.should_propose(state)
        assert t2 is None
        # After cooldown, can trigger again
        rule.last_triggered -= 10.1  # Simulate time passing
        t3 = gen.should_propose(state)
        assert t3 is rule

    def test_missing_metric_does_not_trigger(self):
        """Rule skipped if state lacks the required metric."""
        mock_collective = MagicMock()
        rule = TriggerRule(
            name="needs_metric",
            region="somatic",
            metric="missing_key",
            threshold=1.0,
            comparison="lt",
            cooldown=0,
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Isolate to only this rule for test
        gen.rules = {rule.name: rule}
        state = {"energy": 25.0}  # no 'missing_key'
        triggered = gen.should_propose(state)
        assert triggered is None

    def test_disabled_generator_never_triggers(self):
        """When enabled=False, should_propose always returns None."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.enabled = False
        state = {"energy": 1.0}  # would normally trigger
        assert gen.should_propose(state) is None

    def test_multiple_rules_first_trigger_wins(self):
        """First rule to match (insertion order) is returned."""
        mock_collective = MagicMock()
        rules = [
            TriggerRule(
                name="low_energy",
                region="somatic",
                metric="energy",
                threshold=50.0,
                comparison="lt",
                cooldown=0,
            ),
            TriggerRule(
                name="very_low_energy",
                region="somatic",
                metric="energy",
                threshold=30.0,
                comparison="lt",
                cooldown=0,
            ),
        ]
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Isolate to only these two rules, preserving order
        gen.rules = {r.name: r for r in rules}

        state = {"energy": 25.0}  # Both rules match (25 < 50 AND 25 < 30)
        triggered = gen.should_propose(state)
        # First rule in dict (insertion order) wins
        assert triggered.name == "low_energy"


class TestGenerateProposalContent:
    """Tests for generate_proposal_content() payload builder."""

    def test_content_contains_rule_metadata(self):
        """Proposal content includes rule name, region, and metric value."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        rule = TriggerRule(
            name="test_rule",
            region="somatic",
            metric="energy",
            threshold=30.0,
            comparison="lt",
        )
        state = {"energy": 25.0, "other": 42.0}

        content = gen.generate_proposal_content(rule, state)

        assert content["type"] == "auto_proposal"
        assert content["rule_name"] == "test_rule"
        assert content["region"] == "somatic"
        assert content["metric_value"] == 25.0
        assert "timestamp" in content
        assert "context" in content
        assert content["context"] == state  # Full state snapshot preserved

    def test_timestamp_is_recent(self):
        """Generated timestamp is within last second."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        rule = TriggerRule(
            name="t", region="r", metric="m", threshold=1.0, comparison="lt"
        )

        before = time.time()
        content = gen.generate_proposal_content(rule, {"m": 0.5})
        after = time.time()

        assert before <= content["timestamp"] <= after


class TestProposalGeneratorIntegration:
    """Integration tests with mocked CollectiveIntelligence and HIC."""

    def test_execute_returns_proposal_id_when_triggered(self):
        """execute() calls collective.propose() and returns proposal_id."""
        mock_collective = MagicMock()
        mock_collective.propose.return_value = "prop-abc123"

        # Minimal HIC mock
        mock_hic = MagicMock()
        mock_hic.energy = 25.0
        mock_hic.energy_slope = -5.0
        mock_hic.value_vector = {"mutual_benefit": 0.5}

        gen = ProposalGenerator(
            collective_intelligence=mock_collective,
            hic=mock_hic,
            rules=[
                TriggerRule(
                    name="energy_critical",
                    region="somatic",
                    metric="energy",
                    threshold=30.0,
                    comparison="lt",
                    cooldown=0,
                )
            ],
        )
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=100))

        # execute with empty params (protocol requires dict)
        result = gen.execute({})

        assert result["proposal_id"] == "prop-abc123"
        assert result["rule_name"] == "energy_critical"
        assert result["energy_cost"] == 5.0
        mock_collective.propose.assert_called_once()
        call_args = mock_collective.propose.call_args
        assert call_args[1]["region"] == "somatic"
        assert "priority" in call_args[1]
        assert "activation" in call_args[1]

    def test_execute_returns_none_when_no_trigger(self):
        """execute() returns None proposal_id if no rules match."""
        mock_collective = MagicMock()
        mock_hic = MagicMock()
        mock_hic.energy = 80.0  # High energy, no triggers
        # Provide complete value_vector to avoid triggering new region rules
        mock_hic.value_vector = {
            "mutual_benefit": 0.5,
            "self_preservation": 1.0,
            "curiosity": 0.7,
            "caution": 0.5,
        }

        gen = ProposalGenerator(collective_intelligence=mock_collective, hic=mock_hic)
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=100))

        result = gen.execute({})
        assert result["proposal_id"] is None
        assert result["rule_name"] is None
        mock_collective.propose.assert_not_called()

    def test_execute_respects_enabled_flag(self):
        """Disabled generator's execute() returns no proposal."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.enabled = False
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=100))

        result = gen.execute({})
        assert result["proposal_id"] is None

    def test_execute_without_hic_returns_none(self):
        """Generator without HIC cannot access state → no proposals."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective, hic=None)
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=100))

        result = gen.execute({})
        assert result["proposal_id"] is None

    def test_can_activate_checks_energy(self):
        """can_activate() returns False if energy budget too low."""
        mock_collective = MagicMock()
        mock_hic = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective, hic=mock_hic)
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=2.0))
        assert gen.can_activate(SkillContext(infant_id="test", cycle_count=0, energy_available=2.0)) is False

    def test_can_activate_happy_path(self):
        """can_activate() returns True when all conditions met."""
        mock_collective = MagicMock()
        mock_hic = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective, hic=mock_hic)
        gen.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=100))
        assert gen.can_activate(SkillContext(infant_id="test", cycle_count=0, energy_available=100)) is True


# -------------------------------------------------------------------------
# Sprint 3: Composite Conditions (AND/OR)
# -------------------------------------------------------------------------

class TestCompositeConditions:
    """Tests for AND/OR multi-metric trigger rules."""

    def test_and_condition_requires_all_metrics(self):
        """AND rule triggers only when all sub-conditions are satisfied."""
        from cosmic_mycelium.infant.skills.collective.proposal_generator import Condition

        mock_collective = MagicMock()
        rule = TriggerRule(
            name="energy_critical_and_caution",
            region="somatic",
            conditions=[
                Condition(metric="energy", threshold=30.0, comparison="lt"),
                Condition(metric="caution", threshold=0.7, comparison="gt"),
            ],
            logic="AND",
            cooldown=0,
            priority=0.9,
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.rules = {rule.name: rule}  # isolate

        # Both satisfied → trigger
        state = {"energy": 25.0, "caution": 0.8}
        assert gen.should_propose(state) is rule

        # Energy low but caution low → no trigger
        state2 = {"energy": 25.0, "caution": 0.5}
        assert gen.should_propose(state2) is None

        # Energy ok but caution high → no trigger
        state3 = {"energy": 50.0, "caution": 0.9}
        assert gen.should_propose(state3) is None

    def test_or_condition_triggers_on_any_metric(self):
        """OR rule triggers when any sub-condition is satisfied."""
        from cosmic_mycelium.infant.skills.collective.proposal_generator import Condition

        mock_collective = MagicMock()
        rule = TriggerRule(
            name="energy_or_curiosity_alert",
            region="somatic",
            conditions=[
                Condition(metric="energy", threshold=20.0, comparison="lt"),
                Condition(metric="curiosity", threshold=2.0, comparison="gt"),
            ],
            logic="OR",
            cooldown=0,
            priority=0.7,
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.rules = {rule.name: rule}  # isolate

        # Only energy low → trigger
        state1 = {"energy": 15.0, "curiosity": 1.0}
        assert gen.should_propose(state1) is rule

        # Only curiosity high → trigger
        state2 = {"energy": 80.0, "curiosity": 2.5}
        assert gen.should_propose(state2) is rule

        # Both satisfied → trigger
        state3 = {"energy": 10.0, "curiosity": 3.0}
        assert gen.should_propose(state3) is rule

        # Neither satisfied → no trigger
        state4 = {"energy": 50.0, "curiosity": 1.0}
        assert gen.should_propose(state4) is None

    def test_composite_rule_missing_metric_does_not_trigger(self):
        """If any required metric is missing from state, composite rule fails."""
        from cosmic_mycelium.infant.skills.collective.proposal_generator import Condition

        mock_collective = MagicMock()
        rule = TriggerRule(
            name="needs_both",
            region="meta",
            conditions=[
                Condition(metric="energy", threshold=30.0, comparison="lt"),
                Condition(metric="caution", threshold=0.8, comparison="gt"),
            ],
            logic="AND",
            cooldown=0,
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.rules = {rule.name: rule}  # isolate

        # Missing 'caution'
        state = {"energy": 25.0}
        assert gen.should_propose(state) is None

        # Missing 'energy'
        state2 = {"caution": 0.9}
        assert gen.should_propose(state2) is None

    def test_composite_rule_content_generation_uses_first_metric(self):
        """generate_proposal_content uses first condition's metric for metric_value."""
        from cosmic_mycelium.infant.skills.collective.proposal_generator import Condition

        mock_collective = MagicMock()
        rule = TriggerRule(
            name="composite_test",
            region="meta",
            conditions=[
                Condition(metric="energy", threshold=30.0, comparison="lt"),
                Condition(metric="caution", threshold=0.8, comparison="gt"),
            ],
            logic="AND",
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)

        state = {"energy": 25.0, "caution": 0.9}
        content = gen.generate_proposal_content(rule, state)

        assert content["metric_value"] == 25.0  # first condition's metric
        assert content["rule_name"] == "composite_test"
        assert content["region"] == "meta"

    def test_mixed_simple_and_composite_rules_in_same_generator(self):
        """Generator can handle both simple and composite rules together."""
        from cosmic_mycelium.infant.skills.collective.proposal_generator import Condition

        mock_collective = MagicMock()
        simple_rule = TriggerRule(
            name="energy_low",
            region="somatic",
            metric="energy",
            threshold=30.0,
            comparison="lt",
            cooldown=0,
        )
        composite_rule = TriggerRule(
            name="energy_and_curiosity",
            region="explorer",
            conditions=[
                Condition(metric="energy", threshold=50.0, comparison="lt"),
                Condition(metric="curiosity", threshold=1.5, comparison="gt"),
            ],
            logic="AND",
            cooldown=0,
        )
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        gen.rules = {simple_rule.name: simple_rule, composite_rule.name: composite_rule}  # isolate

        # Only simple rule matches
        state1 = {"energy": 25.0, "curiosity": 1.0}
        triggered = gen.should_propose(state1)
        assert triggered.name == "energy_low"

        # Only composite matches (energy low enough, curiosity high)
        state2 = {"energy": 40.0, "curiosity": 2.0}
        triggered = gen.should_propose(state2)
        assert triggered.name == "energy_and_curiosity"

        # Both match — first in dict wins (insertion order preserved)
        state3 = {"energy": 20.0, "curiosity": 2.0}
        triggered = gen.should_propose(state3)
        assert triggered.name in ("energy_low", "energy_and_curiosity")


# -------------------------------------------------------------------------
# Sprint 3: Cross-Region Proposal Chaining
# -------------------------------------------------------------------------

class TestCrossRegionChaining:
    """Tests for workspace-event-driven proposal chaining."""

    def test_listener_triggers_on_source_workspace_update(self):
        """When source_region's proposal is broadcast, listener rule fires."""
        mock_collective = MagicMock()
        mock_collective.workspace = MagicMock()
        mock_collective.workspace.iteration = 1
        mock_collective.workspace.source_region = "somatic"
        mock_collective.workspace.source_node = "node-1"
        mock_collective.propose.return_value = "chain-prop-1"

        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Listener: when somatic proposal is adopted, trigger meta region rule
        listener_rule = TriggerRule(
            name="post_somatic_analysis",
            region="meta",
            metric="caution",
            threshold=0.5,
            comparison="gt",
            cooldown=0,
        )
        gen.register_chain("somatic", listener_rule)

        # Simulate state where caution is high
        mock_hic = MagicMock()
        mock_hic.energy = 50.0
        mock_hic.value_vector = {"caution": 0.8}
        gen.hic = mock_hic
        gen._initialized = True

        # Execute — should detect workspace update and fire listener
        result = gen.execute({})

        assert result["proposal_id"] == "chain-prop-1"
        assert result["rule_name"] == "post_somatic_analysis"
        mock_collective.propose.assert_called_once_with(
            region="meta",
            content=ANY,
            priority=0.5,
            activation=0.8,  # state.caution value
        )

    def test_listener_respects_cooldown(self):
        """Listener rules obey their cooldown period."""
        mock_collective = MagicMock()
        mock_collective.workspace = MagicMock()
        mock_collective.workspace.iteration = 1
        mock_collective.workspace.source_region = "somatic"
        mock_collective.propose.return_value = "x"

        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Clear defaults to avoid interference
        gen.rules = {}
        rule = TriggerRule(
            name="chain_rule",
            region="meta",
            metric="caution",
            threshold=0.5,
            comparison="gt",
            cooldown=10.0,
        )
        gen.register_chain("somatic", rule)
        # Provide full HIC state with caution metric
        gen.hic = MagicMock()
        gen.hic.energy = 50.0
        gen.hic.energy_slope = 0.0
        gen.hic.value_vector = {"caution": 0.8, "mutual_benefit": 0.5}
        gen._initialized = True

        # First execute — triggers
        result1 = gen.execute({})
        assert result1["proposal_id"] == "x"

        # Second execute with same workspace iteration — no trigger (cooldown)
        result2 = gen.execute({})
        assert result2["proposal_id"] is None

    def test_no_listener_for_unknown_source_region(self):
        """Workspace update from unregistered region does nothing."""
        mock_collective = MagicMock()
        mock_collective.workspace = MagicMock()
        mock_collective.workspace.iteration = 1
        mock_collective.workspace.source_region = "unknown_region"
        mock_collective.propose.return_value = "x"

        gen = ProposalGenerator(collective_intelligence=mock_collective)
        # Clear defaults to avoid any rule firing
        gen.rules = {}
        rule = TriggerRule(name="somatic_listener", region="planner", metric="caution", threshold=0.5, comparison="gt")
        gen.register_chain("somatic", rule)
        gen.hic = MagicMock()
        gen.hic.energy = 50.0
        gen.hic.value_vector = {"caution": 0.3}  # below threshold
        gen._initialized = True

        result = gen.execute({})
        assert result["proposal_id"] is None
        mock_collective.propose.assert_not_called()

    def test_chain_rule_not_added_to_main_rules_automatically(self):
        """register_chain adds rule to both _region_listeners and main rules."""
        mock_collective = MagicMock()
        gen = ProposalGenerator(collective_intelligence=mock_collective)
        rule = TriggerRule(name="chain", region="meta", metric="x", threshold=1, comparison="gt")
        gen.register_chain("somatic", rule)

        assert "chain" in gen.rules
        assert "somatic" in gen._region_listeners
        assert rule in gen._region_listeners["somatic"]
