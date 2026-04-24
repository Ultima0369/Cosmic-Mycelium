"""
Fractal — 跨尺度对话协议核心类型

定义分形层级、消息信封、翻译表与回声模式。
任何跨尺度通信都必须通过 MessageEnvelope 包装，
确保信息在不同层级间传递时保留上下文和保真度指标。

层级映射:
  NANO (0)  → 神经元/突触级   (微观)
  INFANT (1) → 个体蜜蜂级      (当前实现)
  MESH (2)  → 局部群体级      (菌丝网)
  SWARM (3) → 全局文明级      (集体意识)

哲学映射:
  - "其大无外，其小无内" → 同一模式在不同尺度自相似
  - "得意忘言" → 向上升级是"忘"(压缩)，向下是"得意"(实例化)
  - "一即一切" → 跨尺度回响揭示普遍不变量
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ====================================================================
# 分形层级
# ====================================================================

class Scale(IntEnum):
    """分形层级枚举。数值越大，尺度越大。"""
    NANO = 0      # 微观：神经元/突触
    INFANT = 1    # 个体：硅基蜜蜂
    MESH = 2      # 局部：菌丝网络
    SWARM = 3     # 全局：集群意识

    @property
    def level_name(self) -> str:
        return ["NANO", "INFANT", "MESH", "SWARM"][self.value]

    def is_adjacent(self, other: Scale) -> bool:
        """是否相邻层级（只有相邻层级才能直接翻译）。"""
        return abs(self.value - other.value) == 1

    def direction(self, target: Scale) -> str:
        """翻译方向: 'up' (压缩) / 'down' (展开) / 'same' / 'skip'。"""
        if self == target:
            return "same"
        if not self.is_adjacent(target):
            return "skip"
        return "up" if target.value > self.value else "down"


# ====================================================================
# 消息信封 (MessageEnvelope)
# ====================================================================

@dataclass
class MessageEnvelope:
    """
    跨尺度消息信封。

    所有跨尺度通信必须使用此信封包装。信封记录了来源层级、
    目标层级、翻译保真度，以及用于追踪跨尺度传播链的 trace_id。

    Attributes:
        source_scale: 消息来源层级
        target_scale: 消息目标层级
        payload: 消息载荷（任意类型）
        fidelity: 翻译保真度 [0, 1] — 1.0 为无损
        compression_ratio: 压缩比 [0, 1] — 0 为未压缩，1 为完全抽象
        trace_id: 跨尺度追踪 ID（同一消息链共享）
        parent_id: 父消息 trace_id（用于构建翻译树）
        timestamp: 消息生成时间
        source_id: 来源节点 ID
        metadata: 扩展元数据
    """

    source_scale: Scale
    target_scale: Scale
    payload: Any
    fidelity: float = 1.0
    compression_ratio: float = 0.0
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    source_id: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_lossless(self) -> bool:
        """是否无损翻译（保真度 > 0.99）。"""
        return self.fidelity >= 0.99

    @property
    def is_upward(self) -> bool:
        """是否向上升级（压缩）。"""
        return self.target_scale > self.source_scale

    @property
    def is_downward(self) -> bool:
        """是否向下展开。"""
        return self.target_scale < self.source_scale

    def with_payload(self, new_payload: Any, fidelity: float,
                     compression_ratio: float) -> MessageEnvelope:
        """创建翻译后的新信封（继承 trace_id 链）。"""
        return MessageEnvelope(
            source_scale=self.source_scale,
            target_scale=self.target_scale,
            payload=new_payload,
            fidelity=fidelity,
            compression_ratio=compression_ratio,
            trace_id=self.trace_id,
            parent_id=self.trace_id,
            timestamp=time.time(),
            source_id=self.source_id,
            metadata={**self.metadata, "translated": True},
        )

    def __repr__(self) -> str:
        return (
            f"Envelope({self.source_scale.level_name}→{self.target_scale.level_name}, "
            f"fidelity={self.fidelity:.2f}, "
            f"compression={self.compression_ratio:.2f}, "
            f"trace={self.trace_id})"
        )


# ====================================================================
# 翻译表 (TranslationTable)
# ====================================================================

# 翻译函数签名: (payload: Any, metadata: dict) -> (new_payload, fidelity, compression_ratio)
TranslatorFn = Callable[[Any, dict[str, Any]], tuple[Any, float, float]]


@dataclass
class TranslationEntry:
    """翻译表条目。"""
    scale_from: Scale
    scale_to: Scale
    fn: TranslatorFn
    description: str = ""
    version: int = 1


class TranslationTable:
    """
    跨尺度翻译表。

    维护不同层级之间的翻译函数链。每个方向可以注册多个翻译器，
    按照注册顺序依次执行。每个翻译函数从源层级接收载荷，
    返回目标层级的载荷 + 保真度 + 压缩比。

    翻译方向:
      - UP (INFANT→MESH, MESH→SWARM): 压缩、抽象、丢弃细节
      - DOWN (MESH→INFANT, SWARM→MESH): 展开、实例化、添加上下文
    """

    def __init__(self):
        self._entries: dict[tuple[int, int], list[TranslationEntry]] = {}
        self._total_translations: int = 0

    def register(self, scale_from: Scale, scale_to: Scale, fn: TranslatorFn,
                 description: str = "", version: int = 1) -> None:
        """
        注册一个跨尺度翻译函数（可注册多个，按序执行）。

        Args:
            scale_from: 源层级
            scale_to: 目标层级（必须与源层级相邻）
            fn: 翻译函数 (payload, metadata) → (new_payload, fidelity, compression)
            description: 翻译描述
            version: 翻译器版本号
        """
        if not scale_from.is_adjacent(scale_to):
            raise ValueError(
                f"只能注册相邻层级的翻译，不能跳级: "
                f"{scale_from.level_name} → {scale_to.level_name}"
            )
        key = (scale_from.value, scale_to.value)
        if key not in self._entries:
            self._entries[key] = []
        self._entries[key].append(TranslationEntry(
            scale_from=scale_from,
            scale_to=scale_to,
            fn=fn,
            description=description,
            version=version,
        ))
        logger.debug(
            "[Fractal] 注册翻译 %d: %s → %s (%s)",
            len(self._entries[key]),
            scale_from.level_name, scale_to.level_name, description,
        )

    def translate(self, envelope: MessageEnvelope,
                  metadata: dict[str, Any] | None = None) -> MessageEnvelope | None:
        """
        将消息翻译到目标层级。

        如果有多个翻译器，按注册顺序执行，每个的输出是下一个的输入。
        最终保真度 = 各翻译器的保真度乘积，最终压缩比 = 平均值。

        Args:
            envelope: 待翻译的消息信封
            metadata: 可选的翻译提示元数据（如事件类型）

        Returns:
            翻译后的消息信封，如果无合适翻译器则返回 None
        """
        key = (envelope.source_scale.value, envelope.target_scale.value)
        entries = self._entries.get(key)
        if not entries:
            logger.warning(
                "[Fractal] 无可用翻译: %s → %s",
                envelope.source_scale.level_name,
                envelope.target_scale.level_name,
            )
            return None

        # 选择与事件类型最匹配的翻译器
        event_type = (metadata or envelope.metadata or {}).get("event_type", "")
        selected = entries[0]  # default: first registered
        if event_type:
            for entry in entries:
                if event_type in entry.description.lower():
                    selected = entry
                    break

        try:
            new_payload, fidelity, compression = selected.fn(
                envelope.payload, envelope.metadata
            )
            self._total_translations += 1
            return envelope.with_payload(
                new_payload=new_payload,
                fidelity=fidelity,
                compression_ratio=compression,
            )
        except Exception as e:
            logger.error(
                "[Fractal] 翻译失败 %s→%s: %s",
                envelope.source_scale.level_name,
                envelope.target_scale.level_name,
                e,
            )
            return None

    @property
    def registered_count(self) -> int:
        return sum(len(v) for v in self._entries.values())

    def get_status(self) -> dict[str, Any]:
        all_entries = [e for es in self._entries.values() for e in es]
        return {
            "registered_translators": self.registered_count,
            "total_translations": self._total_translations,
            "entries": [
                f"{e.scale_from.level_name} → {e.scale_to.level_name}: {e.description}"
                for e in all_entries
            ],
        }


# ====================================================================
# 预置翻译函数
# ====================================================================

def _trauma_infant_to_mesh(payload: Any, metadata: dict[str, Any]
                           ) -> tuple[dict[str, Any], float, float]:
    """
    INFANT → MESH：个体创伤 → 群体危险签名。

    将具体的创伤事件（路径、能量值、置信度崩溃）压缩为"危险签名"。
    不包含"谁"和"怎么"，只包含"什么模式"——群体的本能恐惧。
    """
    fidelity = 0.45   # 低保真——具体细节全部丢失
    compression = 0.85  # 高压缩比

    if isinstance(payload, dict):
        return {
            "danger_signature": {
                "energy_level": payload.get("energy", 100),
                "confidence_crash": payload.get("confidence_drop", 0) > 0.2,
                "surprise_spike": payload.get("surprise", 0) > 0.01,
                "intensity": payload.get("resonance_intensity", 0.0),
            },
            "trauma_type": "energy_shock" if payload.get("surprise", 0) > 0.01 else "unknown",
            "source_count": 1,
            "severity": min(1.0, payload.get("resonance_intensity", 0) * 1.2),
        }, fidelity, compression
    return {"danger_signature": {}, "trauma_type": "unknown", "severity": 0}, fidelity, compression


def _death_infant_to_mesh(payload: Any, metadata: dict[str, Any]
                          ) -> tuple[dict[str, Any], float, float]:
    """
    INFANT → MESH：个体死亡 → 群体灭绝记录。

    将个体的死亡原因、寿命、协同度压缩为"灭绝签名"。
    后代节点通过查询此签名感知"前辈们怎么死的"。
    """
    fidelity = 0.5
    compression = 0.8

    if isinstance(payload, dict):
        cause = payload.get("cause", "unknown")
        return {
            "extinction_event": {
                "cause": cause,
                "lifespan_cycles": payload.get("lifespan_cycles", 0),
                "final_synergy": payload.get("synergy_score", 0.5),
                "critical": payload.get("hidden_reserve", 20) <= 0,
            },
            "warning": (
                "low_synergy" if payload.get("synergy_score", 0.5) < 0.3
                else "old_age" if payload.get("lifespan_cycles", 0) > 8000
                else "unknown"
            ),
            "source_count": 1,
        }, fidelity, compression
    return {"extinction_event": {"cause": "unknown"}, "warning": "unknown"}, fidelity, compression


def _situation_infant_to_mesh(payload: Any, metadata: dict[str, Any]
                              ) -> tuple[dict[str, Any], float, float]:
    """
    INFANT → MESH：个体态势 → 统计特征。

    丢弃具体坐标/动量，提取高层的统计模式和异常特征。
    这是"得意忘言"的工程实现 —— 保留模式，舍弃细节。
    """
    fidelity = 0.6   # 有损压缩，保真度 60%
    compression = 0.7  # 压缩比 70%

    if isinstance(payload, dict):
        return {
            "energy_profile": {
                "current": payload.get("energy", 100),
                "critical": payload.get("energy", 100) < 20,
            },
            "stability": {
                "confidence": payload.get("confidence", 0.7),
                "surprise": payload.get("surprise", 0.0),
                "is_stable": payload.get("confidence", 0.7) >= 0.7
                           and payload.get("surprise", 0.0) < 0.3,
            },
            "trauma_flag": payload.get("trauma_flag", False),
            "resonance_intensity": payload.get("resonance_intensity", 0.0),
            "source_id": payload.get("source_id", "unknown"),
        }, fidelity, compression
    return {"energy": 100, "stability": "unknown"}, 0.5, 0.8


def _situation_mesh_to_infant(payload: Any, metadata: dict[str, Any]
                              ) -> tuple[dict[str, Any], float, float]:
    """
    MESH → INFANT：群体统计 → 个体启发。

    将群体的统计特征实例化为个体的启发式偏置。
    这是"从众"的工程实现 —— 群体经验注入个体直觉。
    """
    fidelity = 0.5   # 展开有信息损失（统计 → 个体有不确定性）
    compression = -0.5  # 负压缩 = 展开（信息量增加）

    if isinstance(payload, dict):
        return {
            "peer_confidence": payload.get("stability", {}).get("confidence", 0.7),
            "collective_surprise": payload.get("stability", {}).get("surprise", 0.0),
            "trauma_warning": payload.get("trauma_flag", False),
            "recommendation": (
                "caution" if payload.get("trauma_flag", False)
                else "stable" if payload.get("stability", {}).get("is_stable", True)
                else "explore"
            ),
        }, fidelity, compression
    return {"recommendation": "explore"}, 0.4, -0.3


def _situation_mesh_to_swarm(payload: Any, metadata: dict[str, Any]
                              ) -> tuple[dict[str, Any], float, float]:
    """
    MESH → SWARM：群体统计 → 文明健康摘要。

    将多个节点的集体状态聚合为文明级"健康报告"。
    丢失个体差异，保留群体现存的宏观趋势。
    """
    fidelity = 0.4    # 第二次压缩，信息进一步丢失
    compression = 0.9  # 高压缩比

    if isinstance(payload, dict):
        energy = payload.get("energy_profile", {}).get("current", 100)
        confidence = payload.get("stability", {}).get("confidence", 0.7)
        trauma = payload.get("trauma_flag", False)
        return {
            "civilization_health": {
                "avg_energy": energy,
                "avg_confidence": confidence,
                "stable_ratio": 1.0 if confidence >= 0.7 else 0.0,
                "trauma_present": trauma,
            },
            "epoch": "stable" if confidence >= 0.7 else "turbulent",
            "swarm_coherence": max(0.0, confidence - 0.3) / 0.7,
        }, fidelity, compression
    return {
        "civilization_health": {"avg_energy": 100, "avg_confidence": 0.7},
        "epoch": "unknown",
        "swarm_coherence": 0.5,
    }, fidelity, compression


def _trauma_mesh_to_swarm(payload: Any, metadata: dict[str, Any]
                           ) -> tuple[dict[str, Any], float, float]:
    """
    MESH → SWARM：集体创伤 → 文明伤痕记录。

    将 MESH 层级积累的创伤模式进一步压缩为文明级"历史伤痕"。
    只保留最粗粒度的模式类型和烈度——"文明在哪些模式上受过伤"。
    """
    fidelity = 0.3    # 极低保真——几乎所有细节都丢失
    compression = 0.95  # 极高压缩

    if isinstance(payload, dict):
        severity = payload.get("severity", 0.0)
        trauma_type = payload.get("trauma_type", "unknown")
        return {
            "historical_wound": {
                "type": trauma_type,
                "severity": severity,
                "generations_affected": payload.get("source_count", 1),
            },
            "scar": f"wound_{trauma_type}_{'severe' if severity > 0.7 else 'mild'}",
        }, fidelity, compression
    return {"scar": "unknown"}, fidelity, compression


def _death_mesh_to_swarm(payload: Any, metadata: dict[str, Any]
                          ) -> tuple[dict[str, Any], float, float]:
    """
    MESH → SWARM：灭绝记录 → 文明大灭绝年表。

    将 MESH 层级的灭绝警告压缩为文明级"历史灭绝事件"。
    后代文明可以通过查询 SWARM 回声感知"祖先文明的消亡模式"。
    """
    fidelity = 0.35
    compression = 0.92

    if isinstance(payload, dict):
        event = payload.get("extinction_event", {})
        return {
            "mass_extinction": {
                "primary_cause": event.get("cause", "unknown"),
                "avg_lifespan": event.get("lifespan_cycles", 0),
                "critical_threshold_reached": event.get("critical", False),
            },
            "era": "pre_extinction",
        }, fidelity, compression
    return {"era": "unknown"}, fidelity, compression


def _swarm_to_mesh(payload: Any, metadata: dict[str, Any]
                    ) -> tuple[dict[str, Any], float, float]:
    """
    SWARM → MESH：文明智慧 → 群体启示。

    将 SWARM 层级的文明健康报告展开为 MESH 层级的启发式指南。
    这是"先贤智慧"的工程实现——文明经验向下滋养群体。
    """
    fidelity = 0.4
    compression = -0.6  # 展开

    if isinstance(payload, dict):
        health = payload.get("civilization_health", {})
        epoch = payload.get("epoch", "unknown")
        return {
            "civilization_guidance": {
                "epoch": epoch,
                "caution_advised": health.get("trauma_present", False),
                "confidence_floor": max(0.2, health.get("avg_confidence", 0.7) - 0.1),
                "coherence_bias": payload.get("swarm_coherence", 0.5),
            },
        }, fidelity, compression
    return {"guidance": "explore"}, 0.3, -0.4


# ====================================================================
# 回声模式 (EchoPattern)
# ====================================================================

@dataclass
class EchoPattern:
    """
    回声模式 — 跨尺度共振检测的结果。

    当一个模式在两个以上层级同时出现时，产生"回声"。
    回声可能暗示一个"普遍不变量"——在所有层级都成立的基本规律。

    Attributes:
        pattern_id: 模式唯一标识
        signature: 模式的抽象签名（用于跨层级匹配）
        scales_observed: 观察到该模式的层级列表
        first_seen: 首次观测时间
        last_seen: 最近观测时间
        echo_count: 回声次数
        metadata: 扩展信息
    """

    pattern_id: str
    signature: str
    scales_observed: list[Scale] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    echo_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_universal(self) -> bool:
        """是否在所有层级都观察到。"""
        return len(set(self.scales_observed)) >= 4

    @property
    def depth(self) -> int:
        """跨层级深度。"""
        return len(set(self.scales_observed))


class EchoDetector:
    """
    回声探测器 — 检测跨层级重复出现的模式。

    当一个模式在 ≥2 个层级出现时，注册为"回声"。
    回声可能是噪声（偶然重复）或"普遍不变量"（本质规律）。

    使用方式:
        detector = EchoDetector()
        detector.record("high_energy_shock", Scale.INFANT)
        detector.record("high_energy_shock", Scale.MESH)
        echoes = detector.get_echoes(min_depth=2)  # 跨层级回声
    """

    def __init__(self):
        self._patterns: dict[str, EchoPattern] = {}
        self._total_echoes: int = 0

    def record(self, signature: str, scale: Scale,
               metadata: dict[str, Any] | None = None) -> EchoPattern:
        """
        在指定层级记录一个模式出现。

        如果该模式已在其他层级出现过，则更新回声计数。

        Args:
            signature: 模式签名
            scale: 出现的层级
            metadata: 额外信息

        Returns:
            更新后的 EchoPattern
        """
        now = time.time()
        if signature in self._patterns:
            pattern = self._patterns[signature]
            if scale not in pattern.scales_observed:
                pattern.scales_observed.append(scale)
                pattern.echo_count += 1
                self._total_echoes += 1
                logger.debug(
                    "[Echo] 跨层级回声: %s @ %s (深度=%d)",
                    signature, scale.level_name, pattern.depth,
                )
            pattern.last_seen = now
            if metadata:
                pattern.metadata.update(metadata)
        else:
            pattern = EchoPattern(
                pattern_id=uuid.uuid4().hex[:8],
                signature=signature,
                scales_observed=[scale],
                first_seen=now,
                last_seen=now,
                metadata=metadata or {},
            )
            self._patterns[signature] = pattern

        return pattern

    def get_echoes(self, min_depth: int = 2) -> list[EchoPattern]:
        """
        获取跨层级回声（按深度降序）。

        Args:
            min_depth: 最小跨层级深度（默认 2，即至少两个不同层级）

        Returns:
            符合条件的回声模式列表
        """
        echoes = [
            p for p in self._patterns.values()
            if p.depth >= min_depth
        ]
        echoes.sort(key=lambda p: (-p.depth, -p.echo_count))
        return echoes

    @property
    def total_patterns(self) -> int:
        return len(self._patterns)

    @property
    def all_patterns(self) -> list[EchoPattern]:
        """所有已记录的模式（只读视图）。"""
        return list(self._patterns.values())

    def get_status(self) -> dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "total_echoes": self._total_echoes,
            "cross_scale_echoes": len(self.get_echoes(min_depth=2)),
            "universal_patterns": sum(1 for p in self._patterns.values() if p.is_universal),
        }
