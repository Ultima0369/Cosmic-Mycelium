"""
Skills Base — 技能插件系统核心协议

定义所有技能必须遵守的接口规范。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
import time


@dataclass
class SkillContext:
    """技能执行的运行时上下文。"""
    infant_id: str
    cycle_count: int
    energy_available: float
    hic_suspended: bool = False
    timestamp: float = field(default_factory=time.time)


class InfantSkill(Protocol):
    """
    所有技能的协议（接口规范）。

    技能是婴儿能力的可插拔扩展模块，必须：
    1. 明确声明依赖关系
    2. 遵守 HIC 元认知悬置约束
    3. 资源使用透明化
    4. 安全边界校验（SEC-009/010）
    """

    name: str                      # 技能唯一标识 (e.g. "research", "math_calculator")
    version: str                   # 语义化版本 (e.g. "1.0.0")
    description: str               # 人类可读描述
    dependencies: list[str]        # 依赖的其他技能名称列表（可为空）

    def initialize(self, context: SkillContext) -> None:
        """
        技能初始化（单例模式，启动时调用一次）。

        Args:
            context: 运行时上下文（含 infant_id, 初始能量等）

        Raises:
            SkillInitializationError: 初始化失败（如依赖缺失）
        """
        ...

    def can_activate(self, context: SkillContext) -> bool:
        """
        判断当前周期是否应该激活此技能。

        考虑因素：
        - 能量是否充足（context.energy_available）
        - HIC 是否悬置（context.hic_suspended）
        - 前置依赖是否就绪
        - 冷却时间是否满足

        Returns:
            True 表示可以执行，False 表示跳过此周期
        """
        ...

    def execute(self, params: dict[str, Any]) -> Any:
        """
        执行技能核心逻辑。

        Args:
            params: 技能特定参数（由调用方传入）

        Returns:
            执行结果（技能特定格式）

        Raises:
            SkillExecutionError: 执行失败（异常应被捕获并记录）
        """
        ...

    def get_resource_usage(self) -> dict[str, float]:
        """
        返回本轮执行的资源消耗报告。

        用于 HIC 能量核算和速率限制。

        Returns:
            {"energy_cost": float, "memory_mb": float, "duration_s": float}
        """
        ...

    def shutdown(self) -> None:
        """清理资源（单例关闭时调用）。"""
        ...

    def get_status(self) -> dict[str, Any]:
        """
        获取技能健康状态。

        Returns:
            {"name": str, "active": bool, "last_execution": float, ...}
        """
        ...


class SkillExecutionError(Exception):
    """技能执行失败异常。"""
    pass


class SkillInitializationError(Exception):
    """技能初始化失败异常。"""
    pass
