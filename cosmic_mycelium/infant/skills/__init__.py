"""
Skills Package — 技能插件系统

核心组件：
- base: InfantSkill 协议定义
- registry: SkillRegistry 单例
- loader: SkillLoader 发现与加载
- lifecycle: SkillLifecycleManager 调度器
"""

from __future__ import annotations

# 导出公共接口
from cosmic_mycelium.infant.skills.base import (
    InfantSkill,
    SkillContext,
    SkillExecutionError,
    SkillInitializationError,
)
from cosmic_mycelium.infant.skills.registry import SkillRegistry
from cosmic_mycelium.infant.skills.loader import SkillLoader
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager, SkillExecutionRecord

__all__ = [
    "InfantSkill",
    "SkillContext",
    "SkillExecutionError",
    "SkillInitializationError",
    "SkillRegistry",
    "SkillLoader",
    "SkillLifecycleManager",
    "SkillExecutionRecord",
]
