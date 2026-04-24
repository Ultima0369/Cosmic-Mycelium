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
from typing import Any, ClassVar

from cosmic_mycelium.common.fractal import Scale
from cosmic_mycelium.common.situation import Situation
from cosmic_mycelium.infant.breath_bus import BreathAware
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.fossil import FossilLayer, FossilRecord
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
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

    创伤回路: 高强度记忆被永久标记，遗忘曲线逆转为强化曲线。

    哲学映射:
      - "挨打长记性" → 失败路径（高突显度）被深刻削弱
      - "节能" → 长期不用的路径自动遗忘，释放存储
      - "疤痕永不消" → 创伤路径随时间反而加深
    """

    # 路径强度: path_key → strength (0.1 ~ 10.0)
    path_strength: dict[str, float] = field(default_factory=dict)
    # 特征码本: feature_code → occurrence_count
    feature_codebook: dict[str, int] = field(default_factory=dict)
    # 遗忘衰减率 λ
    decay_rate: float = 0.01
    # 总强化次数
    total_reinforcements: int = 0
    # 创伤回路
    trauma_paths: dict[str, dict] = field(default_factory=dict)
    repression_potential: float = 0.0
    # 类常量
    REPRESSION_THRESHOLD: ClassVar[float] = 10.0

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

        创伤覆写: 标记为创伤的路径使用逆遗忘 —— 随时间反而加深。
        """
        import math

        to_remove = []
        for path, strength in self.path_strength.items():
            if path in self.trauma_paths:
                # 逆遗忘: 创伤随时间加深
                boost = 1.0 + self.decay_rate * dt_seconds
                boosted = strength * boost
                self.path_strength[path] = min(10.0, boosted)
            else:
                decayed = strength * math.exp(-self.decay_rate * dt_seconds)
                self.path_strength[path] = max(0.1, decayed)
                if decayed < 0.05:
                    to_remove.append(path)

        for path in to_remove:
            del self.path_strength[path]
            # Don't remove from trauma_paths — trauma is permanent

    def best_paths(self, limit: int = 3) -> list[tuple[str, float]]:
        """获取当前最强的几条路径（宝宝的"直觉"）。"""
        sorted_paths = sorted(
            self.path_strength.items(), key=lambda x: -x[1]
        )
        return sorted_paths[:limit]

    # ── 死亡与继承 ───────────────────────────────────────────────────

    def compile_will(self, top_n: int = 10) -> dict[str, float]:
        """
        编译"遗嘱"：打包最重要的 N 条高突显度记忆。

        节点死前调用此方法，将一生中最重要的记忆打包，
        发送给曾与之共振的关联节点。

        Returns:
            {path: strength} 映射
        """
        sorted_paths = sorted(
            self.path_strength.items(), key=lambda x: -x[1]
        )
        return dict(sorted_paths[:top_n])

    def inherit_will(self, will: dict[str, float], boost: float = 0.3) -> int:
        """
        继承另一个节点（已死亡）的遗嘱记忆。

        继承的记忆以衰减后的强度注入当前记忆池。
        系统通过这种方式跨越"死亡鸿沟"传递经验。

        Args:
            will: 遗嘱 {path: strength}
            boost: 继承强度衰减系数 (默认 0.3)

        Returns:
            成功继承的记忆数量
        """
        count = 0
        for path, strength in will.items():
            inherited = strength * boost
            current = self.path_strength.get(path, 0.0)
            self.path_strength[path] = max(current, inherited)
            count += 1
        return count

    # ── 创伤回路 ─────────────────────────────────────────────────────

    def mark_trauma(self, path_key: str, context: str = "") -> None:
        """标记一条路径为创伤。"""
        if path_key not in self.trauma_paths:
            self.trauma_paths[path_key] = {
                "timestamp": __import__("time").time(),
                "context": context,
                "repression_count": 0,
                "flashback_count": 0,
            }
            # Trauma paths start strong
            current = self.path_strength.get(path_key, 1.0)
            self.path_strength[path_key] = max(current, 5.0)

    def accumulate_repression(self, path_str: str) -> float:
        """增加压抑势能。"""
        if path_str in self.trauma_paths:
            self.trauma_paths[path_str]["repression_count"] += 1
        self.repression_potential += 0.5
        return self.repression_potential

    def check_flashback_trigger(self) -> list[dict]:
        """检查压抑势能是否达到闪回阈值。"""
        triggers = []
        for path_str, info in list(self.trauma_paths.items()):
            if info.get("repression_count", 0) >= 10:
                triggers.append({
                    "path": path_str,
                    "context": info.get("context", ""),
                    "repression_count": info["repression_count"],
                })
                self.trauma_paths[path_str]["repression_count"] = 0
                self.trauma_paths[path_str]["flashback_count"] += 1
                # Flashback re-traumatizes: boost strength
                if path_str in self.path_strength:
                    self.path_strength[path_str] = min(10.0, self.path_strength[path_str] * 1.2)

        if triggers:
            self.repression_potential = max(
                0.0, self.repression_potential - len(triggers) * 3.0
            )

        return triggers

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
        fractal_bus: FractalDialogueBus | None = None,
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
        self.fractal_bus = fractal_bus

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

        # 零件 4: 髓鞘化记忆
        self.memory = MyelinationMemory()

        # 化石层（跨死亡周期的经验存储）
        self._fossil_layer: FossilLayer = FossilLayer()
        self._extinction_counter: int = 0  # 灭绝事件计数器

        # 零件 3 改造：使用完整的 SlimeExplorer + 创伤感知
        from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
        self.explorer = SlimeExplorer(
            num_spores=10,
            exploration_factor=exploration_factor,
            trauma_memory=self.memory,  # 注入创伤记忆
            fractal_bus=self.fractal_bus,  # 注入群体智慧
        )
        self.explorer._source_id = self.id  # 路径共享时标识来源

        # 物理状态
        self.position = 1.0   # q: 位置
        self.momentum = 0.0   # p: 动量
        self.confidence = 0.7
        self.surprise = 0.0

        # 态势向量 (before: _prev_confidence for trauma detection)
        self._prev_confidence = 0.7
        self.situation = self._build_situation()

        # 统计与生命周期
        self._cycle_count = 0
        self._start_time = time.monotonic()
        self._total_energy_consumed = 0.0
        self._hidden_energy_reserve: float = 20.0  # 隐性能量储备（死亡阈值）
        self._synergy_score: float = 0.5            # 协同度 [0, 1]
        self._age: int = 0                          # 当前年龄
        self._max_age: int = 10000                  # 最大寿命（周期数）
        self._is_dead: bool = False                 # 死亡标记
        self._will_package: dict[str, float] | None = None  # 遗嘱记忆包

        if self.verbose:
            print(f"[{self.id}] 🌱 迷你宝宝出生")
            print(f"    物理锚: m={mass}, k={spring_constant}, 漂移红线=0.1%")
            print(f"    节律: CONTRACT {contract_duration*1000:.0f}ms / "
                  f"DIFFUSE {diffuse_duration*1000:.0f}ms / "
                  f"SUSPEND {suspend_duration:.0f}s")

    # ── 状态查询 ─────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        """当前状态: 'alive' | 'dead' | 'suspended'。"""
        if self._is_dead:
            return "dead"
        if hasattr(self.hic, 'breath_state') and self.hic.breath_state == BreathState.SUSPEND:
            return "suspended"
        return "alive"

    # ── 态势构建 ─────────────────────────────────────────────────────

    def _build_situation(self) -> Situation:
        """从当前状态构建态势向量，包含共振烈度和创伤标记。"""
        import numpy as np

        # 共振烈度：从惊讶度和置信度变化推导
        # 高惊讶 + 低置信 = 高烈度（可能是创伤性事件）
        surprise_factor = min(1.0, self.surprise * 50.0)
        confidence_drop = max(0.0, self._prev_confidence - self.confidence)
        resonance_intensity = min(1.0, surprise_factor * 0.6 + confidence_drop * 2.0)

        return Situation(
            position=np.array([self.position]),
            momentum=np.array([self.momentum]),
            trend=np.array([0.0]),
            acceleration=np.array([0.0]),
            confidence=self.confidence,
            surprise=self.surprise,
            energy=self.hic.energy,
            resonance_intensity=resonance_intensity,
            source_id=self.id,
        )

    # ── 分形网络发布 ──────────────────────────────────────────────────

    def _publish_trauma_to_fractal(self) -> None:
        """创伤事件 → INFANT→MESH 分形发布。个体痛苦成为群体的经验。"""
        if self.fractal_bus is None:
            return
        try:
            # 先在 INFANT 层级记录（与本地的呼吸信号呼应）
            self.fractal_bus.echo_detector.record(
                signature="critical_state",
                scale=Scale.INFANT,
                metadata={"event_type": "trauma", "source": self.id},
            )
            self.fractal_bus.publish_trauma(
                situation_data={
                    "energy": self.hic.energy,
                    "confidence": self.confidence,
                    "surprise": self.surprise,
                    "resonance_intensity": self.situation.resonance_intensity,
                    "confidence_drop": max(0.0, self._prev_confidence - self.confidence),
                },
                source_id=self.id,
            )
            if self.verbose:
                print(f"[{self.id}] 📡 创伤信号发布到 MESH")
        except Exception as e:
            logger.warning("[%s] 发布创伤失败: %s", self.id, e)

    def _publish_death_to_fractal(self) -> None:
        """死亡事件 → INFANT→MESH 分形发布。牺牲成为文明的记忆。"""
        if self.fractal_bus is None:
            return
        try:
            cause = (
                "reserve_depleted" if self._hidden_energy_reserve <= 0
                else "old_age" if self._age >= self._max_age
                else "energy_depleted" if self.hic.energy <= 0
                else "unknown"
            )
            self.fractal_bus.publish_death(
                death_data={
                    "cause": cause,
                    "lifespan_cycles": self._cycle_count,
                    "synergy_score": self._synergy_score,
                    "hidden_reserve": self._hidden_energy_reserve,
                    "final_energy": self.hic.energy,
                    "memories_count": len(self.memory.path_strength),
                },
                source_id=self.id,
            )
            if self.verbose:
                print(f"[{self.id}] 📡 死亡信号发布到 MESH")
        except Exception as e:
            logger.warning("[%s] 发布死亡失败: %s", self.id, e)

    def _query_collective_wisdom(self) -> dict[str, Any]:
        """查询群体智慧（MESH 回响），返回可能影响决策的集体经验。"""
        if self.fractal_bus is None:
            return {}
        try:
            return self.fractal_bus.get_collective_wisdom()
        except Exception as e:
            logger.warning("[%s] 查询群体智慧失败: %s", self.id, e)
            return {}

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
        收缩阶段：主动探索 — 物理直觉 → 预测 → 验证 → 置信度 → 创伤检测 → 黏菌寻路 → 学习。

        v4.0 蜜蜂心跳的核心流程:
          1. 物理直觉: 预测未来 10 步状态
          2. 能量验证: 用能量守恒检验预测
          3. 置信度更新: 误差越小越自信
          4. 创伤检测: 共振烈度 > 0.97 + 置信度骤降 → 标记创伤
          5. 自我修正: 误差大则调整物理模型
          6. 黏菌探索: 并行孢子释放 + 收敛 + 闪回避让
          7. 髓鞘化记忆: 强化/削弱路径 + 创伤固化
          8. 状态演化: 物理世界推进一步
        """
        # 1. 物理直觉：预测 10 步后的状态
        q_pred, p_pred = self.physics.predict(self.position, self.momentum, steps=10)

        # 2. 能量守恒验证
        e_pred = self.physics.compute_energy(q_pred, p_pred)
        e_current = self.physics.compute_energy(self.position, self.momentum)
        self.surprise = abs(e_pred - e_current) / max(e_current, 1e-9)

        # 3. 置信度更新（先保存旧值用于创伤检测）
        old_confidence = self._prev_confidence
        self.confidence = max(0.0, min(1.0, 1.0 - self.surprise * 100.0))

        # 4. 创伤检测：共振烈度 > 0.97 且置信度骤降
        confidence_crash = (old_confidence - self.confidence) > 0.2
        surprise_spike = self.surprise > 0.01  # 1% 以上能量漂移
        if surprise_spike and confidence_crash:
            trauma_path = "->".join([
                f"q_{self.position:.2f}",
                f"p_{self.momentum:.2f}",
                f"surprise_{self.surprise:.4f}",
            ])
            self.memory.mark_trauma(
                trauma_path,
                context=(
                    f"能量漂移 {self.surprise*100:.2f}%，"
                    f"置信度 {old_confidence:.2f}→{self.confidence:.2f}"
                ),
            )
            if self.verbose:
                print(f"[{self.id}] ⚠️ 创伤标记: {trauma_path[:48]}...")
            # 接线一：创伤 → 分形回声
            self._publish_trauma_to_fractal()

        # 5. 自我修正：如果物理模型偏离现实，调整
        if self.surprise > 0.001:
            self.physics.adapt()
            saliency = min(2.0, self.surprise * 100)  # 惊讶度越高，突显度越高
            self.memory.reinforce("predict_correct", success=False, saliency=saliency)
        else:
            self.physics.save_checkpoint()
            self.memory.reinforce("predict_correct", success=True, saliency=0.1)

        # 6. 黏菌探索（集成创伤回避 + 闪回）
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

        # 8. 物理状态演化
        self.position, self.momentum = self.physics.step(
            self.position, self.momentum, 0.01
        )
        self.hic.modify_energy(-0.1)  # 基础代谢
        self._total_energy_consumed += 0.1

        # 更新上一周期置信度（用于下一周期的创伤检测）
        self._prev_confidence = self.confidence
        self._cycle_count += 1

    def _diffuse_phase(self) -> None:
        """弥散阶段：低功耗内省，记忆巩固，群体智慧感知。"""
        # 遗忘：清理长期不用的路径
        self.memory.forget(dt_seconds=self.hic.config.diffuse_duration)

        # 微调物理模型
        self.physics.adapt()

        # 接线三：群体智慧 → 个体直觉（"品一品集体的氛围"）
        if self.fractal_bus is not None:
            # 先分享自己的态势到 MESH（日常交流，非仅创伤/死亡）
            try:
                self.fractal_bus.publish_situation_update(
                    situation_data={
                        "energy": self.hic.energy,
                        "confidence": self.confidence,
                        "timestamp": self.situation.timestamp,
                        "source_id": self.id,
                    },
                    source_id=self.id,
                )
            except Exception:
                pass

            # 查询集体创伤记忆
            wisdom = self._query_collective_wisdom()
            if wisdom.get("collective_trauma_count", 0) > 0:
                self.confidence = max(0.1, self.confidence - 0.01)

            # 查询集体态势（群体能量/置信度趋势）
            try:
                collective = self.fractal_bus.get_collective_situation()
                if collective.get("collective_tension", 0) > 0.5:
                    # 群体整体紧张 → 更保守（节能）
                    self.hic.modify_energy(-2.0)  # 紧张氛围消耗额外能量
                if collective.get("collective_tension", 0) < 0.1:
                    # 群体整体放松 → 微幅提升信心
                    self.confidence = min(0.9, self.confidence + 0.005)
            except Exception:
                pass

        # 恢复能量
        self.hic.modify_energy(self.hic.config.recovery_rate)

        self._cycle_count += 1

    # ── 生命周期 ─────────────────────────────────────────────────────

    def run(self, max_cycles: int = 1000) -> dict[str, Any]:
        """
        启动宝宝的生命循环。

        这个循环会一直运行，直到达到 max_cycles、能量耗尽或寿终正寝。
        这就是宝宝的"一生"。

        死亡与继承:
          - 隐性储备耗尽 = 死亡
          - 超过最大年龄 = 死亡
          - 死亡时编译遗嘱，将记忆打包给后继者
          - 化石层记录核心经验，供后代"考古"

        Args:
            max_cycles: 最大呼吸周期数

        Returns:
            最终状态报告 dict
        """
        if self.verbose:
            print(f"\n[{self.id}] 🫀 蜜蜂心跳启动 (max_cycles={max_cycles})")

        while (self._cycle_count < max_cycles and self.hic.energy > 0
               and not self._is_dead):
            self.bee_heartbeat()

            # 每周期检查生命力
            self._check_vitality()

            # 每 100 周期输出状态报告
            if self.verbose and self._cycle_count % 100 == 0 and self._cycle_count > 0:
                self._print_status()

            # 每 1000 周期检查灭绝事件
            if self._cycle_count > 0 and self._cycle_count % 1000 == 0:
                self._extinction_counter += 1
                if self._synergy_score < 0.2:
                    if self.verbose:
                        print(f"[{self.id}] ☠️  低协同 ({self._synergy_score:.2f})，逼近灭绝线")

        # 死亡处理
        if self._is_dead or self.hic.energy <= 0:
            return self._die()

        # 正常结束
        elapsed = time.monotonic() - self._start_time
        fp = self.get_physical_fingerprint()

        if self.verbose:
            print(f"\n[{self.id}] ⏰ 达到最大周期")
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
            "hidden_reserve": self._hidden_energy_reserve,
            "synergy_score": self._synergy_score,
            "age": self._age,
            "status": "completed",
        }

    # ── 死亡与继承 ───────────────────────────────────────────────────

    def _check_vitality(self) -> None:
        """
        每周期检查生命体征。

        隐性储备消耗规则:
          - 能量低 (<20) 且 协同度低 (<0.3): 储备每日消耗加速
          - 协同度高 (>0.7): 储备缓慢恢复
          - 储备归零 → 死亡

        年龄检查:
          - 超过最大年龄 → 死亡（自然寿命终结）
        """
        self._age = self._cycle_count

        # 更新协同度（基于探索器收敛质量）
        if self.explorer.success_history:
            recent = self.explorer.success_history[-10:]
            avg_quality = sum(s["quality"] for s in recent) / len(recent)
            self._synergy_score = self._synergy_score * 0.9 + avg_quality * 0.1

        # 隐性储备消耗
        if self.hic.energy < 20.0 and self._synergy_score < 0.3:
            drain = 0.05 * (1.0 - self._synergy_score)
            self._hidden_energy_reserve -= drain
        elif self._synergy_score > 0.7 and self.hic.energy > 50.0:
            self._hidden_energy_reserve = min(20.0, self._hidden_energy_reserve + 0.01)

        # 死亡判定
        if self._hidden_energy_reserve <= 0.0:
            self._is_dead = True
            if self.verbose:
                print(f"[{self.id}] 💀 隐性储备耗尽 — 寿终正寝")

        if self._age >= self._max_age:
            self._is_dead = True
            if self.verbose:
                print(f"[{self.id}] ⌛ 达到最大年龄 {self._max_age} — 自然死亡")

    def _die(self) -> dict[str, Any]:
        """
        执行死亡流程。

        1. 编译遗嘱：打包最重要的记忆
        2. 埋葬：将核心记忆写入化石层
        3. 返回最终状态报告

        Returns:
            死亡状态报告
        """
        elapsed = time.monotonic() - self._start_time
        fp = self.get_physical_fingerprint()

        # 1. 编译遗嘱
        self._will_package = self.memory.compile_will(top_n=10)

        # 2. 埋葬到化石层
        fossil = FossilRecord(
            node_id=self.id,
            death_timestamp=time.time(),
            lifespan_cycles=self._cycle_count,
            epitaph=(
                f"能量={self.hic.energy:.1f}, "
                f"置信度={self.confidence:.2f}, "
                f"协同度={self._synergy_score:.2f}, "
                f"记忆={len(self.memory.path_strength)}条"
            ),
            core_memories=self._will_package,
            final_situation={
                "energy": self.hic.energy,
                "confidence": self.confidence,
                "surprise": self.surprise,
                "position": self.position,
                "momentum": self.momentum,
            },
        )
        self._fossil_layer.bury(fossil)

        # 接线二：死亡 → 分形信号（牺牲成为文明的记忆）
        self._publish_death_to_fractal()

        if self.verbose:
            print(f"\n[{self.id}] 💀 死亡报告")
            print(f"    寿命: {self._cycle_count} 周期 ({elapsed:.2f}s)")
            print(f"    物理指纹: {fp}")
            print(f"    最终能量: {self.hic.energy:.1f}")
            print(f"    协同度: {self._synergy_score:.2f}")
            print(f"    化石已埋葬 (记忆: {len(fossil.core_memories)}条)")

        # 尝试从化石层重生
        rebirth_evidence = None
        fossils = self._fossil_layer.excavate(sort_by="legacy_count")
        if len(fossils) > 0 and fossils[0].node_id != self.id:
            rebirth_evidence = {
                "ancestor": fossils[0].node_id,
                "inherited_memories": len(fossils[0].core_memories),
            }

        return {
            "infant_id": self.id,
            "cycles": self._cycle_count,
            "elapsed_seconds": elapsed,
            "final_energy": self.hic.energy,
            "suspend_count": self.hic.suspend_count,
            "fingerprint": fp,
            "will_package_size": len(self._will_package),
            "fossil_buried": True,
            "rebirth_evidence": rebirth_evidence,
            "hidden_reserve": self._hidden_energy_reserve,
            "synergy_score": self._synergy_score,
            "age": self._age,
            "status": "dead",
        }

    def _rebirth(self, ancestor_id: str | None = None) -> bool:
        """
        从化石层重生，继承先辈的记忆。

        在 DIFFUSE 期内省时调用，新节点可以"考古"化石层，
        继承被埋葬节点的核心经验。

        Args:
            ancestor_id: 指定继承的祖先 (None = 挖掘最有价值的化石)

        Returns:
            是否成功继承记忆
        """
        if ancestor_id:
            fossil = self._fossil_layer.dig(ancestor_id)
        else:
            fossils = self._fossil_layer.excavate(sort_by="legacy_count")
            fossil = fossils[0] if fossils else None

        if fossil is None:
            return False

        count = self.memory.inherit_will(fossil.core_memories)

        if self.verbose:
            print(f"[{self.id}] 🔄 从 {fossil.node_id} 的化石中继承 {count} 条记忆")

        return count > 0

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
        """输出健康状态报告，包含寿命和协同度。"""
        health = self.physics.get_health()
        best = self.memory.best_paths(3)
        fossil_count = len(self._fossil_layer._records) if self._fossil_layer else 0
        print(
            f"\n[{self.id}] 📊 周期 {self._cycle_count}  |  "
            f"能 {self.hic.energy:.1f}  |  "
            f"信 {self.confidence:.2f}  |  "
            f"惊 {self.surprise:.4f}  |  "
            f"漂移 {health['avg_drift']*100:.4f}%  |  "
            f"记忆 {len(self.memory.path_strength)}  |  "
            f"协同 {self._synergy_score:.2f}  |  "
            f"储备 {self._hidden_energy_reserve:.1f}  |  "
            f"悬置 {self.hic.suspend_count}  |  "
            f"化石 {fossil_count}"
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
