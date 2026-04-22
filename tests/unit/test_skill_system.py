"""
Unit Tests: Skill Plugin System

测试 InfantSkill 协议、SkillRegistry、SkillLoader、SkillLifecycleManager。
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.infant.skills.base import (
    InfantSkill,
    SkillContext,
    SkillExecutionError,
)
from cosmic_mycelium.infant.skills.registry import SkillRegistry
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager, SkillExecutionRecord
from cosmic_mycelium.infant.skills.loader import SkillLoader


# ---------------------------------------------------------------------------
# Fixtures: 每个测试使用独立 Registry
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_registry():
    """重置 SkillRegistry 单例，确保测试隔离。"""
    old = SkillRegistry._instance
    SkillRegistry._instance = None
    reg = SkillRegistry()
    yield reg
    SkillRegistry._instance = old


# ---------------------------------------------------------------------------
# Test Helper: make_mock_skill
# ---------------------------------------------------------------------------

def make_mock_skill(
    name: str = "mock_skill",
    can_activate_return: bool = True,
    execute_return: Any = None,
    dependencies: list[str] | None = None,
) -> InfantSkill:
    """工厂函数：创建一个符合 InfantSkill 协议的模拟技能。"""
    skill = MagicMock(spec=InfantSkill)
    skill.name = name
    skill.version = "1.0.0"
    skill.description = f"Mock skill {name}"
    skill.dependencies = dependencies or []
    # 方法
    skill.initialize = MagicMock()
    skill.can_activate = MagicMock(return_value=can_activate_return)
    execute_val = execute_return or {"result": "ok"}
    skill.execute = MagicMock(return_value=execute_val)
    skill.get_resource_usage = MagicMock(return_value={"energy_cost": 1.0, "duration_s": 0.01, "memory_mb": 1.0})
    skill.shutdown = MagicMock()
    skill.get_status = MagicMock(return_value={"name": name, "active": True})
    return skill


# ---------------------------------------------------------------------------
# Test: SkillRegistry
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    """测试 SkillRegistry 单例和基本功能。"""

    def test_singleton_returns_same_instance(self, fresh_registry):
        reg1 = fresh_registry
        reg2 = SkillRegistry()
        assert reg1 is reg2

    def test_register_adds_skill(self, fresh_registry):
        skill = make_mock_skill()
        fresh_registry.register(skill)
        assert fresh_registry.get("mock_skill") is skill

    def test_register_duplicate_raises(self, fresh_registry):
        fresh_registry.register(make_mock_skill())
        with pytest.raises(Exception):
            fresh_registry.register(make_mock_skill())

    def test_unregister_removes_skill(self, fresh_registry):
        skill = make_mock_skill()
        fresh_registry.register(skill)
        fresh_registry.unregister("mock_skill")
        assert fresh_registry.get("mock_skill") is None

    def test_list_all_returns_all_registered(self, fresh_registry):
        fresh_registry.register(make_mock_skill(name="skill_a"))
        fresh_registry.register(make_mock_skill(name="skill_b"))
        skills = fresh_registry.list_all()
        assert len(skills) == 2

    def test_list_enabled_filters_by_can_activate(self, fresh_registry):
        fresh_registry.register(make_mock_skill(can_activate_return=True))
        fresh_registry.register(make_mock_skill(can_activate_return=False, name="disabled"))
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        enabled = fresh_registry.list_enabled(ctx)
        assert len(enabled) == 1
        assert enabled[0].name == "mock_skill"

    def test_topological_sort_simple(self, fresh_registry):
        class BaseSkill:
            name = "base"
            version = "1.0.0"
            description = "Base test skill"
            dependencies = []
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        class DependentSkill:
            name = "dependent"
            version = "1.0.0"
            description = "Dependent test skill"
            dependencies = ["base"]
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(BaseSkill())
        fresh_registry.register(DependentSkill())
        order = fresh_registry.topological_sort()
        assert order == ["base", "dependent"]

    def test_topological_sort_detects_cycle(self, fresh_registry):
        class SkillA:
            name = "a"
            version = "1.0.0"
            description = "Skill A"
            dependencies = ["b"]
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        class SkillB:
            name = "b"
            version = "1.0.0"
            description = "Skill B"
            dependencies = ["a"]
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(SkillA())
        fresh_registry.register(SkillB())
        with pytest.raises(ValueError, match="Cyclic"):
            fresh_registry.topological_sort()

    def test_validate_dependencies_all_met(self, fresh_registry):
        class DepSkill:
            name = "dep"
            version = "1.0.0"
            description = "Dependency skill"
            dependencies = []
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        class MainSkill:
            name = "main"
            version = "1.0.0"
            description = "Main skill with dependency"
            dependencies = ["dep"]
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(DepSkill())
        fresh_registry.register(MainSkill())
        fresh_registry.validate_dependencies()

    def test_validate_dependencies_missing_raises(self, fresh_registry):
        class MissingDepSkill:
            name = "main"
            version = "1.0.0"
            description = "Skill with missing dependency"
            dependencies = ["missing"]
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(MissingDepSkill())
        with pytest.raises(Exception, match="depends on"):
            fresh_registry.validate_dependencies()

    def test_initialize_all_calls_each_skill(self, fresh_registry):
        s1 = make_mock_skill(name="s1")
        s2 = make_mock_skill(name="s2")
        fresh_registry.register(s1)
        fresh_registry.register(s2)
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        fresh_registry.initialize_all(ctx)
        s1.initialize.assert_called_once_with(ctx)
        s2.initialize.assert_called_once_with(ctx)

    def test_shutdown_all_calls_reverse_order(self, fresh_registry):
        s1 = make_mock_skill(name="s1")
        s2 = make_mock_skill(name="s2")
        fresh_registry.register(s1)
        fresh_registry.register(s2)
        fresh_registry.initialize_all(SkillContext(infant_id="t", cycle_count=0, energy_available=100))
        fresh_registry.shutdown_all()
        s1.shutdown.assert_called_once()
        s2.shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# Test: SkillLifecycleManager
# ---------------------------------------------------------------------------

class TestSkillLifecycleManager:
    """测试技能生命周期管理。"""

    def test_tick_executes_enabled_skills(self, fresh_registry):
        skill = make_mock_skill(can_activate_return=True)
        fresh_registry.register(skill)
        mgr = SkillLifecycleManager(fresh_registry)
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        records = mgr.tick(ctx)
        assert len(records) == 1
        assert records[0].success

    def test_tick_respects_energy_budget(self, fresh_registry):
        class ExpensiveSkill:
            name = "expensive"
            version = "1.0.0"
            description = "Expensive test skill"
            dependencies = []
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 60.0, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(ExpensiveSkill())
        mgr = SkillLifecycleManager(fresh_registry, energy_budget_ratio=0.5)  # 预算 50
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        records = mgr.tick(ctx)
        assert len(records) == 0  # 消耗 60 > 50，不执行

    def test_disable_prevents_execution(self, fresh_registry):
        skill = make_mock_skill()
        fresh_registry.register(skill)
        mgr = SkillLifecycleManager(fresh_registry)
        mgr.disable("mock_skill")
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        records = mgr.tick(ctx)
        assert len(records) == 0

    def test_on_hic_suspend_disables_non_core(self, fresh_registry):
        class CoreSkill:
            name = "energy_monitor"
            version = "1.0.0"
            description = "Core survival skill"
            dependencies = []
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        class NormalSkill:
            name = "research"
            version = "1.0.0"
            description = "Normal non-core skill"
            dependencies = []
            def initialize(self, ctx): pass
            def can_activate(self, ctx): return True
            def execute(self, p): return {}
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.01, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {"name": self.name}
        fresh_registry.register(CoreSkill())
        fresh_registry.register(NormalSkill())
        mgr = SkillLifecycleManager(fresh_registry)
        mgr.on_hic_suspend()
        assert mgr.is_enabled("energy_monitor")
        assert not mgr.is_enabled("research")

    def test_on_hic_resume_clears_disabled_set(self, fresh_registry):
        skill = make_mock_skill()
        fresh_registry.register(skill)
        mgr = SkillLifecycleManager(fresh_registry)
        mgr.disable("mock_skill")
        mgr.on_hic_resume()
        assert mgr.is_enabled("mock_skill")

    def test_get_stats_returns_reasonable_values(self, fresh_registry):
        skill = make_mock_skill()
        fresh_registry.register(skill)
        mgr = SkillLifecycleManager(fresh_registry)
        ctx = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        mgr.tick(ctx)
        stats = mgr.get_stats()
        assert "total_executions" in stats
        assert "disabled_skills" in stats
        assert "enabled_skills_count" in stats


# ---------------------------------------------------------------------------
# Test: SkillLoader
# ---------------------------------------------------------------------------

class TestSkillLoader:
    """测试技能加载器发现机制。"""

    def test_loader_creates_registry_if_none(self):
        loader = SkillLoader()
        assert loader.registry is not None

    def test_loader_uses_provided_registry(self):
        reg = SkillRegistry()
        loader = SkillLoader(reg)
        assert loader.registry is reg

    def test_is_valid_skill_recognizes_implementation(self):
        loader = SkillLoader()
        # Valid skill class with all required attributes
        class ValidSkill:
            name = "valid"
            version = "1.0.0"
            description = "A valid skill"
            dependencies = []
            def initialize(self, ctx): pass
            def execute(self, p): return {}
            def can_activate(self, ctx): return True
            def get_resource_usage(self): return {"energy_cost": 1, "duration_s": 0.1, "memory_mb": 1}
            def shutdown(self): pass
            def get_status(self): return {}
        assert loader._is_valid_skill(ValidSkill)
        class NotASkill: pass
        assert not loader._is_valid_skill(NotASkill)
        class Incomplete:
            name = "incomplete"
        assert not loader._is_valid_skill(Incomplete)
