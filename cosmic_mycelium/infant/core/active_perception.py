"""
Active Perception Gate — Phase 5.1-2

基于预测不确定性选择需要采样的传感器。
对应 ROADMAP 5.1: Active Perception

设计：
- 为每个传感器维护一个 interest_score
- 每次收到预测误差（|预测 - 实际|）后，对应传感器的分数增加
- 所有分数随时间衰减
- get_attention_mask(k) 返回兴趣最高的 k 个传感器
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class ActivePerceptionGate:
    """
    注意力门控：决定哪些传感器需要重点关注。

    用例：
        gate = ActivePerceptionGate()
        # 收到一次预测误差（实际 - 预测）
        gate.update({"vibration": 1.2, "temperature": 0.05})
        # 选择最值得关注的 2 个传感器
        mask = gate.get_attention_mask(k=2)
        # → {"vibration"}（temperature 分数低被忽略）
    """

    initial_interest: float = 0.1
    decay_rate: float = 0.9
    boost: float = 2.0
    interest_scores: Dict[str, float] = field(default_factory=dict)

    def update(self, prediction_error: Dict[str, float]) -> None:
        """
        用一次预测误差更新所有传感器的兴趣分数。

        Args:
            prediction_error: sensor_name → |预测误差| 的映射
        """
        for sensor, error in prediction_error.items():
            current = self.interest_scores.get(sensor, self.initial_interest)
            if sensor in self.interest_scores:
                # 现有：先衰减再增强
                self.interest_scores[sensor] = current * self.decay_rate + error * self.boost
            else:
                # 新传感器：误差直接成为初始兴趣（跳过衰减）
                self.interest_scores[sensor] = error * self.boost

    def decay(self) -> None:
        """全局衰减所有传感器分数（无误差输入时调用）。"""
        for sensor in list(self.interest_scores.keys()):
            self.interest_scores[sensor] *= self.decay_rate

    def get_attention_mask(self, k: int) -> Set[str]:
        """
        返回兴趣分数最高的 k 个传感器集合。

        Args:
            k: 最多返回的传感器数量

        Returns:
            传感器名称集合（若不足 k 个则返回全部）
        """
        if k <= 0:
            return set()
        sorted_sensors = sorted(
            self.interest_scores.items(), key=lambda item: item[1], reverse=True
        )
        return {sensor for sensor, _ in sorted_sensors[:k]}

    def should_sample(self, sensor: str, threshold: float) -> bool:
        """
        判断某个传感器是否值得采样。

        Args:
            sensor: 传感器名称
            threshold: 兴趣分数阈值

        Returns:
            True 如果分数 ≥ threshold
        """
        return self.interest_scores.get(sensor, self.initial_interest) >= threshold

    def reset(self) -> None:
        """清空所有兴趣分数（状态重置）。"""
        self.interest_scores.clear()
