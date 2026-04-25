"""
Skill Lifecycle Manager — 技能生命周期管理器 (Sprint 3: Dynamic Scheduling & Observability)

负责技能的启用/禁用、周期调度、资源核算和 HIC 悬置响应。
支持：同步顺序执行、异步并发 (asyncio)、线程池 CPU 并行、动态调度、优先级、指标。
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field

from cosmic_mycelium.infant.skills.base import (
    InfantSkill,
    ParallelismPolicy,
    SkillContext,
    SkillExecutionError,
)
from cosmic_mycelium.infant.skills.registry import SkillRegistry
from cosmic_mycelium.infant.skills.resource_lock_manager import ResourceLockManager

# Async skills timeout (seconds)
ASYNCIO_TIMEOUT = 5.0
# Thread pool timeout (seconds)
THREADPOOL_TIMEOUT = 5.0

# Sprint 3: Prometheus metrics (lazy-import to avoid hard dependency)
try:
    from prometheus_client import Counter, Gauge, Histogram

    skill_execution_duration_seconds = Histogram(
        "skill_execution_duration_seconds",
        "Skill execution duration by name and mode",
        ["skill_name", "execution_mode"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    skill_parallelism_count = Gauge(
        "skill_parallelism_count",
        "Number of skills executing in parallel (by mode)",
        ["mode"],
    )
    resource_lock_wait_seconds = Histogram(
        "resource_lock_wait_seconds",
        "Time spent waiting for resource locks",
        ["resource_name"],
        buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    )
    skill_auto_fallback_total = Counter(
        "skill_auto_fallback_total",
        "Total number of auto-fallback demotions due to ParallelismUnsafe",
        ["skill_name"],
    )
    # Sprint 4: Enhanced skill-level resource metrics
    skill_energy_cost_total = Counter(
        "skill_energy_cost_total",
        "Total energy consumed by skill",
        ["skill_name"],
    )
    skill_execution_count = Counter(
        "skill_execution_count",
        "Total number of skill executions",
        ["skill_name", "execution_mode", "success"],
    )
    skill_last_success_timestamp = Gauge(
        "skill_last_success_timestamp",
        "Unix timestamp of last successful execution",
        ["skill_name"],
    )
    skill_budget_skips_total = Counter(
        "skill_budget_skips_total",
        "Total number of skills skipped due to energy budget exhaustion",
        ["skill_name"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    # Prometheus not available — use no-op stubs
    _METRICS_AVAILABLE = False

    class _NoopMetric:
        def observe(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    skill_execution_duration_seconds = _NoopMetric()
    skill_parallelism_count = _NoopMetric()
    resource_lock_wait_seconds = _NoopMetric()
    skill_auto_fallback_total = _NoopMetric()
    skill_energy_cost_total = _NoopMetric()
    skill_execution_count = _NoopMetric()
    skill_last_success_timestamp = _NoopMetric()
    skill_budget_skips_total = _NoopMetric()


@dataclass
class SkillExecutionRecord:
    """单次技能执行记录（用于审计和性能分析）。"""
    skill_name: str
    params: dict
    start_time: float
    end_time: float = 0.0
    success: bool = False
    error: str | None = None
    energy_cost: float = 0.0
    result: Any = None
    thread_id: int | None = None  # Sprint 2: track which thread/async task executed
    execution_mode: str = "sync"  # "sync" | "threadpool" | "async"


class SkillLifecycleManager:
    """
    管理技能的全生命周期（支持并行化）。

    Sprint 2 增强：
    - 线程池并行执行 ISOLATED / READONLY 技能
    - 细粒度资源锁（ResourceLockManager）保护共享状态
    - 原子性能量预分配（防超支）
    - 执行模式追踪（同步/线程池/异步）
    """

    def __init__(
        self,
        registry: SkillRegistry,
        max_executions_per_cycle: int = 5,
        energy_budget_ratio: float = 0.1,
        thread_pool_size: int = 2,
        min_thread_pool_size: int = 0,
        max_thread_pool_size: int = 4,
        enable_dynamic_scaling: bool = True,
    ):
        """
        Args:
            registry: 全局技能注册表
            max_executions_per_cycle: 单周期最多执行技能次数
            energy_budget_ratio: 技能消耗占当前能量的最大比例
            thread_pool_size: 初始线程池大小
            min_thread_pool_size: 动态缩小时最小工作线程数
            max_thread_pool_size: 动态扩增时最大工作线程数
            enable_dynamic_scaling: 是否启用动态线程池调整
        """
        self.registry = registry
        self.max_executions = max_executions_per_cycle
        self.energy_budget_ratio = energy_budget_ratio
        self.thread_pool_size = thread_pool_size
        self.min_thread_pool_size = min_thread_pool_size
        self.max_thread_pool_size = max_thread_pool_size
        self.enable_dynamic_scaling = enable_dynamic_scaling
        self.execution_history: list[SkillExecutionRecord] = []
        self._disabled_skills: set[str] = set()

        # Sprint 2: atomic budget state
        self._budget_lock = threading.Lock()
        self._budget_remaining: float = 0.0
        self._spent_energy: float = 0.0

        # Sprint 3: auto-fallback state
        self._demoted_skills: dict[str, int] = {}  # skill_name -> remaining_cycles
        self._demotion_duration = 100  # cycles to keep demoted

        # Thread pool (lazy init on first use)
        self._executor: ThreadPoolExecutor | None = None
        self._load_monitor_lock = threading.Lock()
        self._pending_parallel_count = 0  # for dynamic scaling decisions

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor with dynamic sizing."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.thread_pool_size,
                thread_name_prefix="skill-worker-",
            )
        return self._executor

    def _adjust_pool_size_dynamically(self, pending_count: int) -> None:
        """
        Dynamically adjust thread pool size based on pending parallel skills.

        Scaling policy:
        - If pending > current_workers × 1.5 and workers < max: scale up (+1)
        - If pending < current_workers × 0.3 and workers > min: scale down (-1)
        - Smooth transitions: only adjust once per tick
        """
        if not self.enable_dynamic_scaling or self._executor is None:
            return

        with self._load_monitor_lock:
            current = self._executor._max_workers
            # Scale up
            if pending_count > current * 1.5 and current < self.max_thread_pool_size:
                self._executor._max_workers = min(current + 1, self.max_thread_pool_size)
            # Scale down
            elif pending_count < current * 0.3 and current > self.min_thread_pool_size:
                self._executor._max_workers = max(current - 1, self.min_thread_pool_size)

    def _is_demoted(self, skill_name: str) -> bool:
        """Check if a skill is currently under auto-fallback demotion."""
        if skill_name not in self._demoted_skills:
            return False
        remaining = self._demoted_skills[skill_name]
        if remaining <= 0:
            del self._demoted_skills[skill_name]
            return False
        return True

    def _decrement_demotions(self) -> None:
        """Decrement demotion counters at end of each cycle."""
        expired = []
        for skill_name, remaining in self._demoted_skills.items():
            if remaining <= 1:
                expired.append(skill_name)
            else:
                self._demoted_skills[skill_name] = remaining - 1
        for skill_name in expired:
            del self._demoted_skills[skill_name]

    def _reserve_energy(self, cost: float) -> bool:
        """
        Atomically check if budget can cover cost and reserve it.

        Args:
            cost: Energy cost of the skill.

        Returns:
            True if reserved, False if budget exhausted.
        """
        with self._budget_lock:
            if self._budget_remaining >= cost:
                self._budget_remaining -= cost
                return True
            return False

    def _deduct_energy(self, cost: float) -> None:
        """Add cost to spent total (called after successful execution)."""
        with self._budget_lock:
            self._spent_energy += cost

    def _refund_energy(self, cost: float) -> None:
        """Return reserved energy to budget (on failure/timeout)."""
        with self._budget_lock:
            self._budget_remaining += cost

    # -------------------------------------------------------------------------
    # Skill Enable/Disable
    # -------------------------------------------------------------------------

    def enable(self, skill_name: str) -> bool:
        """启用一个技能。"""
        if skill_name in self._disabled_skills:
            self._disabled_skills.remove(skill_name)
            return True
        return False

    def disable(self, skill_name: str) -> bool:
        """禁用一个技能（悬置期间自动调用）。"""
        if skill_name not in self._disabled_skills:
            self._disabled_skills.add(skill_name)
            return True
        return False

    def is_enabled(self, skill_name: str) -> bool:
        """检查技能是否启用（未手动禁用且 HIC 未悬置）。"""
        return skill_name not in self._disabled_skills

    # -------------------------------------------------------------------------
    # Cycle Execution
    # -------------------------------------------------------------------------

    def tick(self, context: SkillContext) -> list[SkillExecutionRecord]:
        """
        执行一个周期的技能调度（支持并行、优先级、动态伸缩）。

        Returns:
            本周期所有技能执行记录（顺序：同步先 → 共享写 → 线程池并行事按优先级降序 → 异步）
        """
        if context.hic_suspended:
            return []

        # 初始化能量预算
        available_energy = context.energy_available * self.energy_budget_ratio
        with self._budget_lock:
            self._budget_remaining = available_energy
            self._spent_energy = 0.0

        # Sprint 3: decrement demotion counters at START of cycle (before skill selection)
        self._decrement_demotions()

        records: list[SkillExecutionRecord] = []
        candidate_skills = self.registry.list_enabled(context)

        # 分类技能
        sequential_skills = []
        parallel_skills = []
        shared_write_skills = []
        async_skills = []

        for skill in candidate_skills:
            if skill.name in self._disabled_skills:
                continue
            # Sprint 3: 自动降级检查
            if self._is_demoted(skill.name):
                continue
            policy = getattr(skill, "parallelism_policy", ParallelismPolicy.SEQUENTIAL)
            if getattr(skill, "can_execute_async", lambda: False)():
                async_skills.append(skill)
            elif policy == ParallelismPolicy.SEQUENTIAL:
                sequential_skills.append(skill)
            elif policy in (ParallelismPolicy.ISOLATED, ParallelismPolicy.READONLY):
                parallel_skills.append(skill)
            elif policy == ParallelismPolicy.SHARED_WRITE:
                shared_write_skills.append(skill)
            else:
                sequential_skills.append(skill)

        # Sprint 3: 按优先级降序排序（高优先级先执行）
        def get_priority(s: InfantSkill) -> float:
            return getattr(s, "priority", 0.5)

        sequential_skills.sort(key=get_priority, reverse=True)
        shared_write_skills.sort(key=get_priority, reverse=True)
        parallel_skills.sort(key=get_priority, reverse=True)
        async_skills.sort(key=get_priority, reverse=True)

        # Phase 1: SEQUENTIAL skills
        for skill in sequential_skills:
            if len(records) >= self.max_executions:
                break
            try:
                usage = skill.get_resource_usage()
                cost = float(usage.get("energy_cost", 0.0))
            except (TypeError, KeyError, AttributeError):
                cost = 0.0

            if not self._reserve_energy(cost):
                if _METRICS_AVAILABLE:
                    skill_budget_skips_total.labels(skill_name=skill.name).inc()
                continue

            try:
                record = self._execute_skill(skill, context)
                record.execution_mode = "sync"
                records.append(record)
                if record.success:
                    self._deduct_energy(record.energy_cost or cost)
                else:
                    self._refund_energy(cost)
                    # Sprint 3: detect ParallelismUnsafe from sync path
                    if record.error and "data race" in record.error.lower():
                        self._demote_skill(skill.name)
            except Exception as e:
                # Catch ParallelismUnsafe during execution itself
                if getattr(e, "parallelism_unsafe", False):
                    self._demote_skill(skill.name)
                    self._refund_energy(cost)
                else:
                    self._refund_energy(cost)
                    record = SkillExecutionRecord(
                        skill_name=skill.name,
                        params={"_context": context},
                        start_time=time.time(),
                        end_time=time.time(),
                        success=False,
                        error=str(e),
                        energy_cost=0.0,
                        execution_mode="sync",
                    )
                    records.append(record)

        # Phase 2: SHARED_WRITE skills
        for skill in shared_write_skills:
            if len(records) >= self.max_executions:
                break
            try:
                usage = skill.get_resource_usage()
                cost = float(usage.get("energy_cost", 0.0))
            except (TypeError, KeyError, AttributeError):
                cost = 0.0

            if not self._reserve_energy(cost):
                if _METRICS_AVAILABLE:
                    skill_budget_skips_total.labels(skill_name=skill.name).inc()
                continue

            record = self._execute_skill(skill, context)
            record.execution_mode = "sync"
            records.append(record)

            if record.success:
                self._deduct_energy(record.energy_cost or cost)
            else:
                self._refund_energy(cost)

        # Phase 3: ISOLATED + READONLY via thread pool
        if parallel_skills and not context.hic_suspended:
            # Track pending count for dynamic scaling
            with self._load_monitor_lock:
                self._pending_parallel_count = len(parallel_skills)
            parallel_records = self._dispatch_parallel_skills(parallel_skills, context)
            for record in parallel_records:
                records.append(record)
                if record.success:
                    self._deduct_energy(record.energy_cost or 0.0)

        # Phase 4: async skills
        async_records: list[SkillExecutionRecord] = []
        if async_skills and not context.hic_suspended:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            async_results = loop.run_until_complete(
                self._run_async_skills(async_skills, context)
            )
            for skill, result in zip(async_skills, async_results):
                record = self._make_record_from_result(skill, result, context)
                record.execution_mode = "async"
                async_records.append(record)

        records.extend(async_records)
        self.execution_history.extend(records)

        # Post-cycle: adjust pool
        if self.enable_dynamic_scaling:
            self._adjust_pool_size_dynamically(self._pending_parallel_count)
        with self._load_monitor_lock:
            self._pending_parallel_count = 0

        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        return records

    # Sprint 3: Auto-fallback support
    def _demote_skill(self, skill_name: str) -> None:
        """
        Demote a skill to SEQUENTIAL for 100 cycles due to ParallelismUnsafe error.

        Args:
            skill_name: Name of the problematic skill.
        """
        if skill_name not in self._demoted_skills:
            self._demoted_skills[skill_name] = self._demotion_duration
            # Log/metric
            if _METRICS_AVAILABLE:
                skill_auto_fallback_total.labels(skill_name=skill_name).inc()
        else:
            # Reset counter if already demoted
            self._demoted_skills[skill_name] = self._demotion_duration

    def _dispatch_parallel_skills(
        self,
        skills: list[InfantSkill],
        context: SkillContext,
    ) -> list[SkillExecutionRecord]:
        """
        Dispatch skills to thread pool and collect results with timeout.

        Args:
            skills: List of ISOLATED/READONLY skills to run in parallel.
            context: Execution context.

        Returns:
            List of SkillExecutionRecord (order matches skills input).
        """
        if not skills:
            return []

        executor = self._get_executor()
        futures: list[Future] = []

        # Record parallel count metric
        if _METRICS_AVAILABLE:
            skill_parallelism_count.labels(mode="threadpool").set(len(skills))

        # Submit tasks with energy reservation per skill
        for skill in skills:
            try:
                usage = skill.get_resource_usage()
                cost = float(usage.get("energy_cost", 0.0))
            except (TypeError, KeyError, AttributeError):
                cost = 0.0

            if not self._reserve_energy(cost):
                if _METRICS_AVAILABLE:
                    skill_budget_skips_total.labels(skill_name=skill.name).inc()
                continue

            future = executor.submit(self._execute_skill, skill, context)
            futures.append((future, skill, cost))

        # Sprint 3: dynamic scaling decision based on what we just submitted
        self._adjust_pool_size_dynamically(len(futures))

        # Wait for all with timeout
        records: list[SkillExecutionRecord] = []
        for future, skill, cost in futures:
            try:
                start_wait = time.time()
                result = future.result(timeout=THREADPOOL_TIMEOUT)
                wait_time = time.time() - start_wait
                if _METRICS_AVAILABLE and wait_time > 0:
                    resource_lock_wait_seconds.labels(resource_name="threadpool_wait").observe(wait_time)
                record = self._make_parallel_record(skill, result, context, cost)
                record.execution_mode = "threadpool"
                records.append(record)
                self._deduct_energy(cost)
                # Record duration metric
                duration = record.end_time - record.start_time
                if _METRICS_AVAILABLE:
                    skill_execution_duration_seconds.labels(
                        skill_name=skill.name, execution_mode="threadpool"
                    ).observe(duration)
                    # Sprint 4: Enhanced resource metrics
                    skill_execution_count.labels(
                        skill_name=skill.name,
                        execution_mode="threadpool",
                        success=str(record.success).lower(),
                    ).inc()
                    if record.success and record.energy_cost:
                        skill_energy_cost_total.labels(skill_name=skill.name).inc(record.energy_cost)
                        skill_last_success_timestamp.labels(skill_name=skill.name).set(record.end_time)
            except FuturesTimeout:
                future.cancel()
                self._refund_energy(cost)
                record = SkillExecutionRecord(
                    skill_name=skill.name,
                    params={"_context": context},
                    start_time=time.time(),
                    end_time=time.time(),
                    success=False,
                    error=f"Thread pool timeout after {THREADPOOL_TIMEOUT}s",
                    energy_cost=0.0,
                    thread_id=threading.get_ident(),
                    execution_mode="threadpool",
                )
                records.append(record)
                if _METRICS_AVAILABLE:
                    skill_execution_count.labels(
                        skill_name=skill.name,
                        execution_mode="threadpool",
                        success="false",
                    ).inc()
            except Exception as e:
                self._refund_energy(cost)
                record = SkillExecutionRecord(
                    skill_name=skill.name,
                    params={"_context": context},
                    start_time=time.time(),
                    end_time=time.time(),
                    success=False,
                    error=str(e),
                    energy_cost=0.0,
                    thread_id=threading.get_ident(),
                    execution_mode="threadpool",
                )
                records.append(record)
                if _METRICS_AVAILABLE:
                    skill_execution_count.labels(
                        skill_name=skill.name,
                        execution_mode="threadpool",
                        success="false",
                    ).inc()

        return records

    def _make_parallel_record(
        self,
        skill: InfantSkill,
        result: Any,
        context: SkillContext,
        cost: float,
    ) -> SkillExecutionRecord:
        """Build SkillExecutionRecord from a successful parallel execution."""
        # result is actually a SkillExecutionRecord from _execute_skill
        # We preserve its success/error/energy_cost details
        if isinstance(result, SkillExecutionRecord):
            # Clone the inner record but mark execution_mode as threadpool
            record = SkillExecutionRecord(
                skill_name=skill.name,
                params={"_context": context},
                start_time=result.start_time,
                end_time=result.end_time,
                success=result.success,
                error=result.error,
                energy_cost=result.energy_cost if result.energy_cost else cost,
                result=result.result,
                thread_id=result.thread_id or threading.get_ident(),
                execution_mode="threadpool",
            )
        else:
            # Fallback for non-record results
            record = SkillExecutionRecord(
                skill_name=skill.name,
                params={"_context": context},
                start_time=time.time(),
                end_time=time.time(),
                success=True,
                result=result,
                energy_cost=cost,
                thread_id=threading.get_ident(),
                execution_mode="threadpool",
            )
        return record

    # -------------------------------------------------------------------------
    # Existing sync/async execution (unchanged logic, added energy reservation)
    # -------------------------------------------------------------------------

    def _execute_skill(self, skill: InfantSkill, context: SkillContext) -> SkillExecutionRecord:
        """执行单个技能并记录（同步路径）。"""
        start = time.time()
        record = SkillExecutionRecord(
            skill_name=skill.name,
            params={"context": context},
            start_time=start,
        )

        try:
            result = skill.execute({"_context": context})
            record.success = True
            record.result = result
            try:
                usage = skill.get_resource_usage()
                record.energy_cost = usage.get("energy_cost", 0.0)
            except (TypeError, KeyError, AttributeError):
                record.energy_cost = 0.0
        except Exception as e:
            record.success = False
            record.error = str(e)
            record.energy_cost = 0.0
            # Sprint 3: auto-fallback on ParallelismUnsafe
            if getattr(e, "parallelism_unsafe", False):
                self._demote_skill(skill.name)

        record.end_time = time.time()
        # Record duration metric
        duration = record.end_time - record.start_time
        if _METRICS_AVAILABLE:
            skill_execution_duration_seconds.labels(
                skill_name=skill.name, execution_mode="sync"
            ).observe(duration)
            # Sprint 4: Enhanced resource metrics
            skill_execution_count.labels(
                skill_name=skill.name,
                execution_mode="sync",
                success=str(record.success).lower(),
            ).inc()
            if record.success and record.energy_cost:
                skill_energy_cost_total.labels(skill_name=skill.name).inc(record.energy_cost)
                skill_last_success_timestamp.labels(skill_name=skill.name).set(record.end_time)
        return record

    # -------------------------------------------------------------------------
    # Async Execution (Sprint 1, enhanced with energy reservation)
    # -------------------------------------------------------------------------

    def can_execute_async(self) -> bool:
        """KnowledgeTransfer performs network RPC — benefits from async."""
        return True  # Sprint 1: enable parallel I/O

    async def _run_async_skills(
        self,
        skills: list[InfantSkill],
        context: SkillContext,
    ) -> list[Any]:
        """
        Execute async skills concurrently using asyncio.gather.

        Returns list of results (or exceptions if return_exceptions=True).
        """
        # Reserve energy for all async skills before awaiting
        costs = []
        for skill in skills:
            try:
                usage = skill.get_resource_usage()
                cost = float(usage.get("energy_cost", 0.0))
            except (TypeError, KeyError, AttributeError):
                cost = 0.0
            if not self._reserve_energy(cost):
                costs.append(None)
            else:
                costs.append(cost)

        if _METRICS_AVAILABLE:
            skill_parallelism_count.labels(mode="async").set(len([c for c in costs if c is not None]))

        tasks = []
        for skill, cost in zip(skills, costs):
            if cost is None:
                # Budget skip — track metric
                if _METRICS_AVAILABLE:
                    skill_budget_skips_total.labels(skill_name=skill.name).inc()
                async def skip_result():
                    return {"_skipped": True, "_cost": 0.0, "_error": "budget_exhausted"}
                tasks.append(asyncio.create_task(skip_result()))
            else:
                async def run_with_accounting(s=skill, c=cost):
                    start = time.time()
                    try:
                        result = await s.execute_async({"_context": context})
                        self._deduct_energy(c)
                        duration = time.time() - start
                        if _METRICS_AVAILABLE:
                            skill_execution_duration_seconds.labels(
                                skill_name=s.name, execution_mode="async"
                            ).observe(duration)
                            skill_execution_count.labels(
                                skill_name=s.name,
                                execution_mode="async",
                                success="true",
                            ).inc()
                            skill_energy_cost_total.labels(skill_name=s.name).inc(c)
                            skill_last_success_timestamp.labels(skill_name=s.name).set(time.time())
                        return result
                    except Exception as e:
                        self._refund_energy(c)
                        duration = time.time() - start
                        if _METRICS_AVAILABLE:
                            skill_execution_duration_seconds.labels(
                                skill_name=s.name, execution_mode="async"
                            ).observe(duration)
                            skill_execution_count.labels(
                                skill_name=s.name,
                                execution_mode="async",
                                success="false",
                            ).inc()
                        if getattr(e, "parallelism_unsafe", False):
                            self._demote_skill(s.name)
                        return e
                tasks.append(asyncio.create_task(run_with_accounting()))

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=ASYNCIO_TIMEOUT,
            )
            return list(results)
        except asyncio.TimeoutError:
            # Cancel all pending tasks, refund their costs
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Refund costs for all async skills (timeout means none completed)
            for cost in costs:
                if cost is not None:
                    self._refund_energy(cost)
            return [asyncio.TimeoutError(f"Async skills timed out after {ASYNCIO_TIMEOUT}s")] * len(skills)

    def _make_record_from_result(
        self,
        skill: InfantSkill,
        result: Any,
        context: SkillContext,
    ) -> SkillExecutionRecord:
        """将异步执行结果转换为 SkillExecutionRecord。"""
        record = SkillExecutionRecord(
            skill_name=skill.name,
            params={"_context": context},
            start_time=time.time(),
            end_time=time.time(),
            execution_mode="async",
        )
        if isinstance(result, Exception):
            record.success = False
            record.error = str(result)
        else:
            # Check for special skip marker
            if isinstance(result, dict) and result.get("_skipped"):
                record.success = False
                record.error = result.get("_error", "skipped")
                record.energy_cost = 0.0
            else:
                record.success = True
                record.result = result
                try:
                    usage = skill.get_resource_usage()
                    record.energy_cost = usage.get("energy_cost", 0.0)
                except (TypeError, KeyError, AttributeError):
                    record.energy_cost = 0.0
        return record

    # -------------------------------------------------------------------------
    # HIC Suspend Handling
    # -------------------------------------------------------------------------

    def on_hic_suspend(self) -> None:
        """
        HIC 元认知悬置回调（IMP-04）。

        策略：
        - 所有技能标记为禁用（下一周期跳过）
        - 但核心生存技能（如 "energy_monitor"）保持启用
        """
        CORE_SURVIVAL_SKILLS = {"energy_monitor", "physical_anchor"}

        for skill in self.registry.list_all():
            if skill.name not in CORE_SURVIVAL_SKILLS:
                self.disable(skill.name)

    def on_hic_resume(self) -> None:
        """HIC 悬置结束回调，恢复技能调度。"""
        self._disabled_skills.clear()

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取生命周期管理器统计信息。"""
        recent = [r for r in self.execution_history[-100:] if r.success]
        error_rate = 0.0
        avg_latency = 0.0
        if recent:
            error_rate = 1.0 - (len(recent) / 100.0)
            avg_latency = sum(r.end_time - r.start_time for r in recent) / len(recent)

        return {
            "total_executions": len(self.execution_history),
            "disabled_skills": list(self._disabled_skills),
            "error_rate_last_100": error_rate,
            "avg_latency_s": avg_latency,
            "enabled_skills_count": len([
                s for s in self.registry.list_all() if s.name not in self._disabled_skills
            ]),
            "thread_pool_size": self.thread_pool_size,
            "budget_remaining": self._budget_remaining,
            "spent_energy": self._spent_energy,
        }

    def shutdown(self) -> None:
        """Cleanup: shutdown thread pool if running."""
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None
