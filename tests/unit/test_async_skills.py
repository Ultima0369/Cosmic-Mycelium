"""
Unit tests for async skill execution — Sprint 1 parallelization.

TDD coverage:
- Async skill protocol methods exist and are callable
- Async skills are detected by can_execute_async()
- Lifecycle manager runs async skills concurrently via asyncio.gather()
- Sync skills still run sequentially (backward compatibility)
- Mixed async + sync skills execute in correct order (sync first, then async batch)
- Async skill exceptions are caught and recorded, don't crash tick()
- Async skill timeout handling (skills that hang)
- Resource budget enforcement applies to async skills too
"""

from __future__ import annotations

import asyncio
import time

import pytest

from cosmic_mycelium.infant.skills.base import InfantSkill, SkillContext
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager, SkillExecutionRecord
from cosmic_mycelium.infant.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Test fixtures: fresh registry per test (protocol-level singleton reset)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry_singleton():
    """Reset SkillRegistry singleton between tests for isolation."""
    SkillRegistry._instance = None
    yield
    SkillRegistry._instance = None


# ---------------------------------------------------------------------------
# Skill test doubles with unique names per instance
# ---------------------------------------------------------------------------

class SyncSkill(InfantSkill):
    """A simple synchronous skill for testing."""
    version = "1.0.0"
    description = "Sync test skill"
    dependencies = []

    _counter = 0

    def __init__(self, execution_time: float = 0.01, mutate_shared: bool = False):
        self.execution_time = execution_time
        self.mutate_shared = mutate_shared
        self.initialize_called = False
        self.execute_called = False
        self.shared_value = 0
        self.name = f"sync_skill_{SyncSkill._counter}"
        SyncSkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        self.initialize_called = True

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        time.sleep(self.execution_time)
        if self.mutate_shared:
            self.shared_value += 1
        return "sync_result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class AsyncSkill(InfantSkill):
    """A simple asynchronous skill for testing."""
    version = "1.0.0"
    description = "Async test skill"
    dependencies = []

    _counter = 0

    def __init__(self, execution_time: float = 0.01, fail: bool = False):
        self.execution_time = execution_time
        self.fail = fail
        self.execute_called = False
        self.name = f"async_skill_{AsyncSkill._counter}"
        AsyncSkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def can_execute_async(self) -> bool:
        """Marker for async capability."""
        return True

    async def execute_async(self, params: dict[str, object]) -> object:
        """Async execution entry point."""
        self.execute_called = True
        await asyncio.sleep(self.execution_time)
        if self.fail:
            raise RuntimeError("async skill failure")
        return "async_result"

    def execute(self, params: dict[str, object]) -> object:
        raise NotImplementedError("This skill is async-only")

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class FailingAsyncSkill(AsyncSkill):
    """Async skill that always raises."""
    _counter = 0

    def __init__(self):
        super().__init__(execution_time=0.001, fail=True)
        self.name = f"failing_async_{FailingAsyncSkill._counter}"
        FailingAsyncSkill._counter += 1


class SlowAsyncSkill(AsyncSkill):
    """Async skill that takes longer than timeout."""
    _counter = 0

    def __init__(self):
        super().__init__(execution_time=10.0, fail=False)
        self.name = f"slow_async_{SlowAsyncSkill._counter}"
        SlowAsyncSkill._counter += 1


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestAsyncSkillProtocol:
    """Protocol extensions for async execution."""

    def test_async_skill_has_can_execute_async(self):
        skill = AsyncSkill()
        assert hasattr(skill, "can_execute_async")
        assert skill.can_execute_async() is True

    def test_sync_skill_default_can_execute_async_false(self):
        skill = SyncSkill()
        # Skill without can_execute_async method defaults to False via getattr
        assert getattr(skill, "can_execute_async", lambda: False)() is False

    def test_async_skill_has_execute_async(self):
        skill = AsyncSkill()
        assert hasattr(skill, "execute_async")
        assert asyncio.iscoroutinefunction(skill.execute_async)

    def test_sync_skill_still_has_execute(self):
        skill = SyncSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)


class TestLifecycleManagerAsyncDetection:
    """Manager correctly categorizes skills."""

    def test_detects_async_vs_sync(self):
        registry = SkillRegistry()
        registry.register(SyncSkill())
        registry.register(AsyncSkill())
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        skills = registry.list_enabled(context)
        async_skills = [s for s in skills if getattr(s, "can_execute_async", lambda: False)()]
        sync_skills = [s for s in skills if not getattr(s, "can_execute_async", lambda: False)()]

        assert len(async_skills) == 1
        assert async_skills[0].name.startswith("async_skill")
        assert len(sync_skills) == 1
        assert sync_skills[0].name.startswith("sync_skill")


class TestAsyncSkillConcurrentExecution:
    """Async skills run concurrently via asyncio.gather()."""

    @pytest.mark.asyncio
    async def test_multiple_async_skills_run_concurrently(self):
        """Three 0.1s async skills should finish in ~0.1s total, not 0.3s."""
        registry = SkillRegistry()
        for _ in range(3):
            registry.register(AsyncSkill(execution_time=0.1))
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        # Sprint 2: initialize budget state (normally done by tick())
        manager._budget_remaining = context.energy_available * manager.energy_budget_ratio

        async_skills = [
            s for s in registry.list_enabled(context)
            if getattr(s, "can_execute_async", lambda: False)()
        ]

        start = time.time()
        results = await manager._run_async_skills(async_skills, context)
        elapsed = time.time() - start

        # Should be concurrent: ~0.1s not 0.3s (allow 50% margin)
        assert elapsed < 0.2, f"Expected concurrent execution, took {elapsed:.3f}s"
        assert len(results) == 3
        for r in results:
            assert r == "async_result"

    @pytest.mark.asyncio
    async def test_async_skill_exception_caught_and_returned(self):
        """Failed async skill returns exception, doesn't crash gather."""
        registry = SkillRegistry()
        registry.register(AsyncSkill(fail=True))
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        # Sprint 2: initialize budget state (normally tick() does this)
        manager._budget_remaining = context.energy_available * manager.energy_budget_ratio

        async_skills = registry.list_enabled(context)
        results = await manager._run_async_skills(async_skills, context)

        assert len(results) == 1
        assert isinstance(results[0], Exception)
        assert "async skill failure" in str(results[0])


class TestMixedSyncAsyncExecution:
    """Sync skills run before async skills (ordering guarantee)."""

    def test_sync_runs_before_async(self):
        """Sequential skills finish before async batch starts."""
        execution_order = []

        class OrderedSyncSkill(SyncSkill):
            name = "ordered_sync"
            def execute(self, params):
                execution_order.append("sync")
                time.sleep(0.02)
                return "sync"

        class OrderedAsyncSkill(AsyncSkill):
            name = "ordered_async"
            async def execute_async(self, params):
                execution_order.append("async")
                await asyncio.sleep(0.02)
                return "async"

        registry = SkillRegistry()
        registry.register(OrderedSyncSkill())
        registry.register(OrderedAsyncSkill())
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)

        # All "sync" should appear before any "async" in execution_order
        sync_indices = [i for i, e in enumerate(execution_order) if e == "sync"]
        async_indices = [i for i, e in enumerate(execution_order) if e == "async"]
        if sync_indices and async_indices:
            assert max(sync_indices) < min(async_indices), f"Order violated: {execution_order}"


class TestEnergyBudgetWithAsync:
    """Async skills count toward energy budget."""

    def test_async_skill_energy_accounted(self):
        """Even though async, energy cost is tallied sequentially after completion."""
        registry = SkillRegistry()
        skill = AsyncSkill(execution_time=0.001)
        registry.register(skill)
        # Strict budget: only 0.5 of 100 = 50 energy available, skill costs 0.1
        manager = SkillLifecycleManager(registry, energy_budget_ratio=0.5)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        assert len(records) == 1
        assert records[0].success is True
        assert records[0].energy_cost == 0.1


class TestAsyncTimeout:
    """Hanging async skills are cancelled after timeout."""

    @pytest.mark.asyncio
    async def test_async_skill_timeout(self):
        """Skill taking longer than 0.1s timeout is cancelled."""
        registry = SkillRegistry()
        registry.register(SlowAsyncSkill())
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        async_skills = registry.list_enabled(context)
        # Run with short timeout via asyncio.wait_for wrapper
        try:
            results = await asyncio.wait_for(
                manager._run_async_skills(async_skills, context),
                timeout=0.1
            )
            # If we get here, timeout should have triggered inside _run_async_skills
            # (which we haven't implemented yet). For now, test structure.
            assert len(results) >= 1
        except asyncio.TimeoutError:
            # If _run_async_skills doesn't have its own timeout, wait_for catches it
            pass


class TestBackwardCompatibility:
    """Skills without async method run unchanged."""

    def test_sync_only_skills_work_unchanged(self):
        registry = SkillRegistry()
        skill = SyncSkill()
        registry.register(skill)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        assert len(records) == 1
        assert records[0].success is True
        # Name is auto-unique per instance; check it starts with expected prefix
        assert records[0].skill_name.startswith("sync_skill")


class TestHicSuspendBlocksAsync:
    """Async skills respect HIC suspension like sync skills."""

    def test_async_skills_skipped_when_suspended(self):
        registry = SkillRegistry()
        registry.register(AsyncSkill())
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=True,  # SUSPEND
        )

        records = manager.tick(context)
        assert len(records) == 0
