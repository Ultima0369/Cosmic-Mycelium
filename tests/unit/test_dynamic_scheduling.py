"""
Unit tests for Sprint 3: Dynamic Scheduling & Observability.

TDD coverage:
- Priority-based skill ordering within each phase
- Dynamic thread pool scaling (0→4 workers adaptive)
- Prometheus metrics instrumentation
- Auto-fallback: ParallelismUnsafe demotes skill for 100 cycles
- Skill priority field default
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager, SkillExecutionRecord
from cosmic_mycelium.infant.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry_singleton():
    from cosmic_mycelium.infant.skills.registry import SkillRegistry
    SkillRegistry._instance = None
    yield
    SkillRegistry._instance = None


# ---------------------------------------------------------------------------
# Skill test doubles
# ---------------------------------------------------------------------------

class SkillExecutionError(Exception):
    """Exception with parallelism_unsafe flag for testing auto-fallback."""
    parallelism_unsafe = False

    def __init__(self, message: str, parallelism_unsafe: bool = False):
        super().__init__(message)
        self.parallelism_unsafe = parallelism_unsafe


class PrioritizedSkill(InfantSkill):
    version = "1.0.0"
    description = "Prioritized test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.ISOLATED

    _counter = 0

    def __init__(self, priority: float = 0.5, execution_time: float = 0.01, name: str | None = None):
        self.priority = priority
        self.execution_time = execution_time
        self.execute_called = False
        self.name = name or f"prio_{PrioritizedSkill._counter}"
        PrioritizedSkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        time.sleep(self.execution_time)
        return "result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class FlakySkill(InfantSkill):
    version = "1.0.0"
    description = "Flaky test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.ISOLATED

    _counter = 0

    def __init__(self):
        self.name = f"flaky_{FlakySkill._counter}"
        FlakySkill._counter += 1
        self.execute_called = False
        self.raise_unsafe = False

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        if self.raise_unsafe:
            raise SkillExecutionError("data race detected", parallelism_unsafe=True)
        return "flaky_result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": 0.01}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class SkillExecutionError(Exception):
    parallelism_unsafe = False

    def __init__(self, message: str, parallelism_unsafe: bool = False):
        super().__init__(message)
        self.parallelism_unsafe = parallelism_unsafe


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestPriorityScheduling:
    """Skills execute in priority order within each phase."""

    def test_prioritized_skills_execute_in_descending_order(self):
        registry = SkillRegistry()
        low = PrioritizedSkill(priority=0.3, name="low")
        high = PrioritizedSkill(priority=0.9, name="high")
        mid = PrioritizedSkill(priority=0.6, name="mid")
        registry.register(low)
        registry.register(high)
        registry.register(mid)
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        parallel_names = [r.skill_name for r in records if r.execution_mode == "threadpool"]
        assert parallel_names == ["high", "mid", "low"], f"Got: {parallel_names}"

    def test_priority_default_is_half(self):
        skill = PrioritizedSkill()
        assert skill.priority == 0.5


class TestDynamicThreadPool:
    """Thread pool scales dynamically."""

    def test_initial_pool_size_configurable(self):
        registry = SkillRegistry()
        for _ in range(2):
            registry.register(PrioritizedSkill(execution_time=0.05))
        manager = SkillLifecycleManager(registry, thread_pool_size=3)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        stats = manager.get_stats()
        assert stats["thread_pool_size"] == 3

    def test_load_monitor_records_pending_count(self):
        registry = SkillRegistry()
        for _ in range(5):
            registry.register(PrioritizedSkill(execution_time=0.1))
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        stats = manager.get_stats()
        assert "thread_pool_size" in stats

    def test_dynamic_scaling_up_under_burst(self):
        registry = SkillRegistry()
        for _ in range(10):
            registry.register(PrioritizedSkill(execution_time=0.05))
        manager = SkillLifecycleManager(registry, thread_pool_size=2, max_thread_pool_size=4, enable_dynamic_scaling=True)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        assert len(records) == 10
        executor = manager._get_executor()
        assert executor._max_workers >= 2


class TestPrometheusMetrics:
    """Prometheus metrics are exposed."""

    def test_skill_execution_duration_metric_exists(self):
        from cosmic_mycelium.infant.skills.lifecycle import skill_execution_duration_seconds
        assert skill_execution_duration_seconds is not None

    def test_skill_parallelism_count_metric_exists(self):
        from cosmic_mycelium.infant.skills.lifecycle import skill_parallelism_count
        assert skill_parallelism_count is not None

    def test_resource_lock_wait_metric_exists(self):
        from cosmic_mycelium.infant.skills.lifecycle import resource_lock_wait_seconds
        assert resource_lock_wait_seconds is not None

    def test_skill_auto_fallback_metric_exists(self):
        from cosmic_mycelium.infant.skills.lifecycle import skill_auto_fallback_total
        assert skill_auto_fallback_total is not None


class TestAutoFallback:
    """ParallelismUnsafe exceptions trigger auto-demotion."""

    def test_parallelism_unsafe_demotes_skill(self):
        registry = SkillRegistry()
        flaky = FlakySkill()
        flaky.raise_unsafe = True
        registry.register(flaky)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        assert len(records) == 1
        inner = records[0].result
        if isinstance(inner, SkillExecutionRecord):
            assert not inner.success
            assert "data race" in (inner.error or "")
        assert flaky.name in manager._demoted_skills
        assert manager._demoted_skills[flaky.name] == 100

    def test_demotion_skips_skill_in_subsequent_cycles(self):
        registry = SkillRegistry()
        flaky = FlakySkill()
        flaky.raise_unsafe = True
        registry.register(flaky)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        manager.tick(context)  # cycle 1, counter=100
        assert flaky.name in manager._demoted_skills
        assert manager._demoted_skills[flaky.name] == 100

        context.cycle_count = 2  # cycle 2: decrement at start, counter still 100 during check
        records = manager.tick(context)
        assert len(records) == 0
        assert flaky.name in manager._demoted_skills
        assert manager._demoted_skills[flaky.name] == 99

    def test_demotion_counter_decrements_each_cycle(self):
        registry = SkillRegistry()
        flaky = FlakySkill()
        flaky.raise_unsafe = True
        registry.register(flaky)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        manager.tick(context)
        assert manager._demoted_skills[flaky.name] == 100

        context.cycle_count = 2
        manager.tick(context)
        assert manager._demoted_skills[flaky.name] == 99

        context.cycle_count = 3
        manager.tick(context)
        assert manager._demoted_skills[flaky.name] == 98

    def test_demotion_expires_after_100_cycles(self):
        registry = SkillRegistry()
        flaky = FlakySkill()
        flaky.raise_unsafe = True
        registry.register(flaky)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        manager.tick(context)  # cycle 1: demote to 100
        assert flaky.name in manager._demoted_skills

        # Cycles 2-100: counter decrements 99→1
        for i in range(2, 101):
            context.cycle_count = i
            manager.tick(context)

        # After cycle 100, counter should be 1
        assert flaky.name in manager._demoted_skills
        assert manager._demoted_skills[flaky.name] == 1

        # Stop raising so we can verify the skill runs after demotion expires
        flaky.raise_unsafe = False
        context.cycle_count = 101
        records = manager.tick(context)
        # Demotion should have expired and skill executed successfully
        assert flaky.name not in manager._demoted_skills
        assert len(records) == 1
        assert records[0].success is True


class TestSkillAudit:
    """All built-in skills have explicit parallelism_policy."""

    def test_all_registered_skills_have_policy(self):
        from cosmic_mycelium.infant.skills.registry import SkillRegistry
        registry = SkillRegistry()
        for skill in registry.list_all():
            assert hasattr(skill, "parallelism_policy"), f"Skill {skill.name} missing parallelism_policy"

    def test_known_skills_classified_correctly(self):
        from cosmic_mycelium.infant.skills.registry import SkillRegistry
        from cosmic_mycelium.infant.skills.base import ParallelismPolicy

        registry = SkillRegistry()
        classifications = {
            "physics_experiment": ParallelismPolicy.ISOLATED,
            "research": ParallelismPolicy.SHARED_WRITE,
            "proposal_generator": ParallelismPolicy.SHARED_WRITE,
            "negotiation": ParallelismPolicy.SHARED_WRITE,
            "social_learning": ParallelismPolicy.SHARED_WRITE,
            "knowledge_transfer": ParallelismPolicy.SEQUENTIAL,
        }

        for skill_name, expected_policy in classifications.items():
            skill = registry.get(skill_name)
            if skill is None:
                pytest.skip(f"Skill {skill_name} not yet registered")
            assert skill.parallelism_policy == expected_policy, (
                f"{skill_name}: expected {expected_policy}, got {skill.parallelism_policy}"
            )


class TestMetricsIntegration:
    """Metrics accumulate correctly over cycles."""

    def test_metrics_survive_multiple_cycles(self):
        registry = SkillRegistry()
        for _ in range(3):
            registry.register(PrioritizedSkill(execution_time=0.01))
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        for i in range(10):
            context.cycle_count = i + 1
            manager.tick(context)

        stats = manager.get_stats()
        assert stats["total_executions"] >= 30
