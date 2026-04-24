"""
Experiment Designer — 宝宝的"实验设计"模块

将 GeneratedQuestion 转化为可执行的动作序列（工具调用链）。
对应 PHASE4_PROPOSAL 二.1: Experiment Designer

工具来源: inspirations/autoresearch/tool_interface_example.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from cosmic_mycelium.infant.knowledge_store import KnowledgeEntry, KnowledgeStore


@dataclass
class ExperimentPlan:
    """一个可执行的实验计划。"""
    plan_id: str
    question: str
    hypothesis: str
    steps: list[ExperimentStep] = field(default_factory=list)
    expected_duration: float = 10.0  # 秒
    created_at: float = field(default_factory=time.time)


@dataclass
class ExperimentStep:
    """实验的单个步骤（工具调用）。"""
    tool_name: str
    parameters: dict[str, Any]
    rationale: str = ""


class ExperimentDesigner:
    """
    将问题转化为可执行实验。

    工作原理：
    1. 解析 question text，识别关键词（如"呼吸节律"、"resonate"等）
    2. 映射到可用工具（adjust_breath_cycle, resonate_with_node 等）
    3. 构建线性步骤序列（目前只支持单步实验；未来可多步链）
    4. 附加验证方法（结果收集说明）
    """

    # 关键词 → 工具映射（启发式）
    KEYWORD_TOOL_MAP = {
        "呼吸": "adjust_breath_cycle",
        "breath": "adjust_breath_cycle",
        "节律": "adjust_breath_cycle",
        "resonate": "resonate_with_node",
        "共振": "resonate_with_node",
        "节点": "resonate_with_node",
        "node": "resonate_with_node",
        "物理锚": "check_physics_anchor",
        "anchor": "check_physics_anchor",
        "energy": "check_physics_anchor",
        "特征": "extract_feature",
        "feature": "extract_feature",
    }

    def __init__(self, tool_registry: dict[str, Any] | None = None):
        """
        Args:
            tool_registry: dict[tool_name -> tool_instance]。
                           若 None，使用默认工具集（见 tool_interface_example.ALL_TOOLS）
        """
        if tool_registry is None:
            # 延迟导入以避免循环
            from cosmic_mycelium.infant.skills.research.tool_interface_example import (
                ALL_TOOLS,
            )

            self.tools = {name: tool for name, tool in ALL_TOOLS.items()}
        else:
            self.tools = tool_registry

    def design(self, question: str, hypothesis: str) -> ExperimentPlan:
        """
        设计一个单步实验计划。

        目前仅支持：一个 question → 一个工具调用。
        未来可扩展为多步骤链（例如: 调整呼吸 → 观察能量 → 再次调整）。
        """
        plan_id = f"plan_{int(time.time()*1000) % 100000:06d}"

        # 关键词匹配选择工具
        tool_name = self._select_tool(question)
        if tool_name is None:
            # 默认：尝试物理锚检查（通用诊断）
            tool_name = "check_physics_anchor"

        tool = self.tools.get(tool_name)
        if tool is None:
            raise ValueError(f"工具不可用: {tool_name}")

        # 构建参数（目前使用默认值或简单启发式）
        params = self._build_parameters(tool_name, question, hypothesis)

        step = ExperimentStep(
            tool_name=tool_name,
            parameters=params,
            rationale=f"验证: {hypothesis}",
        )

        plan = ExperimentPlan(
            plan_id=plan_id,
            question=question,
            hypothesis=hypothesis,
            steps=[step],
            expected_duration=self._estimate_duration(tool_name, params),
        )
        return plan

    def _select_tool(self, question: str) -> str | None:
        """基于关键词选择工具。"""
        q_lower = question.lower()
        for keyword, tool in self.KEYWORD_TOOL_MAP.items():
            if keyword in q_lower:
                return tool
        return None

    def _build_parameters(
        self, tool_name: str, question: str, hypothesis: str
    ) -> dict[str, Any]:
        """构建工具调用参数（启发式默认值）。"""
        if tool_name == "adjust_breath_cycle":
            # 简单启发式：如果提到"延长"或"缩短"，调整对应相位
            params = {}
            if "延长" in question or "longer" in question.lower():
                params["contract_ms"] = 150  # 延长 CONTRACT
            elif "缩短" in question or "shorter" in question.lower():
                params["contract_ms"] = 50   # 缩短 CONTRACT
            return params
        elif tool_name == "resonate_with_node":
            # 从 question 中提取 node_id（未来可 NLP 解析；目前默认占位符）
            return {"node_id": "partner-close", "duration": 5.0}
        elif tool_name == "check_physics_anchor":
            return {"steps": 5000, "dt": 0.01}
        elif tool_name == "extract_feature":
            # 从 question 推断 sensor_type
            if "温度" in question or "temperature" in question.lower():
                return {"sensor_type": "temperature", "raw_value": 25.0}
            else:
                return {"sensor_type": "vibration", "raw_value": 0.5}
        return {}

    def _estimate_duration(self, tool_name: str, params: dict) -> float:
        """估算工具执行时间（秒）。"""
        if tool_name == "adjust_breath_cycle":
            return 1.0
        elif tool_name == "resonate_with_node":
            return params.get("duration", 5.0)
        elif tool_name == "check_physics_anchor":
            return params.get("steps", 5000) * 0.0001  # ~0.5s for 5000
        elif tool_name == "extract_feature":
            return 0.1
        return 1.0

    def get_available_tools(self) -> list[str]:
        return list(self.tools.keys())
