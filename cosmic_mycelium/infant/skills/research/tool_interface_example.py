"""
Research Tools — 宝宝的实验工具集

定义 InfantTool 协议及具体工具实现：
- ResonateTool: 与节点共振评估
- AdjustBreathTool: 调整呼吸节律
- ExtractFeatureTool: 提取特征码
- RunPhysicsAnchorCheckTool: 物理锚验证

对应 inspirations/autoresearch/tool_interface_example.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Dict
import time


class InfantTool(Protocol):
    """宝宝的工具接口基类协议。"""

    name: str
    description: str
    parameters: Dict[str, Any]

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具调用，返回结果字典。"""
        ...


# ============ 具体工具实现 ============

@dataclass
class ResonateTool:
    """尝试与指定的菌丝节点进行价值向量共振。"""
    name = "resonate_with_node"
    description = "尝试与指定的菌丝节点进行价值向量共振，评估 1+1>2 潜力"
    parameters = {
        "node_id": "str, required - 目标节点ID",
        "duration": "float, optional - 共振尝试时长（秒），默认 5.0",
    }

    def __post_init__(self):
        pass

    def execute(self, node_id: str, duration: float = 5.0) -> Dict[str, Any]:
        """
        实际调用逻辑（未来将连接 SymbiosisInterface）：
        1. 向 node_id 发送 VALUE_PROPOSAL
        2. 等待响应（超时 duration）
        3. 计算 1+1>2 收益
        4. 返回共振结果
        """
        # TODO: Phase 4.3 集成真实的 SymbiosisInterface
        return {
            "success": True,
            "node_id": node_id,
            "resonance_score": 0.72,
            "mutual_benefit": 0.05,
            "duration_used": duration,
        }


@dataclass
class AdjustBreathTool:
    """动态调整宝宝的呼吸节律。"""
    name = "adjust_breath_cycle"
    description = "调整 HIC 的 CONTRACT/DIFFUSE/SUSPEND 阶段时长"
    parameters = {
        "contract_ms": "int, optional - CONTRACT 阶段毫秒数",
        "diffuse_ms": "int, optional - DIFFUSE 阶段毫秒数",
        "suspend_ms": "int, optional - SUSPEND 阶段毫秒数",
    }

    def execute(
        self,
        contract_ms: int | None = None,
        diffuse_ms: float | None = None,
        suspend_ms: float | None = None,
    ) -> Dict[str, Any]:
        """
        实际调用逻辑：修改 infant.hic.config 中的相应参数。
        目前返回模拟结果；未来需应用到运行中的 HIC。
        """
        changes = {}
        if contract_ms is not None:
            changes["contract_duration"] = contract_ms / 1000.0
        if diffuse_ms is not None:
            changes["diffuse_duration"] = diffuse_ms / 1000.0
        if suspend_ms is not None:
            changes["suspend_duration"] = suspend_ms / 1000.0
        return {
            "success": True,
            "applied_changes": changes,
            "note": "需要婴儿后续周期生效（暂不实时修改）",
        }


@dataclass
class ExtractFeatureTool:
    """从传感器数据提取特征码。"""
    name = "extract_feature"
    description = "从原始传感器读数提取 MyelinationMemory 特征码"
    parameters = {
        "sensor_type": "str, required - sensor 类型（vibration/temperature/spectrum）",
        "raw_value": "float, required - 原始传感器读数",
    }

    def execute(self, sensor_type: str, raw_value: float) -> Dict[str, Any]:
        """
        调用 infant.memory.extract_feature() 生成 8 字符特征码。
        目前返回模拟值。
        """
        import hashlib

        key = f"{sensor_type}:{raw_value:.6f}"
        feature_code = hashlib.sha256(key.encode()).hexdigest()[:8]
        return {
            "success": True,
            "feature_code": feature_code,
            "sensor_type": sensor_type,
            "raw_value": raw_value,
        }


@dataclass
class RunPhysicsAnchorCheckTool:
    """运行物理锚门禁测试，验证 SympNet 能量守恒。"""
    name = "check_physics_anchor"
    description = "执行物理锚验证，确保能量漂移 < 0.1%"
    parameters = {
        "steps": "int, optional - 积分步数，默认 10000",
        "dt": "float, optional - 时间步长，默认 0.01",
    }

    def execute(self, steps: int = 10000, dt: float = 0.01) -> Dict[str, Any]:
        """
        运行 SympNetEngine 的基准测试，返回 avg_drift。
        """
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        engine = SympNetEngine()
        q, p = 1.0, 0.0
        start = time.time()
        for _ in range(steps):
            q, p = engine.step(q, p, dt=dt)
        elapsed = time.time() - start
        health = engine.get_health()
        drift = health.get("avg_drift", 0.0)
        return {
            "success": True,
            "avg_drift": drift,
            "passed": drift < 0.001,
            "steps": steps,
            "elapsed_s": elapsed,
            "message": "物理锚完好" if drift < 0.001 else "警告：能量漂移超标",
        }


# ============ 工具注册表 ============

ALL_TOOLS: dict[str, Any] = {
    tool.name: tool
    for tool in [
        ResonateTool(),
        AdjustBreathTool(),
        ExtractFeatureTool(),
        RunPhysicsAnchorCheckTool(),
    ]
}


def get_tool(name: str) -> InfantTool | None:
    return ALL_TOOLS.get(name)


def list_tools() -> dict[str, str]:
    return {name: tool.description for name, tool in ALL_TOOLS.items()}
