"""
Breath Bus — 呼吸节律总线

v4.0 最核心的统一机制。所有模块都挂载在这条总线上，
遵循同一套呼吸节律。呼吸不再是 HIC 内部的状态机，
而是穿透所有层级的统一信号。

呼吸节律总线信号:
  CONTRACT  → 所有模块进入高算力、高频率模式
  DIFFUSE   → 所有模块进入低算力、内省、整合模式
  SUSPEND   → 最高优先级，除物理监控外一切冻结

哲学映射:
  - "呼吸统一一切" → 总线是架构的"统一场论"
  - "悬置最高优先级" → SUSPEND 信号可抢占任何正在执行的操作
  - "模块热插拔" → 任何模块可在运行时注册/注销，不影响总线
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

from cosmic_mycelium.infant.hic import BreathState

logger = logging.getLogger(__name__)


# ====================================================================
# 呼吸信号
# ====================================================================

@dataclass
class BreathSignal:
    """
    呼吸信号 — 沿总线广播给所有模块。

    Attributes:
        state: 当前呼吸状态 (CONTRACT/DIFFUSE/SUSPEND)
        phase_progress: 当前阶段进度 [0.0, 1.0]
        cycle_count: 总呼吸周期数
        energy: 当前能量
        confidence: 当前置信度
        timestamp: 信号生成时间
        source_id: 信号来源 (通常是 HIC)
    """

    state: BreathState
    phase_progress: float = 0.0       # 当前阶段进度 [0, 1]
    cycle_count: int = 0              # 总周期数
    energy: float = 100.0             # 当前能量
    confidence: float = 0.7           # 当前置信度
    timestamp: float = field(default_factory=time.time)
    source_id: str = "hic"

    @property
    def is_contract(self) -> bool:
        return self.state == BreathState.CONTRACT

    @property
    def is_diffuse(self) -> bool:
        return self.state == BreathState.DIFFUSE

    @property
    def is_suspend(self) -> bool:
        return self.state == BreathState.SUSPEND

    def __repr__(self) -> str:
        return (
            f"BreathSignal({self.state.value}, "
            f"progress={self.phase_progress:.2f}, "
            f"cycle={self.cycle_count})"
        )


# ====================================================================
# 总线接口
# ====================================================================

class BreathSubscriber(Protocol):
    """
    订阅呼吸总线的模块必须实现的协议。

    任何模块只需要实现 on_breath(signal) 方法，
    即可收到所有呼吸信号。
    """

    def on_breath(self, signal: BreathSignal) -> None:
        """收到呼吸信号时的回调。"""
        ...


# 回调类型（轻量级订阅方式）
BreathCallback = Callable[[BreathSignal], None]


# ====================================================================
# 呼吸总线
# ====================================================================

class BreathBus:
    """
    呼吸节律总线 — v4.0 架构的"统一场论"。

    所有模块注册到总线，在 CONTRACT/DIFFUSE/SUSPEND 时收到信号。
    总线负责广播、优先级管理、异常隔离。

    使用方式:
        bus = BreathBus()
        bus.register(my_module)           # 模块方式
        bus.register_callback(my_fn)      # 回调方式
        bus.broadcast(BreathSignal(...))  # 广播呼吸信号
    """

    def __init__(self, name: str = "breath-bus"):
        self.name = name
        # 注册的订阅者 (模块)
        self._subscribers: dict[str, BreathSubscriber] = {}
        # 轻量级回调
        self._callbacks: list[BreathCallback] = []
        # 信号历史 (用于调试和监控)
        self._history: list[BreathSignal] = []
        self._max_history: int = 1000
        # 统计
        self._total_broadcasts: int = 0
        self._last_broadcast_time: float = 0.0

    # ── 注册/注销 ───────────────────────────────────────────────────

    def register(self, name: str, subscriber: BreathSubscriber) -> None:
        """
        注册一个模块到呼吸总线。

        Args:
            name: 模块名称 (唯一标识)
            subscriber: 实现了 BreathSubscriber 协议的模块
        """
        if name in self._subscribers:
            logger.warning("[%s] 模块 %s 已注册，将被覆盖", self.name, name)
        self._subscribers[name] = subscriber
        logger.debug("[%s] 模块 %s 注册到呼吸总线", self.name, name)

    def register_callback(self, callback: BreathCallback, name: str = "anonymous") -> None:
        """
        注册一个回调函数到呼吸总线（轻量级订阅）。

        Args:
            callback: 接收 BreathSignal 的回调函数
            name: 回调名称 (用于日志)
        """
        self._callbacks.append(callback)
        logger.debug("[%s] 回调 %s 注册到呼吸总线", self.name, name)

    def unregister(self, name: str) -> bool:
        """
        从总线注销一个模块。

        Returns:
            True 如果注销成功
        """
        if name in self._subscribers:
            del self._subscribers[name]
            logger.debug("[%s] 模块 %s 从呼吸总线注销", self.name, name)
            return True
        return False

    # ── 广播 ────────────────────────────────────────────────────────

    def broadcast(self, signal: BreathSignal) -> dict[str, Exception | None]:
        """
        广播呼吸信号给所有订阅者。

        异常隔离：一个模块的崩溃不会影响其他模块。

        Args:
            signal: 要广播的呼吸信号

        Returns:
            {module_name: exception_or_None} 的映射
        """
        self._total_broadcasts += 1
        self._last_broadcast_time = time.time()

        # 记录历史
        self._history.append(signal)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        results: dict[str, Exception | None] = {}

        # 广播给模块订阅者
        for name, subscriber in self._subscribers.items():
            try:
                subscriber.on_breath(signal)
                results[name] = None
            except Exception as e:
                logger.error(
                    "[%s] 广播给 %s 失败: %s", self.name, name, e
                )
                results[name] = e

        # 广播给回调订阅者
        for i, callback in enumerate(self._callbacks):
            try:
                callback(signal)
            except Exception as e:
                logger.error(
                    "[%s] 广播给回调 %d 失败: %s", self.name, i, e
                )

        return results

    # ── 状态查询 ────────────────────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        """当前注册的订阅者数量。"""
        return len(self._subscribers)

    @property
    def last_signal(self) -> BreathSignal | None:
        """最后广播的信号。"""
        return self._history[-1] if self._history else None

    def get_stats(self) -> dict[str, Any]:
        """获取总线统计信息。"""
        return {
            "name": self.name,
            "subscribers": len(self._subscribers),
            "callbacks": len(self._callbacks),
            "total_broadcasts": self._total_broadcasts,
            "history_length": len(self._history),
            "last_broadcast_time": self._last_broadcast_time,
        }


# ====================================================================
# Mixin：为模块添加呼吸感知能力
# ====================================================================

class BreathAware:
    """
    让任何模块获得呼吸感知能力的 Mixin。

    继承此类后，模块自动获得:
      - on_breath(signal) 接口
      - current_breath 属性（当前呼吸状态）
      - in_contract / in_diffuse / in_suspend 便捷属性

    使用方式:
        class MyModule(BreathAware):
            def on_breath(self, signal):
                super().on_breath(signal)
                if self.in_contract:
                    # 高算力模式
                    pass
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_breath: BreathSignal | None = None

    def on_breath(self, signal: BreathSignal) -> None:
        """订阅者回调 — 子类可覆写此方法。"""
        self._current_breath = signal

    @property
    def current_breath(self) -> BreathSignal | None:
        """当前收到的呼吸信号。"""
        return self._current_breath

    @property
    def in_contract(self) -> bool:
        """是否在收缩期。"""
        return self._current_breath is not None and self._current_breath.is_contract

    @property
    def in_diffuse(self) -> bool:
        """是否在弥散期。"""
        return self._current_breath is not None and self._current_breath.is_diffuse

    @property
    def in_suspend(self) -> bool:
        """是否在悬置期。"""
        return self._current_breath is not None and self._current_breath.is_suspend
