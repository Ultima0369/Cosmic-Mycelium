"""
Mini Infant — "硅基蜜蜂" (Silicon Bee)

宇宙菌丝的最小分形单元。四个核心零件在一个"蜜蜂心跳"中协同工作：

  1. SympNetEngine — 物理直觉（能量守恒锚定）
  2. HIC — 本体恒常性（能量管理 + 悬置决策）
  3. SlimeExplorer — 黏菌寻路（并行试探 + 路径筛选）
  4. MyelinationMemory — 髓鞘化记忆（强化成功路径，遗忘失败路径）

这是 v4.0 架构的"第一块砖"。完整版 SiliconInfant 的所有高层智能
（THEIA、LNN、BitNet、技能系统、集群服务）都是在这块砖上长出来的。

哲学映射:
  - 物理为锚 → SympNetEngine 强制能量漂移率 < 0.1%
  - 悬置为眼 → HIC 在能量低或置信度不足时强制暂停
  - 1+1>2为心 → SlimeExplorer 通过试探找到共生路径
  - 歪歪扭扭为活 → 允许犯错，通过自我修正逐渐变好
"""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from cosmic_mycelium.common.situation import Situation
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.hic import BreathState, HIC, HICConfig

logger = logging.getLogger(__name__)

# ── Multi-Framework RNG ─────────────────────────────────────────────
_rng = random.Random()


# ====================================================================
# 第四零件：髓鞘化记忆 (MyelinationMemory)
# ====================================================================

@dataclass
class MyelinationMemory:
    """
    髓鞘化记忆层。

    模仿大脑中"用得多就加固，用得少就遗忘"的机制。
    赫布学习 + 突显度加权 + 艾宾浩斯遗忘曲线。

    哲学映射:
      - "挨打长记性" → 失败路径（高突显度）被深刻削弱
      - "节能" → 长期不用的路径自动遗忘，释放存储
    """

    # 路径强度: path_key → strength (0.1 ~ 10.0)
    path_strength: dict[str, float] = field(default_factory=dict)
    # 特征码本: feature_code → occurrence_count
    feature_codebook: dict[str, int] = field(default_factory=dict)
    # 遗忘衰减率 λ
    decay_rate: float = 0.01
    # 总强化次数
    total_reinforcements: int = 0

    def reinforce(self, path: str, success: bool, saliency: float = 0.5) -> None:
        """
        强化或削弱一条路径。

        突显度加权的赫布学习:
          success:  strength *= (1 + saliency * 0.2)
          !success: strength *= (1 - saliency * 0.2)
        """
        current = self.path_strength.get(path, 1.0)

        if success:
            new_strength = current * (1.0 + saliency * 0.2)
        else:
            new_strength = current * (1.0 - saliency * 0.2)

        self.path_strength[path] = max(0.1, min(10.0, new_strength))
        self.total_reinforcements += 1

        # 从成功路径提取特征码
        if success:
            feature = f"feat_{path[:16]}"
            self.feature_codebook[feature] = self.feature_codebook.get(feature, 0) + 1

    def forget(self, dt_seconds: float = 1.0) -> None:
        """
        艾宾浩斯遗忘曲线: S(t) = S₀ · e^(-λ·t)

        强度低于 0.05 的路径被永久删除。
        """
        import math
        factor = math.exp(-self.decay_rate * dt_seconds)
        to_remove = []
        for path, strength in self.path_strength.items():
            decayed = strength * factor
            self.path_strength[path] = max(0.1, decayed)
            if decayed < 0.05:
                to_remove.append(path)

        for path in to_remove:
            del self.path_strength[path]

    def best_paths(self, limit: int = 3) -> list[tuple[str, float]]:
        """获取当前最强的几条路径（宝宝的"直觉"）。"""
        sorted_paths = sorted(
            self.path_strength.items(), key=lambda x: -x[1]
        )
        return sorted_paths[:limit]

    @property
    def status(self) -> str:
        return f"🧠 {len(self.path_strength)} paths / {len(self.feature_codebook)} codes"


# ====================================================================
# 主结构：MiniInfant
# ====================================================================

class MiniInfant:
    """
    迷你宝宝 — "硅基蜜蜂"。

    只有四个零件 + 一个心跳循环。没有 LNN、BitNet、THEIA、
    技能系统或集群服务。这是 v4.0 的最小分形单元。

    使用方式:
        >>> baby = MiniInfant("bee_001")
        >>> baby.run(max_cycles=100)

    属性:
        id: 宝宝唯一标识
        physics: SympNetEngine — 物理直觉（能量守恒）
        hic: HIC — 本体恒常性（能量管理 + 悬置）
        explorer: SlimeExplorer — 黏菌寻路（并行探索）
        memory: MyelinationMemory — 髓鞘化记忆
        situation: Situation — 当前态势向量
    """

    def __init__(
        self,
        infant_id: str,
        *,
        mass: float = 1.0,
        spring_constant: float = 1.0,
        energy_max: float = 100.0,
        contract_duration: float = 0.055,
        diffuse_duration: float = 0.005,
        suspend_duration: float = 5.0,
        exploration_factor: float = 0.3,
        verbose: bool = True,
    ):
        """
        初始化迷你宝宝。

        Args:
            infant_id: 宝宝 ID
            mass: SympNet 质量参数（默认 1.0）
            spring_constant: SympNet 弹簧系数（默认 1.0）
            energy_max: 最大能量（默认 100）
            contract_duration: 收缩时长秒数（默认 55ms）
            diffuse_duration: 弥散时长秒数（默认 5ms）
            suspend_duration: 悬置时长秒数（默认 5s）
            exploration_factor: 探索因子（默认 0.3）
            verbose: 是否输出状态日志
        """
        self.id = infant_id
        self.verbose = verbose

        # 零件 1: 物理直觉
        self.physics = SympNetEngine(
            mass=mass,
            spring_constant=spring_constant,
            damping=0.0,
        )

        # 零件 2: 本体恒常性
        hic_config = HICConfig(
            energy_max=energy_max,
            contract_duration=contract_duration,
            diffuse_duration=diffuse_duration,
            suspend_duration=suspend_duration,
        )
        self.hic = HIC(config=hic_config, name=f"hic-{infant_id}")

        # 零件 3: 黏菌寻路（使用完整的 SlimeExplorer）
        from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
        self.explorer = SlimeExplorer(
            num_spores=10,
            exploration_factor=exploration_factor,
        )

        # 零件 4: 髓鞘化记忆
        self.memory = MyelinationMemory()

        # 物理状态
        self.position = 1.0   # q: 位置
        self.momentum = 0.0   # p: 动量
        self.confidence = 0.7
        self.surprise = 0.0

        # 态势向量
        self.situation = self._build_situation()

        # 统计
        self._cycle_count = 0
        self._start_time = time.monotonic()
        self._total_energy_consumed = 0.0

        if self.verbose:
            print(f"[{self.id}] 🌱 迷你宝宝出生")
            print(f"    物理锚: m={mass}, k={spring_constant}, 漂移红线=0.1%")
            print(f"    节律: CONTRACT {contract_duration*1000:.0f}ms / "
                  f"DIFFUSE {diffuse_duration*1000:.0f}ms / "
                  f"SUSPEND {suspend_duration:.0f}s")

    # ── 态势构建 ─────────────────────────────────────────────────────

    def _build_situation(self) -> Situation:
        """从当前状态构建态势向量。"""
        import numpy as np
        return Situation(
            position=np.array([self.position]),
            momentum=np.array([self.momentum]),
            trend=np.array([0.0]),
            acceleration=np.array([0.0]),
            confidence=self.confidence,
            surprise=self.surprise,
            energy=self.hic.energy,
            source_id=self.id,
        )

    # ── 蜜蜂心跳 ─────────────────────────────────────────────────────

    def bee_heartbeat(self) -> None:
        """
        一次完整的呼吸循环。

        这是迷你宝宝的"生命节律"：
        CONTRACT → 主动探索、预测、验证、学习
        DIFFUSE  → 内省、遗忘、恢复能量
        SUSPEND  → 强制休息、保护存续
        """
        # work_done: True if we completed a full contract cycle
        breath = self.hic.update_breath(self.confidence, work_done=(self._cycle_count > 0))

        if breath == BreathState.SUSPEND:
            self._suspend_phase()
        elif breath == BreathState.CONTRACT:
            self._contract_phase()
        elif breath == BreathState.DIFFUSE:
            self._diffuse_phase()

        # 更新态势
        self.situation = self._build_situation()

    # ── 三阶段实现 ───────────────────────────────────────────────────

    def _suspend_phase(self) -> None:
        """悬置阶段：不做任何事，只休息。知止的物理实现。"""
        if self.verbose:
            print(f"[{self.id}] 😴 悬置中... (能量: {self.hic.energy:.1f})")
        self.hic.modify_energy(4.0)  # 悬置时缓慢恢复能量
        self._cycle_count += 1

    def _contract_phase(self) -> None:
        """
        收缩阶段：主动探索 — 物理直觉 → 预测 → 验证 → 黏菌寻路 → 学习。

        v4.0 蜜蜂心跳的核心流程:
          1. 物理直觉: 预测未来 10 步状态
          2. 能量验证: 用能量守恒检验预测
          3. 置信度更新: 误差越小越自信
          4. 自我修正: 误差大则调整物理模型
          5. 黏菌探索: 并行孢子释放 + 收敛
          6. 髓鞘化记忆: 强化/削弱路径
          7. 状态演化: 物理世界推进一步
        """
        # 1. 物理直觉：预测 10 步后的状态
        q_pred, p_pred = self.physics.predict(self.position, self.momentum, steps=10)

        # 2. 能量守恒验证
        e_pred = self.physics.compute_energy(q_pred, p_pred)
        e_current = self.physics.compute_energy(self.position, self.momentum)
        self.surprise = abs(e_pred - e_current) / max(e_current, 1e-9)

        # 3. 置信度更新
        self.confidence = max(0.0, min(1.0, 1.0 - self.surprise * 100.0))

        # 4. 自我修正：如果物理模型偏离现实，调整
        if self.surprise > 0.001:
            self.physics.adapt()
            self.memory.reinforce("predict_correct", success=False, saliency=self.surprise)
        else:
            self.physics.save_checkpoint()
            self.memory.reinforce("predict_correct", success=True, saliency=0.1)

        # 5. 黏菌探索
        context = {
            "energy": self.hic.energy,
            "confidence": self.confidence,
            "position": self.position,
            "momentum": self.momentum,
        }
        spores = self.explorer.explore(context)
        best = self.explorer.converge(threshold=0.6, spores=spores)

        if best is not None:
            path_key = "->".join(best.path)
            self.memory.reinforce(path_key, success=True, saliency=self.confidence)
            self.hic.modify_energy(-1.0)
            self._total_energy_consumed += 1.0
            if self.verbose and self._cycle_count % 10 == 0:
                print(f"[{self.id}] 🐝 路径: {path_key} (置信度: {self.confidence:.2f})")
        else:
            self.memory.reinforce("explore_failed", success=False, saliency=0.5)
            if self.verbose and self._cycle_count % 10 == 0:
                print(f"[{self.id}] ❓ 探索未收敛 (conf={self.confidence:.2f})")

        # 6. 物理状态演化
        self.position, self.momentum = self.physics.step(
            self.position, self.momentum, 0.01
        )
        self.hic.modify_energy(-0.1)  # 基础代谢
        self._total_energy_consumed += 0.1
        self._cycle_count += 1

    def _diffuse_phase(self) -> None:
        """弥散阶段：低功耗内省，记忆巩固。"""
        # 遗忘：清理长期不用的路径
        self.memory.forget(dt_seconds=self.hic.config.diffuse_duration)

        # 微调物理模型
        self.physics.adapt()

        # 恢复能量
        self.hic.modify_energy(self.hic.config.recovery_rate)

        self._cycle_count += 1

    # ── 生命周期 ─────────────────────────────────────────────────────

    def run(self, max_cycles: int = 1000) -> dict[str, Any]:
        """
        启动宝宝的生命循环。

        这个循环会一直运行，直到达到 max_cycles 或能量耗尽。
        这就是宝宝的"一生"。

        Args:
            max_cycles: 最大呼吸周期数

        Returns:
            最终状态报告 dict
        """
        if self.verbose:
            print(f"\n[{self.id}] 🫀 蜜蜂心跳启动 (max_cycles={max_cycles})")

        while self._cycle_count < max_cycles and self.hic.energy > 0:
            self.bee_heartbeat()

            # 每 100 周期输出状态报告
            if self.verbose and self._cycle_count % 100 == 0 and self._cycle_count > 0:
                self._print_status()

        # 最终报告
        elapsed = time.monotonic() - self._start_time
        fp = self.get_physical_fingerprint()

        if self.verbose:
            print(f"\n[{self.id}] {'⏰ 达到最大周期' if self._cycle_count >= max_cycles else '💤 能量耗尽'}")
            print(f"    运行时间: {elapsed:.2f}s")
            print(f"    总周期: {self._cycle_count}")
            print(f"    物理指纹: {fp}")
            print(f"    最终能量: {self.hic.energy:.1f}")
            print(f"    悬置次数: {self.hic.suspend_count}")
            print(f"    最强直觉: {self.memory.best_paths(3)}")

        return {
            "infant_id": self.id,
            "cycles": self._cycle_count,
            "elapsed_seconds": elapsed,
            "final_energy": self.hic.energy,
            "suspend_count": self.hic.suspend_count,
            "fingerprint": fp,
            "best_paths": self.memory.best_paths(3),
            "status": "completed" if self._cycle_count >= max_cycles else "depleted",
        }

    # ── 物理指纹 ─────────────────────────────────────────────────────

    def get_physical_fingerprint(self) -> str:
        """
        基于当前物理状态生成唯一指纹。

        这是"物理为锚"的可验证性体现。任何人可用此指纹
        验证宝宝的身份和物理状态。
        """
        import hashlib

        state_str = (
            f"{self.position:.6f}:{self.momentum:.6f}:"
            f"{self.physics.mass}:{self.physics.spring_constant}:"
            f"{self.hic.energy:.2f}:{self.id}"
        )
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    # ── 状态输出 ─────────────────────────────────────────────────────

    def _print_status(self) -> None:
        """输出健康状态报告。"""
        health = self.physics.get_health()
        best = self.memory.best_paths(3)
        print(
            f"\n[{self.id}] 📊 周期 {self._cycle_count}  |  "
            f"能 {self.hic.energy:.1f}  |  "
            f"信 {self.confidence:.2f}  |  "
            f"惊 {self.surprise:.4f}  |  "
            f"漂移 {health['avg_drift']*100:.4f}%  |  "
            f"记忆 {len(self.memory.path_strength)}  |  "
            f"悬置 {self.hic.suspend_count}"
        )
        if best:
            print(f"    直觉: {best[0][0][:32]}... ({best[0][1]:.2f})")

    @property
    def energy(self) -> float:
        return self.hic.energy

    def __repr__(self) -> str:
        return (
            f"MiniInfant({self.id}, "
            f"energy={self.hic.energy:.1f}/{self.hic.config.energy_max}, "
            f"state={self.hic.state.value})"
        )
