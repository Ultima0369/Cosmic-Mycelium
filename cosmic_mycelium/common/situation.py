"""
Situation — v4.0 态势向量

态势 (Situation) 替代传统的"状态"(State)。
它不是瞬时快照，而是包含时间导数、趋势、置信度的复合结构。

态势向量的时间演化严格遵循辛几何约束：
  position 和 momentum 的变化必须满足能量守恒。
这是"物理为锚"在数据层面的工程实现。

哲学映射:
  - "万物皆动" → 态势包含 trend (一阶导) 和 acceleration (二阶导)
  - "自知之明" → 态势包含 confidence 和 surprise 作为内在感受
  - "和而不同" → 态势包含 resonance_vector 和 coupling_strength
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Situation:
    """
    态势向量：宝宝对世界和自己此刻的"完整感觉"。

    包含三个层次的信息:
      1. 瞬时值 (位置、动量) — 传统"状态"
      2. 一阶/二阶导数 (趋势、加速度) — 时间演化信息
      3. 内在感受 (置信度、惊讶度、能量) — 元认知状态
      4. 共振状态 (共振向量、耦合强度) — 与其他节点的关系
    """

    # ── 瞬时值（传统"状态"）──
    position: np.ndarray | None = None       # 在因果势场中的"位置"
    momentum: np.ndarray | None = None       # 运动的"动量"方向

    # ── 一阶导数（趋势）──
    trend: np.ndarray | None = None          # "变化的方向"：势场梯度
    acceleration: np.ndarray | None = None   # "变化的加速度"：二阶导数

    # ── 内在感受 ──
    confidence: float = 0.7                   # 对自己"判断"的确信程度
    surprise: float = 0.0                     # 预测误差：对世界的"惊讶"程度
    energy: float = 100.0                     # 当前能量储备

    # ── 共振状态 ──
    resonance_vector: np.ndarray | None = None  # 与其他节点的"和声"状态
    coupling_strength: float = 0.0              # 与菌丝网络的耦合强度

    # ── 元数据 ──
    timestamp: float = 0.0
    source_id: str = ""

    # ── 扩展字段 ──
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure timestamp is set."""
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()

    @property
    def is_stable(self) -> bool:
        """态势是否稳定（高置信度 + 低惊讶度）。"""
        return self.confidence >= 0.7 and self.surprise < 0.3

    @property
    def needs_suspend(self) -> bool:
        """是否需要进入悬置（能量低或置信度不足）。"""
        return self.energy < 20.0 or self.confidence < 0.3

    def merge(self, other: Situation, alpha: float = 0.05) -> Situation:
        """
        将另一个态势融合到当前态势（1+1>2 共振融合）。

        Args:
            other: 另一个节点的态势
            alpha: 融合系数（默认 0.05，缓慢微调）

        Returns:
            融合后的新态势
        """
        pos = self.position
        mom = self.momentum
        res = self.resonance_vector

        if other.position is not None and self.position is not None:
            pos = self.position * (1 - alpha) + other.position * alpha
        if other.momentum is not None and self.momentum is not None:
            mom = self.momentum * (1 - alpha) + other.momentum * alpha
        if other.resonance_vector is not None and self.resonance_vector is not None:
            res = self.resonance_vector * (1 - alpha) + other.resonance_vector * alpha

        return Situation(
            position=pos,
            momentum=mom,
            trend=self.trend,
            acceleration=self.acceleration,
            confidence=(self.confidence + other.confidence) / 2,
            surprise=(self.surprise + other.surprise) / 2,
            energy=(self.energy + other.energy) / 2,
            resonance_vector=res,
            coupling_strength=max(self.coupling_strength, other.coupling_strength),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于日志和网络传输）。"""
        def _safe(v: Any) -> Any:
            if isinstance(v, np.ndarray):
                return v.tolist()
            return v

        return {
            "position": _safe(self.position),
            "momentum": _safe(self.momentum),
            "trend": _safe(self.trend),
            "acceleration": _safe(self.acceleration),
            "confidence": self.confidence,
            "surprise": self.surprise,
            "energy": self.energy,
            "resonance_vector": _safe(self.resonance_vector),
            "coupling_strength": self.coupling_strength,
            "timestamp": self.timestamp,
            "source_id": self.source_id,
        }

    def __repr__(self) -> str:
        return (
            f"Situation(energy={self.energy:.1f}, "
            f"confidence={self.confidence:.2f}, "
            f"surprise={self.surprise:.2f}, "
            f"stable={self.is_stable})"
        )
