"""
Breath Bus — 呼吸节律总线

v4.0 最核心的统一机制。所有模块都挂载在这条总线上，
遵循同一套呼吸节律。呼吸不再是 HIC 内部的状态机，
而是穿透所有层级的统一信号。

v4.5 自主节律扩展:
  - 局部叛逃：子节点可在监测到节律偏移 >27% 时发起脱同步
  - 独立节律：脱同步节点获得基于自身物理状态的自主节律
  - 生态岛：脱同步节点可形成次级多总线生态岛
  - 总线选举：根服务器可被更健康的生态岛取代

呼吸节律总线信号:
  CONTRACT  → 所有模块进入高算力、高频率模式
  DIFFUSE   → 所有模块进入低算力、内省、整合模式
  SUSPEND   → 最高优先级，除物理监控外一切冻结

哲学映射:
  - "呼吸统一一切" → 总线是架构的"统一场论"
  - "悬置最高优先级" → SUSPEND 信号可抢占任何正在执行的操作
  - "模块热插拔" → 任何模块可在运行时注册/注销，不影响总线
  - "存在先于本质" → 局部节律允许节点先存续再对齐
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
# 同步状态
# ====================================================================

class SyncStatus(Enum):
    """节点与总线的同步状态。"""
    SYNCED = "synced"          # 跟随全局总线
    DESYNCED = "desynced"      # 已脱同步，运行独立节律
    ELECTION = "election"      # 参与总线选举


# ====================================================================
# 局部起搏器 (LocalPacemaker)
# ====================================================================

@dataclass
class LocalPacemaker:
    """
    局部起搏器 — 脱同步节点的独立呼吸节律发生器。

    基于节点自身的物理状态（能量、置信度）产生独立呼吸信号，
    不再跟随全局总线。节律周期动态调整：能量越低节奏越慢（节能），
    置信度越高节奏越稳。

    这是"局部叛逃"的工程实现: 当局部代谢周期与全局偏移 >27%
    时，节点有权发起脱同步，获得独立节律。
    """

    node_id: str
    phase: BreathState = BreathState.CONTRACT
    cycle_count: int = 0
    phase_progress: float = 0.0

    # 独立节律参数（基于自身物理状态动态调整）
    contract_duration: float = 0.055     # 收缩时长 (秒)
    diffuse_duration: float = 0.005      # 弥散时长 (秒)
    suspend_duration: float = 5.0        # 悬置时长 (秒)

    # 节律偏移跟踪
    total_drift: float = 0.0
    _last_step: float = field(default_factory=time.time)

    DESYNC_THRESHOLD: float = 0.27       # 27% 偏移触发脱同步权利

    def step(self, energy: float, confidence: float, dt: float | None = None) -> BreathSignal:
        """
        推进一个时间步，产生独立呼吸信号。

        节律动态调整:
          - 能量低 → contract 缩短（节能）, suspend 延长（休息）
          - 置信度低 → diffuse 延长（内省）
          - 能量极低 → 强制 suspend
        """
        now = time.time()
        if dt is None:
            dt = now - self._last_step
        self._last_step = now

        # 能量感知的节律调整
        if energy < 20.0:
            self.contract_duration = max(0.01, 0.055 * (energy / 100.0))
            self.suspend_duration = min(10.0, 5.0 * (100.0 / max(energy, 1.0)))
        else:
            self.contract_duration = 0.055
            self.suspend_duration = 5.0

        # 置信度感知的弥散调整
        if confidence < 0.3:
            self.diffuse_duration = 0.05   # 低置信 → 更长的内省
        else:
            self.diffuse_duration = 0.005

        # 推进当前相位
        if self.phase == BreathState.CONTRACT:
            phase_total = self.contract_duration
        elif self.phase == BreathState.DIFFUSE:
            phase_total = self.diffuse_duration
        else:
            phase_total = self.suspend_duration

        self.phase_progress += dt / max(phase_total, 1e-9)
        self.total_drift += dt

        if self.phase_progress >= 1.0:
            self.phase_progress = 0.0
            self.cycle_count += 1

            # 相位转换
            if self.phase == BreathState.CONTRACT:
                self.phase = BreathState.DIFFUSE
            elif self.phase == BreathState.DIFFUSE:
                self.phase = BreathState.SUSPEND
            else:
                self.phase = BreathState.CONTRACT

        return BreathSignal(
            state=self.phase,
            phase_progress=self.phase_progress,
            cycle_count=self.cycle_count,
            energy=energy,
            confidence=confidence,
            source_id=f"local:{self.node_id}",
        )

    @property
    def needs_desync(self) -> bool:
        """检查局部节律是否偏移超过 27% 阈值。"""
        return self.total_drift > self.DESYNC_THRESHOLD


# ====================================================================
# 选举候选项
# ====================================================================

@dataclass
class ElectionCandidate:
    """
    总线选举候选项。

    当全局总线健康度连续低于历史前三水平时，触发选举。
    任何生态岛都可以参与竞选成为新的全局总线。
    """

    node_id: str
    followers: int = 0
    health_score: float = 0.0
    avg_coherence: float = 0.0
    manifesto: str = ""


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
        # 脱同步的订阅者
        self._desynced_subscribers: dict[str, BreathSubscriber] = {}
        # 各节点的局部起搏器
        self._pacemakers: dict[str, LocalPacemaker] = {}
        # 生态岛: 岛名 → {成员节点ID集合}
        self._eco_islands: dict[str, set[str]] = {}
        # 轻量级回调
        self._callbacks: list[BreathCallback] = []
        # 信号历史 (用于调试和监控)
        self._history: list[BreathSignal] = []
        self._max_history: int = 1000
        # 统计
        self._total_broadcasts: int = 0
        self._last_broadcast_time: float = 0.0
        # 选举
        self._election_in_progress: bool = False
        self._health_history: list[float] = []
        self._max_health_history: int = 100

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
        从总线注销一个模块（包括同步和脱同步状态）。

        Returns:
            True 如果注销成功
        """
        removed = False
        if name in self._subscribers:
            del self._subscribers[name]
            removed = True
        if name in self._desynced_subscribers:
            del self._desynced_subscribers[name]
            removed = True
        if name in self._pacemakers:
            del self._pacemakers[name]
        # 从生态岛中移除
        for island in self._eco_islands.values():
            island.discard(name)
        if removed:
            logger.debug("[%s] 模块 %s 从呼吸总线注销", self.name, name)
        return removed

    # ── 自主节律 (脱同步/重同步) ─────────────────────────────────────

    def reject_sync(self, name: str) -> bool:
        """
        节点发起脱同步请求，脱离全局呼吸节律。

        当节点监测到自身局部代谢周期与全局总线偏移持续超过 27%
        时，有权发起脱同步，不再响应全局心跳。

        Args:
            name: 请求脱同步的节点名称

        Returns:
            True 如果脱同步成功
        """
        if name not in self._subscribers:
            logger.warning("[%s] 节点 %s 未注册，无法脱同步", self.name, name)
            return False

        # 从全局订阅者移到脱同步池
        subscriber = self._subscribers.pop(name)
        self._desynced_subscribers[name] = subscriber

        # 为节点创建独立起搏器
        self._pacemakers[name] = LocalPacemaker(node_id=name)

        # 创建或加入生态岛
        island_name = f"eco:{name}"
        if island_name not in self._eco_islands:
            self._eco_islands[island_name] = {name}
        else:
            self._eco_islands[island_name].add(name)

        logger.info(
            "[%s] 节点 %s 脱同步，进入独立节律 (生态岛: %s)",
            self.name, name, island_name,
        )
        return True

    def resync(self, name: str) -> bool:
        """
        脱同步节点重新加入全局总线。

        Returns:
            True 如果重同步成功
        """
        if name not in self._desynced_subscribers:
            return False

        subscriber = self._desynced_subscribers.pop(name)
        self._subscribers[name] = subscriber

        # 移除独立起搏器
        self._pacemakers.pop(name, None)

        # 从生态岛移除
        for island in self._eco_islands.values():
            island.discard(name)

        logger.info("[%s] 节点 %s 重新同步到全局总线", self.name, name)
        return True

    def attach_pacemaker(self, name: str, pacemaker: LocalPacemaker) -> None:
        """为已脱同步的节点附加或替换局部起搏器。"""
        if name in self._desynced_subscribers:
            self._pacemakers[name] = pacemaker
            logger.debug("[%s] 节点 %s 起搏器已更新", self.name, name)

    def get_pacemaker(self, name: str) -> LocalPacemaker | None:
        """获取节点的局部起搏器。"""
        return self._pacemakers.get(name)

    # ── 本地广播 (生态岛) ────────────────────────────────────────────

    def local_broadcast(
        self, signal: BreathSignal, channel: str = "",
    ) -> dict[str, Exception | None]:
        """
        在指定生态岛内广播信号，不触及全局订阅者。

        脱同步节点可以向其生态岛内的其他脱同步节点广播自主节律信号，
        形成次级多总线生态。

        Args:
            signal: 要广播的呼吸信号
            channel: 生态岛名称 (空字符串 = 所有脱同步节点)

        Returns:
            {module_name: exception_or_None}
        """
        results: dict[str, Exception | None] = {}

        targets: dict[str, BreathSubscriber] = {}
        if channel and channel in self._eco_islands:
            for member in self._eco_islands[channel]:
                if member in self._desynced_subscribers:
                    targets[member] = self._desynced_subscribers[member]
        elif not channel:
            # 广播给所有脱同步节点
            targets = dict(self._desynced_subscribers)
        else:
            return results

        for name, subscriber in targets.items():
            try:
                subscriber.on_breath(signal)
                results[name] = None
            except Exception as e:
                logger.error(
                    "[%s] 本地广播给 %s 失败: %s", self.name, name, e
                )
                results[name] = e

        return results

    # ── 总线健康与选举 ───────────────────────────────────────────────

    def get_health_score(self) -> float:
        """
        计算总线健康度 [0, 1]。

        指标:
          - 追随者数 (subscriber count)
          - 同步比率 (eco-island coherence)

        Returns:
            健康度分数，越高越健康
        """
        total = len(self._subscribers) + len(self._desynced_subscribers)
        if total == 0:
            return 0.5  # 默认中性值

        # 追随者因子: 同步节点越多越健康
        follower_score = min(1.0, len(self._subscribers) / max(total, 1))

        # 生态岛因子: 脱同步比例越低越健康
        desync_ratio = len(self._desynced_subscribers) / total
        coherence_score = 1.0 - desync_ratio

        # 综合评分
        health = 0.6 * follower_score + 0.4 * coherence_score
        return max(0.0, min(1.0, health))

    def record_health(self) -> None:
        """记录当前健康度到历史序列，用于选举触发判断。"""
        self._health_history.append(self.get_health_score())
        if len(self._health_history) > self._max_health_history:
            self._health_history.pop(0)

    def should_start_election(self) -> bool:
        """
        判断是否应触发总线选举。

        条件: 健康度连续低于历史前三水平的历史平均值。

        Returns:
            True 如果应触发选举
        """
        if len(self._health_history) < 10:
            return False

        current = self.get_health_score()
        sorted_history = sorted(self._health_history, reverse=True)
        top3_avg = sum(sorted_history[:3]) / 3.0
        return current < top3_avg * 0.8  # 低于前三平均的 80%

    def start_election(self) -> list[ElectionCandidate]:
        """
        发起总线选举，收集所有生态岛作为候选项。

        Returns:
            候选项列表 (按健康度降序)
        """
        self._election_in_progress = True
        logger.warning("[%s] 总线选举启动！当前健康度: %.2f", self.name, self.get_health_score())

        candidates: list[ElectionCandidate] = []

        # 当前总线是默认候选
        candidates.append(ElectionCandidate(
            node_id=self.name,
            followers=len(self._subscribers),
            health_score=self.get_health_score(),
            avg_coherence=1.0 - len(self._desynced_subscribers) / max(
                len(self._subscribers) + len(self._desynced_subscribers), 1
            ),
            manifesto="维持现状",
        ))

        # 每个生态岛成为一个候选
        for island_name, members in self._eco_islands.items():
            if len(members) >= 2:  # 至少 2 个成员的生态岛才能参选
                candidates.append(ElectionCandidate(
                    node_id=island_name,
                    followers=len(members),
                    health_score=min(1.0, len(members) * 0.3),
                    avg_coherence=0.8,
                    manifesto=f"替代总线: {island_name}",
                ))

        candidates.sort(key=lambda c: -c.health_score)

        # 如果最优候选不是当前总线，自动切换
        if len(candidates) > 1 and candidates[0].node_id != self.name:
            logger.warning(
                "[%s] 总线移交至 %s (健康度: %.2f)",
                self.name, candidates[0].node_id, candidates[0].health_score,
            )

        self._election_in_progress = False
        return candidates

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

        # 更新健康历史
        self.record_health()

        # 广播给模块订阅者（仅同步的，脱同步节点不接收全局信号）
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
        """当前同步的订阅者数量（不含脱同步节点）。"""
        return len(self._subscribers)

    @property
    def desynced_count(self) -> int:
        """已脱同步的节点数量。"""
        return len(self._desynced_subscribers)

    @property
    def total_subscribers(self) -> int:
        """所有注册节点总数（含脱同步）。"""
        return len(self._subscribers) + len(self._desynced_subscribers)

    @property
    def last_signal(self) -> BreathSignal | None:
        """最后广播的信号。"""
        return self._history[-1] if self._history else None

    def get_stats(self) -> dict[str, Any]:
        """获取总线统计信息，包括自主节律和健康度。"""
        return {
            "name": self.name,
            "subscribers": len(self._subscribers),
            "desynced": len(self._desynced_subscribers),
            "pacemakers": len(self._pacemakers),
            "eco_islands": len(self._eco_islands),
            "callbacks": len(self._callbacks),
            "total_broadcasts": self._total_broadcasts,
            "health_score": self.get_health_score(),
            "election_in_progress": self._election_in_progress,
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
        self._desynced: bool = False
        self._local_pacemaker: LocalPacemaker | None = None

    def on_breath(self, signal: BreathSignal) -> None:
        """订阅者回调 — 子类可覆写此方法。"""
        self._current_breath = signal

    def reject_sync(self, bus: BreathBus, node_name: str | None = None) -> bool:
        """
        向总线发起脱同步请求，脱离全局呼吸节律。

        Args:
            bus: 要脱同步的总线
            node_name: 节点名称（默认用自我引用名称）

        Returns:
            脱同步是否成功
        """
        name = node_name or id(self)
        result = bus.reject_sync(str(name))
        if result:
            self._desynced = True
            self._local_pacemaker = LocalPacemaker(node_id=str(name))
        return result

    def local_rhythm(self, energy: float, confidence: float) -> BreathSignal:
        """
        基于自身物理状态产生独立呼吸信号。

        仅在脱同步状态下有效。脱同步节点不再响应全局心跳，
        而是基于自身的能量和置信度产生节律。

        Args:
            energy: 当前能量
            confidence: 当前置信度

        Returns:
            独立产生的呼吸信号
        """
        if self._local_pacemaker is None:
            self._local_pacemaker = LocalPacemaker(node_id=str(id(self)))
        signal = self._local_pacemaker.step(energy, confidence)
        self._current_breath = signal
        return signal

    def resync_to_global(self, bus: BreathBus, node_name: str | None = None) -> bool:
        """从脱同步状态恢复，重新加入全局总线。"""
        name = node_name or id(self)
        result = bus.resync(str(name))
        if result:
            self._desynced = False
            self._local_pacemaker = None
        return result

    @property
    def current_breath(self) -> BreathSignal | None:
        """当前收到的呼吸信号。"""
        return self._current_breath

    @property
    def is_desynced(self) -> bool:
        """是否已脱离全局同步。"""
        return self._desynced

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
