"""
Skill Abstractor — Phase 5.4

从动作-感知变化历史中挖掘频繁的动作序列模式，并将其提炼为"宏动作"（macro-action）。
宏动作是高级抽象：一旦定义，可作为原子动作被调用，执行时展开为底层动作序列。

设计：
- 使用滑动窗口记录最近 N 条 (action_signature, delta) 对
- 在窗口内枚举 n-grams (n=2..max_ngram)，统计频次并累加合并 delta
- 当某 pattern 支持度 ≥ min_support 时，创建 MacroDefinition
- 宏动作签名格式：macro_<action1>_<action2>_...（按出现顺序拼接）
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import math


@dataclass(frozen=True)
class MacroDefinition:
    """一个被提炼出的宏动作定义。"""
    signature: str                      # 宏动作唯一标识（如 "macro_A_B"）
    sequence: Tuple[str, ...]           # 底层动作序列
    avg_delta: Dict[str, float]         # 平均合并后的传感器变化
    support: int                        # 该 pattern 被观测到的次数


class SkillAbstractor:
    """
    技能抽象器：持续观察动作流，周期性地挖掘重复模式并生成宏动作。

    使用方式：
        abstractor = SkillAbstractor(min_support=5, max_ngram=3)
        for each cycle after action recorded:
            abstractor.record(action_sig, delta)
            new_macros = abstractor.mine()
            for macro in new_macros:
                print(f"Discovered {macro.signature}")
    """

    def __init__(
        self,
        min_support: int = 5,
        max_ngram: int = 3,
        window_size: int = 100,
    ):
        """
        Args:
            min_support: 模式最小支持度（出现次数）阈值，低于此值不生成宏。
            max_ngram: 最大考虑的序列长度（n-gram 上限）。
            window_size: 滑动窗口大小，仅分析最近这么多条动作记录。
        """
        self.min_support = min_support
        self.max_ngram = max_ngram
        self.window_size = window_size
        self.history: deque[Tuple[str, Dict[str, float]]] = deque(maxlen=window_size)
        self.macros: Dict[str, MacroDefinition] = {}  # signature → definition

    def record(self, action_sig: str, delta: Dict[str, float]) -> None:
        """
        记录一次动作及其导致的传感器变化。

        Args:
            action_sig: 动作签名字符串。
            delta: 传感器变化量 dict {sensor: delta_value}。
        """
        self.history.append((action_sig, delta))

    def mine(self) -> List[MacroDefinition]:
        """
        在历史窗口内枚举 n-grams，发现新 pattern 并创建宏。

        Returns:
            本次挖掘新创建的 MacroDefinition 列表（重复调用不会重复创建）。
        """
        n = len(self.history)
        if n < 2:
            return []

        seq = [entry[0] for entry in self.history]
        deltas = [entry[1] for entry in self.history]

        # 统计 pattern 的频次与合并 delta 总和
        pattern_counts: Dict[Tuple[str, ...], int] = {}
        pattern_delta_sums: Dict[Tuple[str, ...], Dict[str, float]] = {}

        for gram_len in range(2, min(self.max_ngram, n) + 1):
            for i in range(n - gram_len + 1):
                pattern = tuple(seq[i : i + gram_len])
                # 合并该 occurrence 的 delta
                combined: Dict[str, float] = {}
                for j in range(gram_len):
                    d = deltas[i + j]
                    for sensor, val in d.items():
                        combined[sensor] = combined.get(sensor, 0.0) + val
                # 累加
                if pattern not in pattern_counts:
                    pattern_counts[pattern] = 1
                    pattern_delta_sums[pattern] = combined.copy()
                else:
                    pattern_counts[pattern] += 1
                    for sensor, val in combined.items():
                        pattern_delta_sums[pattern][sensor] = pattern_delta_sums[pattern].get(sensor, 0.0) + val

        new_macros: List[MacroDefinition] = []
        for pattern, count in pattern_counts.items():
            if count < self.min_support:
                continue
            signature = f"macro_{'_'.join(pattern)}"
            if signature in self.macros:
                continue
            avg_delta = {
                sensor: total / count
                for sensor, total in pattern_delta_sums[pattern].items()
            }
            macro = MacroDefinition(
                signature=signature,
                sequence=pattern,
                avg_delta=avg_delta,
                support=count,
            )
            self.macros[signature] = macro
            new_macros.append(macro)

        return new_macros

    def get_all_macros(self) -> List[MacroDefinition]:
        """返回当前已发现的所有宏动作定义。"""
        return list(self.macros.values())

    def get_macro(self, signature: str) -> MacroDefinition | None:
        """根据签名获取单个宏定义。"""
        return self.macros.get(signature)
