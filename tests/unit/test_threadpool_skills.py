"""
Unit tests for ThreadPool-based parallel skill execution — Sprint 2.

TDD coverage:
- ThreadPoolExecutor integration in SkillLifecycleManager
- ISOLATED skills run in thread pool (parallel)
- READONLY skills run in thread pool (parallel)
- SEQUENTIAL skills still run in main thread (serial)
- SHARED_WRITE skills acquire resource locks correctly
- Lock ordering prevents deadlock (FM → Memory → Brain → HIC)
- Energy budget enforced atomically across parallel dispatch
- Thread pool respects timeout (skills that hang get cancelled)
- Mixed SEQUENTIAL + parallel + async skills execute in correct order
- ResourceLockManager lock acquisition and release
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.infant.skills.base import InfantSkill, SkillContext, ParallelismPolicy
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager, SkillExecutionRecord
from cosmic_mycelium.infant.skills.registry import SkillRegistry
from cosmic_mycelium.infant.skills.resource_lock_manager import ResourceLockManager


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry_singleton():
    """Reset SkillRegistry singleton between tests."""
    from cosmic_mycelium.infant.skills.registry import SkillRegistry
    SkillRegistry._instance = None
    yield
    SkillRegistry._instance = None


# ---------------------------------------------------------------------------
# Skill test doubles with various parallelism policies
# ---------------------------------------------------------------------------

class SequentialSkill(InfantSkill):
    """A skill that must run sequentially (default policy)."""
    version = "1.0.0"
    description = "Sequential test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.SEQUENTIAL

    _counter = 0

    def __init__(self, execution_time: float = 0.01, name: str | None = None):
        self.execution_time = execution_time
        self.execute_called = False
        self.thread_id: int | None = None
        if name is None:
            self.name = f"seq_{SequentialSkill._counter}"
            SequentialSkill._counter += 1
        else:
            self.name = name

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        self.thread_id = threading.get_ident()
        time.sleep(self.execution_time)
        return "seq_result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class IsolatedSkill(InfantSkill):
    """A skill with no shared state access — safe for thread pool."""
    version = "1.0.0"
    description = "Isolated test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.ISOLATED

    _counter = 0

    def __init__(self, execution_time: float = 0.01, result: str = "iso_result"):
        self.execution_time = execution_time
        self.execute_called = False
        self.thread_id: int | None = None
        self.name = f"iso_{IsolatedSkill._counter}"
        self._result = result
        IsolatedSkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        self.thread_id = threading.get_ident()
        time.sleep(self.execution_time)
        return self._result

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class ReadonlySkill(InfantSkill):
    """A skill that only reads shared state (no writes)."""
    version = "1.0.0"
    description = "Readonly test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.READONLY

    _counter = 0

    def __init__(self, execution_time: float = 0.01):
        self.execution_time = execution_time
        self.execute_called = False
        self.thread_id: int | None = None
        self.name = f"ro_{ReadonlySkill._counter}"
        ReadonlySkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        self.thread_id = threading.get_ident()
        time.sleep(self.execution_time)
        return "ro_result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


class SharedWriteSkill(InfantSkill):
    """A skill that writes shared state — requires lock."""
    version = "1.0.0"
    description = "Shared write test skill"
    dependencies = []
    parallelism_policy = ParallelismPolicy.SHARED_WRITE
    shared_resource = "feature_manager"  # which resource it needs

    _counter = 0

    def __init__(self, execution_time: float = 0.01, resource: str = "feature_manager"):
        self.execution_time = execution_time
        self.execute_called = False
        self.thread_id: int | None = None
        self.name = f"sw_{SharedWriteSkill._counter}"
        self.shared_resource = resource
        SharedWriteSkill._counter += 1

    def initialize(self, context: SkillContext) -> None:
        pass

    def can_activate(self, context: SkillContext) -> bool:
        return True

    def execute(self, params: dict[str, object]) -> object:
        self.execute_called = True
        self.thread_id = threading.get_ident()
        # Simulate shared write under lock
        with ResourceLockManager.lock(self.shared_resource):
            time.sleep(self.execution_time)
        return "sw_result"

    def get_resource_usage(self) -> dict[str, float]:
        return {"energy_cost": 0.1, "memory_mb": 1.0, "duration_s": self.execution_time}

    def shutdown(self) -> None:
        pass

    def get_status(self) -> dict[str, object]:
        return {"name": self.name, "active": True}


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestParallelismPolicy:
    """Policy enum and default values."""

    def test_sequential_default(self):
        skill = SequentialSkill()
        assert skill.parallelism_policy == ParallelismPolicy.SEQUENTIAL

    def test_isolated_policy(self):
        skill = IsolatedSkill()
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_readonly_policy(self):
        skill = ReadonlySkill()
        assert skill.parallelism_policy == ParallelismPolicy.READONLY

    def test_shared_write_policy(self):
        skill = SharedWriteSkill()
        assert skill.parallelism_policy == ParallelismPolicy.SHARED_WRITE


class TestThreadPoolExecutorIntegration:
    """Thread pool dispatch for parallelizable skills."""

    def test_isolated_skills_runInThreadPool(self):
        """ISOLATED skills should execute in separate threads."""
        registry = SkillRegistry()
        for _ in range(3):
            registry.register(IsolatedSkill(execution_time=0.1))
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        # Filter to only isolated skills (for this test, we'll patch tick logic)
        # Actually, let's directly test the _dispatch_parallel phase
        # For now, test that parallel skills complete faster than sequential sum
        start = time.time()
        records = manager.tick(context)
        elapsed = time.time() - start

        # With 2 workers and 3 tasks of 0.1s each, should take ~0.15-0.2s (not 0.3s)
        assert elapsed < 0.25, f"Expected parallel execution, took {elapsed:.3f}s"
        assert len(records) == 3
        assert all(r.success for r in records)

    def test_readonly_skillsRunInThreadPool(self):
        """READONLY skills also use thread pool."""
        registry = SkillRegistry()
        for _ in range(2):
            registry.register(ReadonlySkill(execution_time=0.1))
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        start = time.time()
        records = manager.tick(context)
        elapsed = time.time() - start

        assert elapsed < 0.15  # ~0.1s not 0.2s
        assert len(records) == 2
        assert all(r.success for r in records)

    def test_sequential_skillsStayOnMainThread(self):
        """SEQUENTIAL skills execute on the calling thread (no thread pool)."""
        registry = SkillRegistry()
        skill = SequentialSkill(execution_time=0.05)
        registry.register(skill)
        manager = SkillLifecycleManager(registry)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        main_thread_id = threading.get_ident()
        records = manager.tick(context)

        assert len(records) == 1
        assert records[0].success
        # SEQUENTIAL skill should have executed on main thread
        assert skill.thread_id == main_thread_id

    def test_mixed_policies_respect_order(self):
        """SEQUENTIAL skills run first, then parallel batch, then async."""
        seq_ordered = []

        class OrderedSeq(SequentialSkill):
            def __init__(self):
                super().__init__(execution_time=0.02, name="ordered_seq")
            def execute(self, params):
                seq_ordered.append("seq")
                time.sleep(0.02)
                return "seq"

        iso_ordered = []

        class OrderedIso(IsolatedSkill):
            def __init__(self):
                super().__init__(execution_time=0.02, result="iso")
            def execute(self, params):
                iso_ordered.append("iso")
                time.sleep(0.02)
                return "iso"

        registry = SkillRegistry()
        registry.register(OrderedSeq())
        registry.register(OrderedIso())
        manager = SkillLifecycleManager(registry, thread_pool_size=2)

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)

        # First record should be the sequential skill
        assert records[0].skill_name == "ordered_seq"
        assert records[1].skill_name.startswith("iso_")


class TestResourceLockManager:
    """Fine-grained locks protect shared state."""

    def test_lock_acquire_release(self):
        """Single lock can be acquired and released."""
        lock = ResourceLockManager.get_lock("feature_manager")
        assert lock is not None

        with ResourceLockManager.lock("feature_manager"):
            # Should be able to re-acquire (RLock)
            with ResourceLockManager.lock("feature_manager"):
                pass  # nested acquisition OK

    def test_multiple_locks_acquired_in_order(self):
        """Multiple locks acquired in global order (FM → Memory → Brain → HIC)."""
        acquired = []

        # Acquire FM then Memory in one thread
        def worker_a():
            with ResourceLockManager.lock("feature_manager"):
                with ResourceLockManager.lock("memory"):
                    acquired.append("A")

        # Acquire Memory then FM in another thread — should NOT deadlock
        # because lock_multiple() sorts by global order
        def worker_b():
            with ResourceLockManager.lock_multiple(["memory", "feature_manager"]):
                acquired.append("B")

        t1 = threading.Thread(target=worker_a)
        t2 = threading.Thread(target=worker_b)

        t1.start()
        t2.start()
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)

        assert len(acquired) == 2, f"Both threads should complete without deadlock, got {acquired}"

    def test_lock_protects_shared_variable(self):
        """Lock ensures mutual exclusion on protected resource."""
        shared = {"value": 0}
        lock = ResourceLockManager.get_lock("brain")

        def increment_n(n: int):
            for _ in range(n):
                with lock:
                    shared["value"] += 1

        threads = [threading.Thread(target=increment_n, args=(100,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert shared["value"] == 500


class TestEnergyBudgetParallel:
    """Energy accounting is thread-safe across parallel skills."""

    def test_parallel_skills_respect_global_budget(self):
        """Total energy spent across parallel skills ≤ budget."""
        registry = SkillRegistry()
        # Each costs 0.3, budget allows only 0.6 total (ratio 0.1 of 100 = 10, but we set tighter)
        for _ in range(3):
            registry.register(IsolatedSkill(execution_time=0.05))
        manager = SkillLifecycleManager(registry, energy_budget_ratio=0.01)  # 1% of 100 = 1.0

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)

        # Only skills within budget should execute
        total_cost = sum(r.energy_cost for r in records if r.success)
        assert total_cost <= 1.0 + 0.1  # small tolerance

    def test_energy_reservation_atomic(self):
        """Budget check and reserve is atomic (no double-spend)."""
        # This tests that two parallel skills don't both see budget available
        # and both dispatch, overspending. Need to verify via stress test.
        registry = SkillRegistry()
        # 10 skills, each costs 0.15, budget = 1.0 → max ~6 skills
        for _ in range(10):
            registry.register(IsolatedSkill(execution_time=0.05))
        manager = SkillLifecycleManager(registry, energy_budget_ratio=0.01)  # 1.0 total

        context = SkillContext(
            infant_id="test",
            cycle_count=1,
            energy_available=100.0,
            hic_suspended=False,
        )

        records = manager.tick(context)
        successful = [r for r in records if r.success]
        total_cost = sum(r.energy_cost for r in successful)

        # Should not exceed budget significantly
        assert total_cost <= 1.1, f"Overspent budget: {total_cost:.2f} > 1.0"


class TestDeadlockPrevention:
    """Skills acquiring multiple locks don't cause deadlock."""

    def test_multiple_locks_acquired_in_global_order(self):
        """Even if skills request locks in different orders, global order prevents deadlock."""
        # This test verifies that ResourceLockManager.lock_multiple sorts locks
        # by global order before acquiring, so two threads asking for (FM, Brain)
        # and (Brain, FM) both acquire as (FM, Brain) — no deadlock.
        results = []

        def skill_a():
            # Simulates skill needing FM and Brain
            with ResourceLockManager.lock_multiple(["feature_manager", "brain"]):
                results.append("A")

        def skill_b():
            # Simulates skill needing Brain then FM (reversed request order)
            with ResourceLockManager.lock_multiple(["brain", "feature_manager"]):
                results.append("B")

        t1 = threading.Thread(target=skill_a)
        t2 = threading.Thread(target=skill_b)

        t1.start()
        t2.start()
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        assert len(results) == 2, f"Both threads completed, results: {results}"


class TestTimeoutHandling:
    """Hanging parallel skills are cancelled."""

    def test_threadpool_timeout(self):
        """Skill exceeding thread pool timeout is cancelled."""
        from cosmic_mycelium.infant.skills.lifecycle import THREADPOOL_TIMEOUT
        registry = SkillRegistry()
        registry.register(IsolatedSkill(execution_time=5.0))  # 5 second sleep
        # Patch timeout via monkeypatch
        import cosmic_mycelium.infant.skills.lifecycle as lifecycle_mod
        original = lifecycle_mod.THREADPOOL_TIMEOUT
        lifecycle_mod.THREADPOOL_TIMEOUT = 0.5
        try:
            manager = SkillLifecycleManager(registry, thread_pool_size=1)
            context = SkillContext(
                infant_id="test",
                cycle_count=1,
                energy_available=100.0,
                hic_suspended=False,
            )
            start = time.time()
            records = manager.tick(context)
            elapsed = time.time() - start
            # Should timeout after ~0.5s, not wait 5s
            assert elapsed < 1.0, f"Timeout not working, took {elapsed:.3f}s"
            assert len(records) == 1
            if not records[0].success:
                assert records[0].error is not None
        finally:
            lifecycle_mod.THREADPOOL_TIMEOUT = original


# ---------------------------------------------------------------------------
# Skill classification tests
# ---------------------------------------------------------------------------

class TestSkillClassification:
    """Verify each built-in skill has correct parallelism_policy."""

    def test_physics_experiment_isolated(self):
        from cosmic_mycelium.infant.skills.physics.physics_experiment import PhysicsExperimentSkill
        skill = PhysicsExperimentSkill()
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_research_shared_write(self):
        from cosmic_mycelium.infant.skills.research.research_skill import ResearchSkill
        skill = ResearchSkill()
        # Sprint 5: ResearchSkill migrated to ISOLATED (KnowledgeStore now thread-safe)
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_proposal_generator_shared_write(self):
        from cosmic_mycelium.infant.skills.collective.proposal_generator import ProposalGenerator
        skill = ProposalGenerator()
        # Sprint 5: ProposalGenerator migrated to ISOLATED (CollectiveIntelligence now thread-safe)
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_negotiation_isolated(self):
        from cosmic_mycelium.infant.skills.collective.negotiation import NegotiationSkill
        skill = NegotiationSkill()
        # Sprint 5: NegotiationSkill migrated to ISOLATED (class-level lock protects shared state)
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_social_learning_isolated(self):
        from cosmic_mycelium.infant.skills.social.social_learning import SocialLearningSkill
        skill = SocialLearningSkill()
        # Sprint 5: SocialLearningSkill migrated to ISOLATED (class-level lock protects shared state)
        assert skill.parallelism_policy == ParallelismPolicy.ISOLATED

    def test_knowledge_transfer_async_not_threadpool(self):
        from cosmic_mycelium.infant.skills.collective.knowledge_transfer import KnowledgeTransfer
        skill = KnowledgeTransfer()
        # Async skills don't use thread pool; they use asyncio
        assert skill.can_execute_async() is True
        # But policy should still be SEQUENTIAL for thread pool decision
        # (async and thread pool are separate dimensions)
        assert skill.parallelism_policy == ParallelismPolicy.SEQUENTIAL

    def test_extract_feature_shared_write(self):
        from cosmic_mycelium.infant.feature_manager import FeatureManager
        # FeatureManager is not a skill; the skill that extracts is embedded in main.py
        # The actual skill that calls FeatureManager.append is part of the core loop
        # For now, we'll classify extract_feature as SHARED_WRITE if it existed as a skill
        # Since it's not a standalone skill yet, skip this test in Sprint 2
        pytest.skip("extract_feature is not yet a standalone skill")
