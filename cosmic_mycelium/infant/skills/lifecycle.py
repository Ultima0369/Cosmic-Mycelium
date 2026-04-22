"""
Skill Lifecycle Manager — 技能生命周期管理器

负责技能的启用/禁用、周期调度、资源核算和 HIC 悬置响应。
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from cosmic_mycelium.infant.skills.base import InfantSkill, SkillContext, SkillExecutionError
from cosmic_mycelium.infant.skills.registry import SkillRegistry


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


class SkillLifecycleManager:
    """
    管理技能的全生命周期。

    职责：
    - 周期调度：每个周期判断哪些技能可以激活
    - 资源核算：累计技能消耗，防止 HIC 能量耗尽
    - HIC 悬置响应：悬置期间暂停非关键技能
    - 执行审计：记录每次执行，供调试和监控
    """

    def __init__(
        self,
        registry: SkillRegistry,
        max_executions_per_cycle: int = 5,
        energy_budget_ratio: float = 0.1,  # 每个周期最多消耗 10% 能量
    ):
        """
        Args:
            registry: 全局技能注册表
            max_executions_per_cycle: 单周期最多执行技能次数（防止无限循环）
            energy_budget_ratio: 技能消耗占当前能量的最大比例
        """
        self.registry = registry
        self.max_executions = max_executions_per_cycle
        self.energy_budget_ratio = energy_budget_ratio
        self.execution_history: list[SkillExecutionRecord] = []
        self._disabled_skills: set[str] = set()  # 手动禁用的技能

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
        执行一个周期的技能调度。

        Args:
            context: 当前周期上下文（能量、周期数等）

        Returns:
            本周期所有技能执行记录
        """
        # HIC 悬置期间跳过所有非关键技能
        if context.hic_suspended:
            return []

        # 计算能量预算
        available_energy = context.energy_available * self.energy_budget_ratio
        spent_energy = 0.0

        records: list[SkillExecutionRecord] = []
        candidate_skills = self.registry.list_enabled(context)

        # 按注册顺序（拓扑排序）执行，确保依赖顺序
        for skill in candidate_skills:
            if len(records) >= self.max_executions:
                break

            # 检查手动禁用
            if skill.name in self._disabled_skills:
                continue

            # 检查能量预算（预估消耗）
            try:
                usage = skill.get_resource_usage()
                cost = usage.get("energy_cost", 0.0)
            except Exception:
                cost = 0.0
            if spent_energy + cost > available_energy:
                continue  # 跳过此技能，继续尝试其他

            # 执行技能
            record = self._execute_skill(skill, context)
            records.append(record)

            if record.success:
                spent_energy += record.energy_cost

        self.execution_history.extend(records)
        # 保持历史长度上限（最近 1000 条）
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        return records

    def _execute_skill(self, skill: InfantSkill, context: SkillContext) -> SkillExecutionRecord:
        """执行单个技能并记录。"""
        start = time.time()
        record = SkillExecutionRecord(
            skill_name=skill.name,
            params={"context": context},  # 保留上下文用于审计
            start_time=start,
        )

        try:
            # 传入 _context 供技能内部使用（如 ResearchSkill 记录 last_execution）
            result = skill.execute({"_context": context})
            record.success = True
            record.result = result

            # 资源核算
            usage = skill.get_resource_usage()
            record.energy_cost = usage.get("energy_cost", 0.0)
        except Exception as e:
            record.success = False
            record.error = str(e)

        record.end_time = time.time()
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
        # 清空禁用列表（全部恢复）
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
        }
