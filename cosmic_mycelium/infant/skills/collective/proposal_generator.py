"""
Proposal Generator — Automatic Cluster Proposal Triggers

Scans local brain state and automatically generates cluster proposals
when conditions warrant collective attention or coordination.

Phase: Epic 4 (主动集群协同)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext

if TYPE_CHECKING:
    from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
    from cosmic_mycelium.infant.hic import HIC


@dataclass
class Condition:
    """Single metric condition for composite rules."""

    metric: str
    threshold: float
    comparison: str  # "gt", "lt", "eq"


@dataclass
class TriggerRule:
    """Condition that automatically fires a proposal.

    Supports both simple (single metric) and composite (AND/OR across multiple
    metrics) conditions. Simple conditions use metric/threshold/comparison
    fields directly; composite conditions use the `conditions` list with
    `logic` operator.
    """

    name: str
    region: str
    # Simple condition (backward compatible): single metric check
    metric: str = ""
    threshold: float = 0.0
    comparison: str = "gt"  # "gt", "lt", "eq"
    # Composite condition (AND/OR across multiple metrics)
    conditions: list[Condition] | None = None
    logic: str = "AND"  # "AND" or "OR" — only used when conditions is not None
    cooldown: float = 60.0  # Minimum seconds between triggers
    priority: float = 0.5  # Proposal priority [0, 1]
    last_triggered: float = field(default=0.0, init=False)  # 0 = never triggered


class ProposalGenerator(InfantSkill):
    """
    Monitors local state and auto-generates cluster proposals.

    Integration: attached to SiliconInfant, lifecycle manager calls can_activate()
    each cycle; if True, execute() generates proposal via CollectiveIntelligence.
    """

    name = "proposal_generator"
    version = "1.0.0"
    description = "自动提案生成器 — 监控本地状态触发集群提案"
    dependencies = []  # no external deps
    parallelism_policy = ParallelismPolicy.ISOLATED  # Sprint 5: thread-safe (writes CI with lock)

    def __init__(
        self,
        collective_intelligence: CollectiveIntelligence | None = None,
        hic: HIC | None = None,
        rules: list[TriggerRule] | None = None,
    ):
        self.collective = collective_intelligence
        self.hic = hic
        self.rules: dict[str, TriggerRule] = {}
        self.enabled = True
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0
        # Sprint 3: Cross-region proposal chaining — listeners for workspace updates
        self._region_listeners: dict[str, list[TriggerRule]] = {}
        self._last_workspace_iteration: int = -1  # Track workspace changes
        # Start with defaults, then overlay custom (custom overrides on name clash)
        for rule in self._default_rules():
            self.rules[rule.name] = rule
        for rule in rules or []:
            self.rules[rule.name] = rule

    def add_rule(self, rule: TriggerRule) -> None:
        """Register a new trigger rule."""
        self.rules[rule.name] = rule

    def remove_rule(self, name: str) -> None:
        """Remove a trigger rule by name."""
        self.rules.pop(name, None)

    def register_chain(
        self, source_region: str, trigger_rule: TriggerRule
    ) -> None:
        """
        Register a listener rule that triggers when source_region's proposal
        gets adopted into the cluster workspace.

        Args:
            source_region: Region whose workspace entry adoption triggers this rule
            trigger_rule: The rule to evaluate when source_region proposal is broadcast
        """
        if source_region not in self._region_listeners:
            self._region_listeners[source_region] = []
        self._region_listeners[source_region].append(trigger_rule)
        # Also add to main rules dict for lifecycle management
        self.rules[trigger_rule.name] = trigger_rule

    def _default_rules(self) -> list[TriggerRule]:
        """Built-in trigger rules for common scenarios."""
        return [
            TriggerRule(
                name="energy_critical",
                region="somatic",
                metric="energy",
                threshold=30.0,
                comparison="lt",
                cooldown=120.0,
                priority=0.9,
            ),
            TriggerRule(
                name="energy_recovery",
                region="somatic",
                metric="energy",
                threshold=80.0,
                comparison="gt",
                cooldown=180.0,
                priority=0.7,
            ),
            TriggerRule(
                name="high_curiosity",
                region="explorer",
                metric="curiosity",
                threshold=1.5,
                comparison="gt",
                cooldown=90.0,
                priority=0.8,
            ),
            TriggerRule(
                name="novelty_spike",
                region="sensory",
                metric="novelty",
                threshold=0.7,
                comparison="gt",
                cooldown=60.0,
                priority=0.6,
            ),
            # Sprint 3: 新增区域规则
            TriggerRule(
                name="high_caution",
                region="meta",
                metric="caution",
                threshold=0.8,
                comparison="gt",
                cooldown=60.0,
                priority=0.75,
            ),
            TriggerRule(
                name="low_self_preservation",
                region="somatic",
                metric="self_preservation",
                threshold=0.5,
                comparison="lt",
                cooldown=120.0,
                priority=0.8,
            ),
        ]

    # -------------------------------------------------------------------------
    # InfantSkill Protocol
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """Initialize skill (no external resources needed)."""
        self._initialized = True

    def can_activate(self, context: SkillContext) -> bool:
        """
        Activation conditions:
        - Enabled
        - Initialized
        - HIC available
        - Energy budget >= 5.0 (proposal overhead)
        """
        if not self.enabled or not self._initialized or self.hic is None:
            return False
        if context.energy_available < 5.0:
            return False
        return True

    def execute(self, params: dict[str, object]) -> dict[str, object]:
        """
        Execute one proposal-generation cycle.

        Args:
            params: ignored (kept for protocol compatibility)

        Returns:
            {
                "proposal_id": str | None,
                "rule_name": str | None,
                "energy_cost": float,
            }
        """
        if not self._initialized:
            raise RuntimeError("ProposalGenerator not initialized")

        # HIC + CollectiveIntelligence required
        if self.hic is None or self.collective is None:
            return {"proposal_id": None, "rule_name": None, "energy_cost": 5.0}

        # Build state snapshot from HIC
        state: dict[str, float] = {
            "energy": self.hic.energy,
            "energy_slope": getattr(self.hic, "energy_slope", 0.0),
            "mutual_benefit": self.hic.value_vector.get("mutual_benefit", 0.0),
            "curiosity": self.hic.value_vector.get("curiosity", 0.0),
            "caution": self.hic.value_vector.get("caution", 0.0),
            "self_preservation": self.hic.value_vector.get("self_preservation", 0.0),
        }

        # Sprint 3: Cross-region chaining — check for new workspace events
        if self.collective.workspace is not None:
            ws = self.collective.workspace
            try:
                current_iter = int(ws.iteration)
            except (TypeError, ValueError, AttributeError):
                current_iter = -1  # Invalid, skip chaining
            if current_iter > self._last_workspace_iteration:
                source_region = getattr(ws, "source_region", None)
                if source_region in self._region_listeners:
                    now = time.time()
                    for rule in self._region_listeners[source_region]:
                        # Check rule cooldown
                        if now - rule.last_triggered < rule.cooldown:
                            continue
                        if self._rule_matches(rule, state):
                            content = self.generate_proposal_content(rule, state)
                            proposal_id = self.collective.propose(
                                region=rule.region,
                                content=content,
                                priority=rule.priority,
                                activation=state.get(rule.metric, 0.5),
                            )
                            rule.last_triggered = now
                            self._last_execution = now
                            self._execution_count += 1
                            self._last_workspace_iteration = current_iter
                            return {
                                "proposal_id": proposal_id,
                                "rule_name": rule.name,
                                "energy_cost": 5.0,
                            }
                self._last_workspace_iteration = current_iter

        # Regular local-state-based proposal
        rule = self.should_propose(state)
        proposal_id = None
        rule_name = None
        if rule is not None:
            content = self.generate_proposal_content(rule, state)
            proposal_id = self.collective.propose(
                region=rule.region,
                content=content,
                priority=rule.priority,
                activation=state.get(rule.metric, 0.5),
            )
            rule_name = rule.name
            self._last_execution = time.time()
            self._execution_count += 1

        return {
            "proposal_id": proposal_id,
            "rule_name": rule_name,
            "energy_cost": 5.0,
        }

    def get_resource_usage(self) -> dict[str, float]:
        """Resource cost per execute() call."""
        return {"energy_cost": 5.0, "duration_s": 0.01, "memory_mb": 1.0}

    def shutdown(self) -> None:
        """Cleanup."""
        self.enabled = False
        self.rules.clear()
        self._region_listeners.clear()

    def get_status(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "initialized": self._initialized,
            "execution_count": self._execution_count,
            "last_execution": self._last_execution,
            "rule_count": len(self.rules),
        }

    # -------------------------------------------------------------------------
    # Internal Logic
    # -------------------------------------------------------------------------

    def _evaluate_condition(
        self,
        condition: Condition,
        state: dict[str, float],
    ) -> bool:
        """Evaluate a single condition against state snapshot."""
        value = state.get(condition.metric)
        if value is None:
            return False

        if condition.comparison == "gt":
            return value > condition.threshold
        elif condition.comparison == "lt":
            return value < condition.threshold
        elif condition.comparison == "eq":
            return abs(value - condition.threshold) < 1e-3
        return False

    def _rule_matches(self, rule: TriggerRule, state: dict[str, float]) -> bool:
        """
        Check if a rule's condition matches current state.

        Supports both simple (single metric) and composite (AND/OR) conditions.
        """
        # Composite condition path
        if rule.conditions is not None:
            results = [self._evaluate_condition(c, state) for c in rule.conditions]
            if rule.logic.upper() == "AND":
                return all(results)
            elif rule.logic.upper() == "OR":
                return any(results)
            # Unknown logic defaults to AND
            return all(results)

        # Simple condition (backward compatible)
        value = state.get(rule.metric)
        if value is None:
            return False

        if rule.comparison == "gt":
            return value > rule.threshold
        elif rule.comparison == "lt":
            return value < rule.threshold
        elif rule.comparison == "eq":
            return abs(value - rule.threshold) < 1e-3

        return False

    def should_propose(
        self, state_snapshot: dict[str, float]
    ) -> TriggerRule | None:
        """
        Check all rules against current state. Return first triggered rule.

        Supports both simple and composite rule conditions.
        """
        if not self.enabled:
            return None

        now = time.time()
        for rule in self.rules.values():
            if now - rule.last_triggered < rule.cooldown:
                continue  # Still in cooldown

            if self._rule_matches(rule, state_snapshot):
                rule.last_triggered = now
                return rule

        return None

    def generate_proposal_content(
        self, rule: TriggerRule, state: dict[str, float]
    ) -> dict[str, object]:
        """
        Build proposal payload dict from trigger rule and current state.

        For composite rules, uses the rule's primary metric (if set) for
        `metric_value`, otherwise uses the first condition's metric.
        """
        # Determine which metric to report as the triggering metric
        metric_name = rule.metric if rule.metric else (
            rule.conditions[0].metric if rule.conditions else "unknown"
        )

        return {
            "type": "auto_proposal",
            "rule_name": rule.name,
            "region": rule.region,
            "metric_value": state.get(metric_name),
            "timestamp": time.time(),
            "context": state.copy(),
        }
