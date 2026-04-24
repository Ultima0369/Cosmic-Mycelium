"""
Skill Loader — 技能发现与加载器

支持两种发现机制：
1. Entry Points（setuptools）— 第三方插件通过 pip install 自动注册
2. 目录扫描 — 内置技能从 infant/skills/ 自动加载
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any

from cosmic_mycelium.infant.skills.base import InfantSkill
from cosmic_mycelium.infant.skills.registry import SkillRegistry


class SkillLoader:
    """
    技能加载器 — 负责发现、验证、加载技能模块。

    使用方式：
    >>> loader = SkillLoader()
    >>> loader.discover_entry_points()     # 第三方插件
    >>> loader.discover_builtin()          # 内置技能
    >>> loader.load_all()
    """

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or SkillRegistry()
        self._loaded_modules: set[str] = set()

    # -------------------------------------------------------------------------
    # Entry Points Discovery (第三方插件)
    # -------------------------------------------------------------------------

    def discover_entry_points(self, group: str = "cosmic_mycelium.skills") -> None:
        """
        扫描 setuptools entry points 并注册。

        Args:
            group: entry point 组名（默认: cosmic_mycelium.skills）

        第三方插件示例（setup.py）：
        ```python
        setup(
            name="infant-skill-math",
            entry_points={
                "cosmic_mycelium.skills": [
                    "math = infant_skill_math.math_skill:MathSkill",
                ]
            },
        )
        ```
        """
        try:
            import importlib.metadata as importlib_metadata
        except ImportError:
            import importlib_metadata  # type: ignore

        try:
            eps = importlib_metadata.entry_points()
            # Python 3.10+ 返回字典，旧版本返回 EntryPoints 对象
            if hasattr(eps, "select"):
                group_eps = eps.select(group=group)
            else:
                group_eps = eps.get(group, [])
        except Exception as e:
            # Entry points 不可用（如离线环境），静默跳过
            return

        for ep in group_eps:
            try:
                module_path, class_name = ep.value.split(":")
                module = importlib.import_module(module_path)
                skill_cls = getattr(module, class_name)
                # 检查是否实现了 InfantSkill 协议（运行时检查）
                if not self._is_valid_skill(skill_cls):
                    continue
                # 实例化并注册
                skill_instance = skill_cls()
                self.registry.register(skill_instance)
            except Exception as e:
                # 单个插件加载失败不应影响整体
                continue

    # -------------------------------------------------------------------------
    # Built-in Discovery (内置技能)
    # -------------------------------------------------------------------------

    def discover_builtin(self, package: str = "cosmic_mycelium.infant.skills") -> None:
        """
        扫描内置技能包目录，自动注册所有实现了 InfantSkill 的类。

        Args:
            package: 技能包 Python 路径（默认: cosmic_mycelium.infant.skills）
        """
        try:
            pkg = importlib.import_module(package)
        except ImportError:
            return

        pkg_path = Path(getattr(pkg, "__path__", [""])[0])
        if not pkg_path.exists():
            return

        for finder, name, is_pkg in pkgutil.iter_modules([str(pkg_path)]):
            if name == "__pycache__":
                continue
            module_name = f"{package}.{name}"
            try:
                module = importlib.import_module(module_name)
                self._register_from_module(module)
            except Exception:
                continue

        # 递归扫描子包
        if pkg_path.is_dir():
            for sub_dir in pkg_path.iterdir():
                if sub_dir.is_dir() and (sub_dir / "__init__.py").exists():
                    self.discover_builtin(f"{package}.{sub_dir.name}")

    def _register_from_module(self, module: Any) -> None:
        """
        从模块中查找并注册所有 InfantSkill 子类。

        扫描逻辑：
        1. 查找 module 中所有类定义
        2. 过滤出 InfantSkill 子类（排除协议本身）
        3. 实例化并注册（排除已注册的）
        """
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue  # 跳过导入的类
            if not self._is_valid_skill(obj):
                continue
            try:
                instance = obj()
                # 避免重复注册
                if self.registry.get(instance.name) is None:
                    self.registry.register(instance)
            except Exception:
                continue

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_valid_skill(cls: type) -> bool:
        """
        检查一个类是否为有效的 InfantSkill 实现。

        条件：
        1. 不是 InfantSkill 协议本身
        2. 是类（不是函数）
        3. 实现了必需的属性和方法（通过 duck typing 检查）
        """
        from cosmic_mycelium.infant.skills.base import InfantSkill

        if not inspect.isclass(cls):
            return False
        # 跳过协议本身
        if cls.__name__ == "InfantSkill":
            return False
        # 检查必需属性
        required_attrs = {
            "name", "version", "description", "dependencies",
            "initialize", "can_activate", "execute",
            "get_resource_usage", "shutdown", "get_status",
        }
        return all(hasattr(cls, attr) for attr in required_attrs)

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def load_all(self) -> None:
        """一次性发现并加载所有内置和第三方技能。"""
        self.discover_builtin()
        self.discover_entry_points()

    def unload_all(self) -> None:
        """卸载所有技能。"""
        self.registry.shutdown_all()
