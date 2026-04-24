"""
Unit Tests: ResearchSkill — autonomous research loop as a pluggable skill.

Covers initialization, activation conditions, bootstrap, and normal execution.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.infant.knowledge_store import KnowledgeEntry
from cosmic_mycelium.infant.skills.base import SkillContext, SkillExecutionError
from cosmic_mycelium.infant.skills.research.research_skill import ResearchSkill


@pytest.fixture
def mock_knowledge():
    """Mock KnowledgeStore with minimal interface."""
    mock = MagicMock()
    mock.get_stats.return_value = {"total_entries": 0}
    mock.execute_experiment.return_value = KnowledgeEntry(
        entry_id="test-entry",
        question="test question",
        hypothesis="test hypothesis",
        experiment_method="test method",
        result={"test": True},
        conclusion="success",
        confidence=0.9,
    )
    return mock


@pytest.fixture
def skill_with_knowledge(mock_knowledge):
    """ResearchSkill with knowledge injected and initialized."""
    skill = ResearchSkill(knowledge_store=mock_knowledge)
    skill.initialize(
        SkillContext(infant_id="test", cycle_count=0, energy_available=100)
    )
    return skill


class TestResearchSkillInitialization:
    def test_initialize_with_knowledge_creates_components(self, mock_knowledge):
        skill = ResearchSkill(knowledge_store=mock_knowledge)
        ctx = SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        skill.initialize(ctx)
        assert skill._initialized
        assert skill.question_generator is not None
        assert skill.experiment_designer is not None

    def test_initialize_without_knowledge_still_initializes_flag(self):
        skill = ResearchSkill(knowledge_store=None)
        ctx = SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        skill.initialize(ctx)
        assert skill._initialized
        assert skill.question_generator is None
        assert skill.experiment_designer is None


class TestResearchSkillActivation:
    def test_can_activate_false_when_not_initialized(self, mock_knowledge):
        skill = ResearchSkill(knowledge_store=mock_knowledge)
        ctx = SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        assert not skill.can_activate(ctx)

    def test_can_activate_false_when_knowledge_none(self):
        skill = ResearchSkill(knowledge_store=None)
        skill.initialize(
            SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        )
        ctx = SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        assert not skill.can_activate(ctx)

    def test_can_activate_false_when_energy_low(self, skill_with_knowledge):
        ctx = SkillContext(infant_id="t", cycle_count=10, energy_available=30)
        assert not skill_with_knowledge.can_activate(ctx)

    def test_can_activate_false_during_cooldown(self, skill_with_knowledge):
        # Simulate recent execution: last_execution set to current cycle
        skill_with_knowledge._last_execution = 10
        ctx = SkillContext(infant_id="t", cycle_count=10, energy_available=100)
        assert not skill_with_knowledge.can_activate(ctx)

    def test_can_activate_true_when_conditions_met(self, skill_with_knowledge):
        skill_with_knowledge._last_execution = 0  # long ago
        ctx = SkillContext(infant_id="t", cycle_count=20, energy_available=100)
        assert skill_with_knowledge.can_activate(ctx)


class TestResearchSkillExecution:
    def test_execute_bootstrap_when_knowledge_empty(
        self, mock_knowledge, skill_with_knowledge
    ):
        mock_knowledge.get_stats.return_value = {"total_entries": 0}
        ctx = SkillContext(infant_id="t", cycle_count=0, energy_available=100)
        result = skill_with_knowledge.execute({"_context": ctx})
        assert result["executed"] is True
        assert result["bootstrap"] is True
        assert "conclusion" in result
        mock_knowledge.execute_experiment.assert_called_once()

    def test_execute_normal_cycle_with_questions(
        self, mock_knowledge, skill_with_knowledge
    ):
        mock_knowledge.get_stats.return_value = {"total_entries": 5}
        # Mock question generator to return a list with one GeneratedQuestion-like object
        mock_q = MagicMock()
        mock_q.question = "测试问题"
        mock_q.hypothesis = "测试假设"
        skill_with_knowledge.question_generator.generate = MagicMock(return_value=[mock_q])
        # Mock experiment designer
        mock_plan = MagicMock()
        skill_with_knowledge.experiment_designer.design = MagicMock(
            return_value=mock_plan
        )
        # Knowledge execute_experiment returns KnowledgeEntry (already mocked)

        ctx = SkillContext(infant_id="t", cycle_count=5, energy_available=100)
        result = skill_with_knowledge.execute({"_context": ctx})

        assert result["executed"] is True
        assert result["question"] == "测试问题"
        assert result["hypothesis"] == "测试假设"
        assert result["conclusion"] == "success"
        assert result["confidence"] == 0.9
        skill_with_knowledge.question_generator.generate.assert_called_once()
        skill_with_knowledge.experiment_designer.design.assert_called_once_with(
            "测试问题", "测试假设"
        )
        mock_knowledge.execute_experiment.assert_called_once_with(mock_plan)

    def test_execute_returns_false_when_no_questions(self, skill_with_knowledge):
        # Ensure knowledge store reports non-empty to avoid bootstrap path
        skill_with_knowledge.knowledge.get_stats.return_value = {"total_entries": 5}
        skill_with_knowledge.question_generator.generate = MagicMock(return_value=[])
        ctx = SkillContext(infant_id="t", cycle_count=5, energy_available=100)
        result = skill_with_knowledge.execute({"_context": ctx})
        assert result["executed"] is False
        assert result["reason"] == "no_questions_generated"

    def test_execute_forces_bootstrap_with_flag(self, mock_knowledge, skill_with_knowledge):
        mock_knowledge.get_stats.return_value = {"total_entries": 10}
        # Even with entries, force_bootstrap triggers bootstrap
        ctx = SkillContext(infant_id="t", cycle_count=5, energy_available=100)
        result = skill_with_knowledge.execute({"force_bootstrap": True, "_context": ctx})
        assert result["bootstrap"] is True

    def test_execute_updates_counters(self, mock_knowledge, skill_with_knowledge):
        mock_knowledge.get_stats.return_value = {"total_entries": 1}
        mock_q = MagicMock()
        mock_q.question = "q"
        mock_q.hypothesis = "h"
        skill_with_knowledge.question_generator.generate = MagicMock(return_value=[mock_q])
        skill_with_knowledge.experiment_designer.design = MagicMock(return_value=MagicMock())
        ctx = SkillContext(infant_id="t", cycle_count=5, energy_available=100)
        initial_count = skill_with_knowledge._execution_count
        skill_with_knowledge.execute({"_context": ctx})
        assert skill_with_knowledge._execution_count == initial_count + 1
        assert skill_with_knowledge._last_execution == 5

    def test_execute_raises_when_not_initialized(self):
        skill = ResearchSkill(knowledge_store=None)
        with pytest.raises(SkillExecutionError):
            skill.execute({})

    def test_get_resource_usage(self, skill_with_knowledge):
        usage = skill_with_knowledge.get_resource_usage()
        assert usage["energy_cost"] == 5.0
        assert usage["duration_s"] == 0.1
        assert usage["memory_mb"] == 10.0

    def test_get_status_contains_fields(self, skill_with_knowledge):
        status = skill_with_knowledge.get_status()
        assert status["name"] == "research"
        assert status["version"] == "1.0.0"
        assert status["initialized"] is True
        assert "execution_count" in status
        assert "last_execution" in status
        assert "knowledge_entries" in status

    def test_shutdown_cleans_up(self, skill_with_knowledge):
        skill_with_knowledge.shutdown()
        assert skill_with_knowledge.question_generator is None
        assert skill_with_knowledge.experiment_designer is None
        assert skill_with_knowledge._initialized is False
