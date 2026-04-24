"""
Sensorimotor Contingency Learner — Phase 5.1

学习 "动作 → 感知变化" 的映射，识别可操控性。
对应 ROADMAP 5.1: Sensorimotor Contingency Learner

设计：
- 记录 (action, prev_sensors, post_sensors) 三元组
- 维护每个动作的典型 delta (移动平均)
- predict(action, current_sensors) 预测执行后的传感器值
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Observation:
    """单次传感器过渡记录 (prev → post)，用于交叉验证拆分。"""
    prev: Dict[str, float]
    post: Dict[str, float]


@dataclass
class SensorReading:
    """单次传感器快照。"""
    timestamp: float
    values: Dict[str, float]


@dataclass
class ContingencyRecord:
    """
    一个动作的典型效果统计。

    同时保存原始观测 (prev, post) 对（用于交叉验证拆分）和聚合的 delta 统计。
    """

    action_signature: str
    max_history: int = 100
    _observations: list[tuple[Dict[str, float], Dict[str, float]]] = field(
        default_factory=list, init=False
    )  # [(prev, post), ...]
    avg_delta: Dict[str, float] = field(default_factory=dict, init=False)
    total_observations: int = field(default=0, init=False)

    def add_observation(
        self, prev: Dict[str, float], post: Dict[str, float]
    ) -> None:
        """添加一次观测（前/后传感器），更新移动平均 delta。"""
        self._observations.append((prev, post))
        self.total_observations += 1
        if len(self._observations) > self.max_history:
            self._observations.pop(0)
        self._recompute_average()

    def _recompute_average(self) -> None:
        """根据当前所有观测重新计算平均 delta。"""
        if not self._observations:
            return
        deltas = []
        for prev, post in self._observations:
            delta = {
                s: post.get(s, 0.0) - prev.get(s, 0.0)
                for s in set(prev) | set(post)
            }
            deltas.append(delta)
        sensors = set()
        for d in deltas:
            sensors.update(d.keys())
        self.avg_delta = {
            sensor: sum(d.get(sensor, 0.0) for d in deltas) / len(deltas)
            for sensor in sensors
        }


class SensorimotorContingencyLearner:
    """
    具身认知核心：学习动作如何改变感知。

    用例：
        learner = SensorimotorContingencyLearner()
        prev = {"vibration": 0.2, "temperature": 25.0}
        # ... 执行某个动作 ...
        post = {"vibration": 0.8, "temperature": 25.1}
        learner.record("adjust_breath_cycle(contract_ms=150)", prev, post)

        # 预测：如果当前传感器是 X，执行动作 A 后会变成什么
        current = {"vibration": 0.3, "temperature": 25.0}
        predicted = learner.predict("adjust_breath_cycle(contract_ms=150)", current)
        # → {"vibration": 0.9, "temperature": 25.1}
    """

    def __init__(self, max_history_per_action: int = 100):
        """
        Args:
            max_history_per_action: 每个动作保留的最大观测次数（滑动窗口）
        """
        self.max_history = max_history_per_action
        # action_signature → ContingencyRecord
        self._records: Dict[str, ContingencyRecord] = {}
        # 全局时序：用于去重和老化
        self._last_update: float = 0.0

    # ----------------------------------------------------------------------
    # 数据记录
    # ----------------------------------------------------------------------
    def record(
        self,
        action_signature: str,
        prev_sensors: Dict[str, float],
        post_sensors: Dict[str, float],
    ) -> None:
        """
        记录一次动作-感知三元组。

        Args:
            action_signature: 动作的唯一字符串标识（如 "adjust_breath_cycle(contract_ms=150)"）
            prev_sensors: 动作执行前的传感器读数
            post_sensors: 动作执行后的传感器读数
        """
        if action_signature not in self._records:
            self._records[action_signature] = ContingencyRecord(
                action_signature, max_history=self.max_history
            )

        self._records[action_signature].add_observation(prev_sensors, post_sensors)
        self._last_update = time.time()

    # ----------------------------------------------------------------------
    # 预测
    # ----------------------------------------------------------------------
    def predict(
        self,
        action_signature: str,
        current_sensors: Dict[str, float],
    ) -> Dict[str, float] | None:
        """
        预测执行动作后的传感器值。

        Args:
            action_signature: 要执行的动作
            current_sensors: 当前传感器读数

        Returns:
            预测的 post-sensors dict，或 None（未知动作）
        """
        record = self._records.get(action_signature)
        if record is None or not record.avg_delta:
            return None

        # 当前值 + 典型变化量
        predicted = current_sensors.copy()
        for sensor, delta in record.avg_delta.items():
            predicted[sensor] = predicted.get(sensor, 0.0) + delta
        return predicted

    def get_contingency(self, action_signature: str) -> Dict[str, float] | None:
        """
        获取某个动作的典型 delta 向量。

        Returns:
            sensor_name → avg_delta mapping，或 None（无记录）
        """
        record = self._records.get(action_signature)
        return record.avg_delta if record else None

    # ----------------------------------------------------------------------
    # 查询
    # ----------------------------------------------------------------------
    def known_actions(self) -> list[str]:
        """返回所有已学习的动作签名列表。"""
        return list(self._records.keys())

    def get_confidence(self, action_signature: str) -> float:
        """
        返回对某个动作预测的置信度（基于观测次数）。

        Returns:
            [0.0, 1.0] — 观测次数经过 sigmoid 归一化，饱和于 ~20 次
        """
        record = self._records.get(action_signature)
        if not record:
            return 0.0
        # sigmoid: n ∈ [0, ∞] → [0, 1], 20 次后饱和到 ~0.99
        n = record.total_observations
        return n / (n + 5.0)  # 简单饱和函数，5 次后达 0.67，20 次后达 0.8

    def get_status(self) -> Dict[str, any]:
        """返回学习器状态摘要（用于监控）。"""
        return {
            "known_actions": len(self._records),
            "total_observations": sum(r.total_observations for r in self._records.values()),
            "actions": list(self._records.keys()),
        }

    # ----------------------------------------------------------------------
    # 逆模型 — 从感知变化推断动作
    # ----------------------------------------------------------------------
    def infer_action(
        self, prev_sensors: Dict[str, float], post_sensors: Dict[str, float], k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        逆映射：给定传感器前后变化，推断最可能执行了哪个动作。

        Args:
            prev_sensors: 动作前的传感器读数
            post_sensors: 动作后的传感器读数
            k: 返回前 k 个最可能的动作假设

        Returns:
            排序列表 [(action_signature, confidence), ...]，置信度总和为 1.0
        """
        observed_delta = {
            s: post_sensors.get(s, 0.0) - prev_sensors.get(s, 0.0)
            for s in set(prev_sensors) | set(post_sensors)
        }

        # 计算每个动作的匹配分数（负 MSE）并辅以观测次数加权
        raw_scores: Dict[str, float] = {}
        for action_sig, record in self._records.items():
            if not record.avg_delta:
                continue
            mse = 0.0
            for sensor, obs_delta in observed_delta.items():
                pred_delta = record.avg_delta.get(sensor, 0.0)
                mse += (obs_delta - pred_delta) ** 2
            # 观测次数作为置信度先验（log 平滑）
            count_boost = math.log(record.total_observations + 1)
            raw_scores[action_sig] = -mse + count_boost

        if not raw_scores:
            return []

        # Softmax 转换为归一化置信度
        max_score = max(raw_scores.values())
        exp_scores = {a: math.exp(s - max_score) for a, s in raw_scores.items()}
        total = sum(exp_scores.values())
        confidences = {a: v / total for a, v in exp_scores.items()}

        # Top-k 排序
        ranked = sorted(confidences.items(), key=lambda x: x[1], reverse=True)
        return ranked[:k] if k > 0 else []

    def train_test_split(
        self, test_ratio: float = 0.3
    ) -> Tuple[List[Observation], List[Observation]]:
        """
        将所有动作的观测记录划分为训练集和测试集。

        Args:
            test_ratio: 测试集比例 (0.0–1.0)

        Returns:
            (train_observations, test_observations) — 两个 Observation 列表
        """
        if not 0.0 <= test_ratio <= 1.0:
            raise ValueError(f"test_ratio must be in [0,1], got {test_ratio}")

        # 收集所有动作的原始观测
        all_obs: List[Tuple[Dict[str, float], Dict[str, float]]] = []
        for record in self._records.values():
            all_obs.extend(record._observations)

        if not all_obs:
            return [], []

        # 可复现的随机打乱
        random.Random(42).shuffle(all_obs)

        n_test = int(len(all_obs) * test_ratio)
        n_train = len(all_obs) - n_test

        train_raw = all_obs[:n_train]
        test_raw = all_obs[n_train:]

        train = [Observation(prev, post) for prev, post in train_raw]
        test = [Observation(prev, post) for prev, post in test_raw]
        return train, test
