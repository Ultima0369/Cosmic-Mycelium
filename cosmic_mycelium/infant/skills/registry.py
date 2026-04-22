"""
Skill Registry — 全局技能注册中心

单例模式，管理所有已加载技能的注册、查询和生命周期。
"""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

from .base import InfantSkill, SkillContext, SkillInitializationError


class SkillRegistry:
    """
    全局技能注册表（Singleton）。

    职责：
    - 技能注册/注销
    - 技能实例查询
    - 依赖关系管理
    - 生命周期事件广播
    """

    _instance: SkillRegistry | None = None
    _lock = threading.RLock()

    def __new__(cls) -> SkillRegistry:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._skills: dict[str, InfantSkill] = {}
        self._load_order: list[str] = []  # 依赖排序后的加载顺序
        self._initialized = True
        self._event_listeners: dict[str, list[callable]] = {
            "skill_loaded": [],
            "skill_unloaded": [],
            "skill_executed": [],
        }

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register(self, skill: InfantSkill) -> None:
        """
        注册一个新技能。

        Args:
            skill: 实现 InfantSkill 协议的实例

        Raises:
            SkillInitializationError: 如果技能名已存在或依赖缺失
        """
        with self._lock:
            if skill.name in self._skills:
                raise SkillInitializationError(f"Skill '{skill.name}' already registered")

            self._skills[skill.name] = skill
            self._emit("skill_loaded", {"skill_name": skill.name, "version": skill.version})

    def unregister(self, skill_name: str) -> None:
        """从注册表移除技能（shutdown 后调用）。"""
        with self._lock:
            if skill_name in self._skills:
                del self._skills[skill_name]
                self._load_order = [s for s in self._load_order if s != skill_name]
                self._emit("skill_unloaded", {"skill_name": skill_name})

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    def get(self, skill_name: str) -> InfantSkill | None:
        """按名称获取技能实例。"""
        return self._skills.get(skill_name)

    def list_all(self) -> list[InfantSkill]:
        """列出所有已注册技能。"""
        return list(self._skills.values())

    def list_enabled(self, context: SkillContext) -> list[InfantSkill]:
        """
        列出当前周期可激活的技能（can_activate(context) == True）。

        Args:
            context: 当前周期上下文

        Returns:
            可激活技能列表（按依赖拓扑排序）
        """
        return [
            skill for skill in self._skills.values()
            if skill.can_activate(context)
        ]

    # -------------------------------------------------------------------------
    # Dependency Resolution
    # -------------------------------------------------------------------------

    def topological_sort(self) -> list[str]:
        """
        对技能加载顺序进行拓扑排序（依赖先行）。

        Returns:
            技能名称列表，依赖靠前

        Raises:
            ValueError: 如果存在循环依赖
        """
        # 构建依赖图：dep -> [skills that depend on it]
        dependents: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        # 初始化所有节点
        for skill in self._skills.values():
            in_degree[skill.name] = 0
            dependents[skill.name] = []

        # 填充依赖关系：skill 依赖于 dep，因此 dep -> skill 边
        for skill in self._skills.values():
            for dep in skill.dependencies:
                if dep in in_degree:
                    dependents[dep].append(skill.name)
                    in_degree[skill.name] += 1
                # 否则由 validate_dependencies 捕获缺失依赖

        # Kahn 算法：从入度为 0 的节点开始
        queue = [node for node, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for dependent in dependents.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(in_degree):
            raise ValueError("Cyclic skill dependency detected")

        self._load_order = order
        return order

    def validate_dependencies(self) -> None:
        """
        检查所有依赖是否已注册。

        Raises:
            SkillInitializationError: 如果某个技能的依赖缺失
        """
        for skill in self._skills.values():
            for dep in skill.dependencies:
                if dep not in self._skills:
                    raise SkillInitializationError(
                        f"Skill '{skill.name}' depends on '{dep}' which is not registered"
                    )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize_all(self, context: SkillContext) -> None:
        """
        按拓扑排序依次初始化所有技能。

        Args:
            context: 初始化上下文

        Raises:
            SkillInitializationError: 任一个技能初始化失败时回滚
        """
        order = self.topological_sort()
        try:
            for skill_name in order:
                skill = self._skills[skill_name]
                skill.initialize(context)
        except Exception as e:
            # 初始化失败，已初始化的技能需要 shutdown
            for initialized_name in order[: order.index(skill_name)]:
                self._skills[initialized_name].shutdown()
            raise SkillInitializationError(f"Failed to initialize skill '{skill_name}': {e}") from e

    def shutdown_all(self) -> None:
        """按逆序关闭所有技能。"""
        for skill_name in reversed(self._load_order):
            skill = self._skills.get(skill_name)
            if skill:
                skill.shutdown()

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def on(self, event: str, callback: callable) -> str:
        """
        订阅技能事件。

        Args:
            event: 事件名 ("skill_loaded", "skill_unloaded", "skill_executed")
            callback: 回调函数(event_data: dict) -> None

        Returns:
            订阅 ID（用于取消订阅）
        """
        sub_id = str(uuid4())
        self._event_listeners[event].append((sub_id, callback))
        return sub_id

    def off(self, event: str, sub_id: str) -> None:
        """取消订阅。"""
        for callback_list in self._event_listeners.values():
            callback_list[:] = [(hid, cb) for hid, cb in callback_list if hid != sub_id]

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        """触发事件（内部使用）。"""
        for _, callback in self._event_listeners.get(event, []):
            try:
                callback(data)
            except Exception:
                pass  # 事件回调异常不应影响主流程
