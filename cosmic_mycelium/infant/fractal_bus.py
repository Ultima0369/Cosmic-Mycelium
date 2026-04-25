"""
Fractal Bus — 跨尺度对话总线

扩展 BreathBus，增加层感知广播和自动翻译。
消息在层级间传递时自动调用 TranslationTable 进行压缩/展开。

使用方式:
    bus = FractalDialogueBus("mesh-bus")
    bus.register_infant("bee_001", bee_module)

    # 向群体发送个体态势（自动 INFANT→MESH 翻译）
    envelope = MessageEnvelope(Scale.INFANT, Scale.MESH, situation_data)
    bus.publish(envelope)

    # 订阅特定层级的消息
    bus.subscribe(Scale.MESH, mesh_handler)

哲学映射:
  - "万物相连" → 不同层级通过统一总线对话
  - "和而不同" → 保留层级差异，只翻译相邻层级
  - "一多相即" → 个体声音经翻译成为群体信号
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

from cosmic_mycelium.common.fractal import (
    EchoDetector,
    EchoPattern,
    MessageEnvelope,
    Scale,
    TranslationTable,
    _death_infant_to_mesh,
    _death_mesh_to_swarm,
    _situation_infant_to_mesh,
    _situation_mesh_to_infant,
    _situation_mesh_to_swarm,
    _swarm_to_mesh,
    _trauma_infant_to_mesh,
    _trauma_mesh_to_swarm,
)
from cosmic_mycelium.infant.breath_bus import BreathBus, BreathSignal

logger = logging.getLogger(__name__)

# 回调类型
ScaleHandler = Callable[[MessageEnvelope], None]


class FractalDialogueBus:
    """
    跨尺度对话总线。

    包装 BreathBus，增加层级感知能力。消息在跨层级发送时
    自动通过 TranslationTable 进行翻译，记录保真度和压缩比。

    支持三种模式:
      1. 层级内通信 (同层级) — 无损，直接转发
      2. 升级通信 (向上) — 压缩，抽象
      3. 降级通信 (向下) — 展开，实例化

    Attributes:
        name: 总线名称
        breath_bus: 底层呼吸总线
        translator: 跨层级翻译表
        echo_detector: 回声探测器
    """

    def __init__(self, name: str = "fractal-bus", verbose: bool = False,
                 cache_ttl: float = 2.0):
        """
        Args:
            name: 总线名称
            verbose: 详细日志
            cache_ttl: 查询结果缓存有效期（秒），默认 2s
        """
        self.name = name
        self.verbose = verbose
        self._cache_ttl = cache_ttl
        self.breath_bus = BreathBus(name)

        # 跨层级翻译
        self.translator = TranslationTable()
        self._register_default_translators()

        # 层级订阅者: scale → [(name, handler)]
        self._subscribers: dict[Scale, list[tuple[str, ScaleHandler]]] = defaultdict(list)

        # 消息统计
        self._total_messages: int = 0
        self._messages_by_scale: dict[str, int] = defaultdict(int)

        # 回声探测
        self.echo_detector = EchoDetector()

        # 抗体银行：跨节点抗体共享存储（pattern → [antibody_dict, ...]）
        self._antibody_bank: dict[str, list[dict]] = {}
        self._max_antibody_bank_size: int = 1000  # 防止无限增长

        # 查询结果缓存: key → (expire_at, value)
        self._query_cache: dict[str, tuple[float, Any]] = {}

        # 链接呼吸总线：BreathSignal → 自动探测回声
        self.breath_bus.register_callback(self._on_breath_signal, "fractal-echo")

    def _register_default_translators(self) -> None:
        """注册内置的默认翻译函数。"""
        self.translator.register(
            Scale.INFANT, Scale.MESH,
            _situation_infant_to_mesh,
            description="个体态势 → 群体统计特征 (有损压缩)",
        )
        self.translator.register(
            Scale.MESH, Scale.INFANT,
            _situation_mesh_to_infant,
            description="群体统计 → 个体启发偏置 (带不确定性展开)",
        )
        self.translator.register(
            Scale.INFANT, Scale.MESH,
            _trauma_infant_to_mesh,
            description="个体创伤 → 群体危险签名 (低保真高压缩)",
        )
        self.translator.register(
            Scale.INFANT, Scale.MESH,
            _death_infant_to_mesh,
            description="个体死亡 → 群体灭绝记录 (低保真高压缩)",
        )
        self.translator.register(
            Scale.MESH, Scale.SWARM,
            _situation_mesh_to_swarm,
            description="群体统计 → 文明健康摘要 (二次压缩)",
        )
        self.translator.register(
            Scale.MESH, Scale.SWARM,
            _trauma_mesh_to_swarm,
            description="集体创伤 → 文明伤痕记录 (极低保真)",
        )
        self.translator.register(
            Scale.MESH, Scale.SWARM,
            _death_mesh_to_swarm,
            description="灭绝记录 → 文明大灭绝年表 (极低保真)",
        )
        self.translator.register(
            Scale.SWARM, Scale.MESH,
            _swarm_to_mesh,
            description="文明智慧 → 群体启示 (带不确定性展开)",
        )

    # ── 订阅/注销 ────────────────────────────────────────────────────

    def subscribe(self, scale: Scale, handler: ScaleHandler,
                  name: str | None = None) -> str:
        """
        订阅指定层级的所有消息。

        Args:
            scale: 要订阅的层级
            handler: 消息处理函数
            name: 订阅者名称（自动生成如果未提供）

        Returns:
            订阅者名称
        """
        sub_name = name or f"{scale.level_name}-sub-{len(self._subscribers[scale])}"
        self._subscribers[scale].append((sub_name, handler))
        logger.debug(
            "[FractalBus:%s] %s 订阅 %s 层级消息",
            self.name, sub_name, scale.level_name,
        )
        return sub_name

    def unsubscribe(self, scale: Scale, name: str) -> bool:
        """取消订阅。"""
        before = len(self._subscribers[scale])
        self._subscribers[scale] = [
            (n, h) for n, h in self._subscribers[scale] if n != name
        ]
        removed = len(self._subscribers[scale]) < before
        if removed:
            logger.debug(
                "[FractalBus:%s] %s 取消订阅 %s",
                self.name, name, scale.level_name,
            )
        return removed

    # ── 发布 ─────────────────────────────────────────────────────────

    def publish(self, envelope: MessageEnvelope) -> list[MessageEnvelope]:
        """
        发布一条跨层级消息。

        消息按目标层级分发到所有订阅者。
        如果目标层级与来源层级不同，自动调用翻译。

        Args:
            envelope: 消息信封

        Returns:
            所有已分发的消息副本列表（翻译后）
        """
        self._total_messages += 1
        self._messages_by_scale[
            f"{envelope.source_scale.level_name}→{envelope.target_scale.level_name}"
        ] += 1

        # 如果需要跨层级翻译
        if envelope.source_scale != envelope.target_scale:
            translated = self.translator.translate(envelope)
            if translated is None:
                logger.warning(
                    "[FractalBus:%s] 消息 %s→%s 翻译失败，丢弃",
                    self.name,
                    envelope.source_scale.level_name,
                    envelope.target_scale.level_name,
                )
                return []
            # 分发翻译后的副本
            results = [translated]
            self._dispatch_to_scale(translated.target_scale, translated)
        else:
            # 同级分发
            results = [envelope]
            self._dispatch_to_scale(envelope.target_scale, envelope)

        return results

    def _dispatch_to_scale(self, scale: Scale, envelope: MessageEnvelope) -> None:
        """将消息分发到指定层级的所有订阅者。"""
        for name, handler in self._subscribers.get(scale, []):
            try:
                handler(envelope)
            except Exception as e:
                logger.error(
                    "[FractalBus:%s] 分发到 %s@%s 失败: %s",
                    self.name, name, scale.level_name, e,
                )

    # ── 便捷方法 ─────────────────────────────────────────────────────

    def publish_situation(self, situation_data: dict[str, object],
                          source_scale: Scale = Scale.INFANT,
                          target_scale: Scale = Scale.MESH,
                          source_id: str = "unknown") -> list[MessageEnvelope]:
        """
        便捷方法：发布态势数据到目标层级。

        典型用法: 个体节点向网格发布态势报告。
        """
        envelope = MessageEnvelope(
            source_scale=source_scale,
            target_scale=target_scale,
            payload=situation_data,
            source_id=source_id,
        )
        return self.publish(envelope)

    def broadcast_to_scale(self, scale: Scale, payload: dict[str, object],
                           source_id: str = "fractal-bus") -> list[MessageEnvelope]:
        """在同一层级内广播消息（同级无损）。"""
        envelope = MessageEnvelope(
            source_scale=scale,
            target_scale=scale,
            payload=payload,
            source_id=source_id,
        )
        return self.publish(envelope)

    def register_infant(self, infant_id: str, handler: ScaleHandler,
                        mesh_handler: ScaleHandler | None = None) -> None:
        """
        注册一个个体蜜蜂到总线。

        自动订阅 INFANT 层级的消息，并可选择注册 MESH 层级处理。

        Args:
            infant_id: 蜜蜂 ID
            handler: INFANT 层级消息处理
            mesh_handler: 可选的 MESH 层级消息处理（接收翻译后的群体消息）
        """
        self.subscribe(Scale.INFANT, handler, name=infant_id)
        if mesh_handler:
            self.subscribe(Scale.MESH, mesh_handler, name=f"{infant_id}-mesh")
        logger.info(
            "[FractalBus:%s] 个体 %s 注册 (INFANT)",
            self.name, infant_id,
        )

    # ── 常规态势发布 ──────────────────────────────────────────────────

    def publish_situation_update(self, situation_data: dict[str, object],
                                  source_id: str = "unknown") -> list[MessageEnvelope]:
        """
        发布常规态势更新到 MESH（非创伤/死亡事件）。

        供 DIFFUSE 阶段调用，让群体感知个体的日常状态。
        不触发创伤或死亡的回声记录，仅更新集体态势画像。

        Args:
            situation_data: 态势数据（含 energy, confidence 等）
            source_id: 来源节点 ID

        Returns:
            翻译并分发后的消息副本
        """
        # 在 MESH 层级记录能量/置信度信息，供 get_collective_situation 聚合
        self.echo_detector.record(
            signature=f"situation_{source_id}",
            scale=Scale.MESH,
            metadata={
                "event_type": "situation",
                "source": source_id,
                "energy": situation_data.get("energy", 100.0),
                "confidence": situation_data.get("confidence", 0.7),
                "timestamp": situation_data.get("timestamp", 0.0),
            },
        )
        # 通过态势翻译器发布（INFANT→MESH，有损压缩）
        envelope = MessageEnvelope(
            source_scale=Scale.INFANT,
            target_scale=Scale.MESH,
            payload=situation_data,
            source_id=source_id,
            metadata={"event_type": "situation"},
        )
        return self.publish(envelope)

    def publish_path_success(self, path: list[str], quality: float,
                              source_id: str = "unknown") -> None:
        """
        发布一条成功路径到 MESH，供其他节点学习。

        正向信息素共享——一个节点的探索成果成为群体的启发式。
        不记录为创伤或死亡，仅作为集体经验的一部分。

        Args:
            path: 成功的路径（动作序列）
            quality: 路径质量评分
            source_id: 来源节点 ID
        """
        path_key = "->".join(path)
        self.echo_detector.record(
            signature=f"success_path_{quality:.2f}",
            scale=Scale.MESH,
            metadata={
                "event_type": "success_path",
                "source": source_id,
                "path": path_key,
                "quality": quality,
            },
        )
        if self.verbose:
            print(f"[{self.name}] 🧬 路径共享: {path_key[:48]} (质量={quality:.3f})")

    def get_shared_paths(self, min_quality: float = 0.5,
                          top_k: int = 5) -> list[dict[str, Any]]:
        """
        获取 MESH 层级共享的成功路径。

        Args:
            min_quality: 最低质量阈值
            top_k: 返回的最大路径数

        Returns:
            共享路径列表，每项含 path, quality, source
        """
        ck = self._cache_key("shared_paths", min_quality=min_quality, top_k=top_k)
        cached = self._get_cached(ck)
        if cached is not None:
            return cached
        shared = []
        for p in self.echo_detector.all_patterns:
            meta = p.metadata or {}
            if meta.get("event_type") == "success_path":
                quality = meta.get("quality", 0.0)
                if quality >= min_quality:
                    shared.append({
                        "path": meta.get("path", ""),
                        "quality": quality,
                        "source": meta.get("source", "unknown"),
                        "echo_count": p.echo_count,
                    })
        shared.sort(key=lambda x: -x["quality"])
        result = shared[:top_k]
        self._set_cached(ck, result)
        return result

    # ── SWARM 层级交互 ─────────────────────────────────────────────────

    def publish_to_swarm(self, payload: dict[str, object],
                          event_type: str = "situation",
                          source_id: str = "mesh") -> list[MessageEnvelope]:
        """
        发布 MESH 层级的集体摘要到 SWARM 层级。

        这是"文明记忆"的上行通道——群体的经验沉淀为文明的历史。
        经过 MESH→SWARM 翻译后，个体细节已不可辨。

        Args:
            payload: MESH 层级数据
            event_type: 事件类型（situation / trauma / death）
            source_id: 来源标识

        Returns:
            翻译并分发后的消息副本
        """
        envelope = MessageEnvelope(
            source_scale=Scale.MESH,
            target_scale=Scale.SWARM,
            payload=payload,
            source_id=source_id,
            metadata={"event_type": event_type},
        )
        # 在 SWARM 层级记录回声
        self.echo_detector.record(
            signature=f"swarm_{event_type}",
            scale=Scale.SWARM,
            metadata={"event_type": event_type, "source": source_id},
        )
        return self.publish(envelope)

    def get_swarm_wisdom(self) -> dict[str, Any]:
        """
        查询 SWARM 层级的文明智慧摘要。

        返回聚合后的文明级洞察——群体的经验在最高尺度上的投影。

        Returns:
            - civilization_health: 文明健康摘要
            - epoch: 当前文明纪
            - swarm_coherence: 文明凝聚力
            - warnings: SWARM 层级的活跃警告
        """
        ck = self._cache_key("swarm_wisdom")
        cached = self._get_cached(ck)
        if cached is not None:
            return cached
        all_patterns = self.echo_detector.get_echoes(min_depth=1)
        swarm_patterns = [p for p in all_patterns if Scale.SWARM in p.scales_observed]

        if not swarm_patterns:
            result = {
                "civilization_health": {"avg_energy": 100, "avg_confidence": 0.7},
                "epoch": "pre_civilization",
                "swarm_coherence": 0.0,
                "warnings": [],
            }
            self._set_cached(ck, result)
            return result

        # 从 SWARM 模式中提取文明级信息
        traumas = [p for p in swarm_patterns
                   if p.metadata and p.metadata.get("event_type") == "trauma"]
        deaths = [p for p in swarm_patterns
                  if p.metadata and p.metadata.get("event_type") == "death"]

        result = {
            "civilization_health": {
                "total_echoes": len(swarm_patterns),
                "trauma_count": len(traumas),
                "extinction_count": len(deaths),
            },
            "epoch": "recorded" if len(swarm_patterns) > 0 else "pre_civilization",
            "swarm_coherence": min(1.0, len(swarm_patterns) * 0.1),
            "warnings": [
                {"type": "extinction", "count": len(deaths)},
                {"type": "trauma", "count": len(traumas)},
            ],
        }
        self._set_cached(ck, result)
        return result

    # ── 便捷发布方法 ──────────────────────────────────────────────────

    def publish_trauma(self, situation_data: dict[str, object],
                       source_id: str = "unknown") -> list[MessageEnvelope]:
        """
        发布个体创伤事件到 MESH 层级。

        自动将具体创伤路径压缩为"危险签名"，供群体感知。
        EchoDetector 自动在 MESH 层级记录签名，形成集体本能。

        Args:
            situation_data: 创伤时的态势数据（含 energy, confidence, surprise 等）
            source_id: 来源节点 ID

        Returns:
            翻译并分发后的消息副本
        """
        envelope = MessageEnvelope(
            source_scale=Scale.INFANT,
            target_scale=Scale.MESH,
            payload=situation_data,
            source_id=source_id,
            metadata={"event_type": "trauma"},
        )
        # 在 MESH 层级记录"critical_state"，与 INFANT 层级同签名形成跨层级回声
        self.echo_detector.record(
            signature="critical_state",
            scale=Scale.MESH,
            metadata={"event_type": "trauma", "source": source_id},
        )
        self.invalidate_cache()
        return self.publish(envelope)

    def publish_death(self, death_data: dict[str, object],
                      source_id: str = "unknown") -> list[MessageEnvelope]:
        """
        发布个体死亡事件到 MESH 层级。

        将死亡原因、寿命、协同度等压缩为"灭绝签名"。
        后代节点可通过查询回声"感知"先辈的死亡模式。

        Args:
            death_data: 死亡报告（含 cause, lifespan_cycles, synergy_score 等）
            source_id: 死亡节点 ID

        Returns:
            翻译并分发后的消息副本
        """
        envelope = MessageEnvelope(
            source_scale=Scale.INFANT,
            target_scale=Scale.MESH,
            payload=death_data,
            source_id=source_id,
            metadata={"event_type": "death"},
        )
        # 在 MESH 层级记录灭绝回声（后代节点可以查询"前辈怎么死的"）
        cause = death_data.get("cause", "unknown")
        death_sig = f"death_{cause}_{death_data.get('synergy_score', 0.5):.2f}"
        self.echo_detector.record(
            signature=death_sig,
            scale=Scale.MESH,
            metadata={"event_type": "death", "source": source_id, "cause": cause},
        )
        self.invalidate_cache()
        return self.publish(envelope)

    # ── 查询缓存 ───────────────────────────────────────────────────────

    def _cache_key(self, method: str, **params: Any) -> str:
        """生成缓存键。"""
        parts = [method]
        for k, v in sorted(params.items()):
            parts.append(f"{k}={v}")
        return ":".join(parts)

    def _get_cached(self, key: str) -> object | None:
        """获取缓存值（未过期）或 None。"""
        entry = self._query_cache.get(key)
        if entry is None:
            return None
        expire_at, value = entry
        if __import__("time").time() >= expire_at:
            del self._query_cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: object, ttl: float | None = None) -> None:
        """写入缓存。"""
        self._query_cache[key] = (__import__("time").time() + (ttl or self._cache_ttl), value)

    def invalidate_cache(self) -> None:
        """清空查询缓存（数据变更后调用）。"""
        self._query_cache.clear()

    # ── 抗体广播（回路二：免疫 → 分形） ──────────────────────────────

    def publish_antibody(
        self,
        antibody_data: dict[str, object],
        source_id: str = "unknown",
        envelope: object | None = None,
    ) -> None:
        """
        发布个体产生的抗体到 MESH 层级。

        抗体在 MESH 层级累积，供其他节点查询并通过 ImmuneMemory.load_antibody()
        加载到本地免疫系统。这使得一个节点的创伤经验可以"预警"整个群体。

        支持通过 AntibodyEnvelope 传递协议元数据（跳数、消息类型等）。
        当 hop_count >= max_migrations 时丢弃该抗体（跳数限制）。

        Args:
            antibody_data: 抗体数据（含 target_pattern, suppression_strength,
                          source_node_id, lifespan_cycles 等）
            source_id: 来源节点 ID
            envelope: 可选的 AntibodyEnvelope 实例，提供协议元数据
        """
        # 从信封或数据中提取跳数
        if envelope is not None:
            hop_count = getattr(envelope, "hop_count", 0)
            source_id = getattr(envelope, "sender_node_id", source_id)
        else:
            hop_count = antibody_data.get("migration_count", 0)

        # 跳数限制检查
        max_hop = antibody_data.get("max_migrations", 5)
        if hop_count >= max_hop:
            if self.verbose:
                print(f"[{self.name}] 🧬 抗体丢弃: 跳数 {hop_count} >= 最大 {max_hop}")
            return

        pattern = antibody_data.get("target_pattern", "unknown")
        bank_key = f"antibody_{pattern}"

        # 存入抗体银行
        if bank_key not in self._antibody_bank:
            self._antibody_bank[bank_key] = []
        self._antibody_bank[bank_key].append({
            **antibody_data,
            "source_id": source_id,
            "arrived_at": __import__("time").time(),
            "hop_count": hop_count,
        })

        # 抗体银行大小限制：超出时淘汰最旧条目
        total_entries = sum(len(v) for v in self._antibody_bank.values())
        if total_entries > self._max_antibody_bank_size:
            all_entries: list[tuple[str, int, float]] = []
            for bk, entries in self._antibody_bank.items():
                for i, e in enumerate(entries):
                    all_entries.append((bk, i, e.get("arrived_at", 0.0)))
            all_entries.sort(key=lambda x: x[2])
            to_evict = all_entries[:total_entries - self._max_antibody_bank_size]
            evict_map: dict[str, list[int]] = {}
            for bk, idx, _ in to_evict:
                evict_map.setdefault(bk, []).append(idx)
            for bk, indices in evict_map.items():
                for idx in sorted(indices, reverse=True):
                    if bk in self._antibody_bank and idx < len(self._antibody_bank[bk]):
                        del self._antibody_bank[bk][idx]
                if bk in self._antibody_bank and not self._antibody_bank[bk]:
                    del self._antibody_bank[bk]

        # 在 MESH 层级记录回声
        self.echo_detector.record(
            signature=bank_key,
            scale=Scale.MESH,
            metadata={
                "event_type": "antibody",
                "source": source_id,
                "pattern": pattern,
                "strength": antibody_data.get("suppression_strength", 0.5),
                "hop_count": hop_count,
            },
        )

        if self.verbose:
            print(f"[{self.name}] 🧬 抗体广播: {pattern} "
                  f"(强度={antibody_data.get('suppression_strength', 0.5):.2f}, "
                  f"跳数={hop_count})")

        self.invalidate_cache()

    def get_foreign_antibodies(self, pattern: str = "",
                               exclude_node: str = "") -> list[dict]:
        """
        查询 MESH 层级中来自其他节点的抗体。

        Args:
            pattern: 可选模式过滤（子串匹配抗体 target_pattern）
            exclude_node: 排除的节点 ID（通常传入自身 ID，只获取"外来"抗体）

        Returns:
            匹配的抗体数据列表，按到达时间降序
        """
        results: list[dict] = []
        for bank_key, antibodies in self._antibody_bank.items():
            for ab in antibodies:
                ab_pattern = ab.get("target_pattern", "")
                if pattern and pattern not in ab_pattern and ab_pattern not in pattern:
                    continue
                if exclude_node:
                    ab_source = ab.get("source_node_id") or ab.get("source_id", "")
                    if ab_source == exclude_node:
                        continue
                results.append(ab)

        results.sort(key=lambda x: x.get("arrived_at", 0), reverse=True)
        return results

    def get_antibody_stats(self) -> dict[str, Any]:
        """获取抗体银行统计信息。"""
        cache_key = self._cache_key("antibody_stats")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        total = sum(len(v) for v in self._antibody_bank.values())
        unique_patterns = len(self._antibody_bank)
        sources: set[str] = set()
        for antibodies in self._antibody_bank.values():
            for ab in antibodies:
                sid = ab.get("source_node_id") or ab.get("source_id", "unknown")
                if sid:
                    sources.add(sid)
        result = {
            "total_antibodies": total,
            "unique_patterns": unique_patterns,
            "unique_sources": len(sources),
            "patterns": list(self._antibody_bank.keys()),
        }
        self._set_cached(cache_key, result)
        return result

    # ── 集体态势聚合 ──────────────────────────────────────────────────

    def get_collective_situation(self) -> dict[str, Any]:
        """
        聚合所有节点在 MESH 层级的态势信息。

        通过对已记录的 MESH 层级模式进行统计分析，
        返回群体的"整体感觉"——不暴露个体细节。

        Returns:
            - node_count: 报告态势的节点数
            - avg_energy: 平均能量
            - avg_confidence: 平均置信度
            - collective_tension: 集体紧张度（低能量 + 低置信度的综合指标）
            - energy_distribution: 能量分布摘要
        """
        cache_key = self._cache_key("collective_situation")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        all_patterns = self.echo_detector.all_patterns
        mesh_situations = []
        for p in all_patterns:
            meta = p.metadata or {}
            if Scale.MESH in p.scales_observed and "energy" in meta:
                mesh_situations.append(meta)

        if not mesh_situations:
            result = {
                "node_count": 0,
                "avg_energy": 100.0,
                "avg_confidence": 0.7,
                "collective_tension": 0.0,
                "energy_distribution": "unknown",
            }
            self._set_cached(cache_key, result)
            return result

        energies = [s.get("energy", 100.0) for s in mesh_situations]
        confidences = [s.get("confidence", 0.7) for s in mesh_situations]
        avg_e = sum(energies) / len(energies)
        avg_c = sum(confidences) / len(confidences)

        # 集体紧张度: 低能量 + 低置信的复合指标
        low_energy_ratio = sum(1 for e in energies if e < 30.0) / len(energies)
        low_conf_ratio = sum(1 for c in confidences if c < 0.4) / len(confidences)
        tension = low_energy_ratio * 0.6 + low_conf_ratio * 0.4

        result = {
            "node_count": len(mesh_situations),
            "avg_energy": round(avg_e, 1),
            "avg_confidence": round(avg_c, 3),
            "collective_tension": round(tension, 3),
            "energy_distribution": (
                "critical" if avg_e < 30.0
                else "low" if avg_e < 50.0
                else "normal" if avg_e < 80.0
                else "healthy"
            ),
        }
        self._set_cached(cache_key, result)
        return result

    # ── 集体智慧查询 ──────────────────────────────────────────────────

    def has_collective_trauma(self, signature_prefix: str = "") -> bool:
        """
        查询 MESH 层级是否存在集体创伤记录。

        这是个体"本能感知"群体的接口——不告诉个体具体发生了什么，
        只告诉它"群体对这个模式有不好的记忆"。

        检查所有已记录的模式（不要求跨层级回声），因为单个节点的
        创伤发布到 MESH 就已经构成集体记忆。

        Args:
            signature_prefix: 可选的签名前缀过滤

        Returns:
            True 如果存在创伤记录
        """
        ck = self._cache_key("has_trauma", prefix=signature_prefix)
        cached = self._get_cached(ck)
        if cached is not None:
            return cached
        all_patterns = self.echo_detector.get_echoes(min_depth=1)
        for p in all_patterns:
            meta = p.metadata or {}
            if meta.get("event_type") == "trauma":
                if not signature_prefix or p.signature.startswith(signature_prefix):
                    self._set_cached(ck, True, ttl=5.0)
                    return True
        self._set_cached(ck, False, ttl=5.0)
        return False

    def get_collective_wisdom(self) -> dict[str, Any]:
        """
        获取聚合的群体经验摘要。

        返回:
            - collective_trauma_count: 群体感知到的创伤模式数
            - extinction_warnings: 活跃的灭绝警告
            - hot_signatures: 最频繁的跨层级回声签名
        """
        ck = self._cache_key("collective_wisdom")
        cached = self._get_cached(ck)
        if cached is not None:
            return cached
        all_patterns = self.echo_detector.get_echoes(min_depth=1)
        trauma_echoes = [e for e in all_patterns if
                         e.metadata and e.metadata.get("event_type") == "trauma"]
        death_echoes = [e for e in all_patterns if
                        e.metadata and e.metadata.get("event_type") == "death"]

        hot = self.get_hot_patterns(top_k=3)

        result = {
            "collective_trauma_count": len(trauma_echoes),
            "extinction_warnings": [
                {"signature": e.signature, "echo_count": e.echo_count}
                for e in death_echoes
            ],
            "hot_signatures": [
                {"signature": e.signature, "depth": e.depth, "count": e.echo_count}
                for e in hot
            ],
        }
        self._set_cached(ck, result)
        return result

    # ── 回声探测集成 ─────────────────────────────────────────────────

    def _on_breath_signal(self, signal: BreathSignal) -> None:
        """
        呼吸信号回调 — 自动探测潜在回声。

        将呼吸状态的剧烈变化注册到回声探测器，
        为跨层级模式识别提供数据。
        """
        # 检测异常模式
        if signal.energy < 20.0 or (signal.confidence is not None and signal.confidence < 0.3):
            self.echo_detector.record(
                signature="critical_state",
                scale=Scale.INFANT,
                metadata={
                    "energy": signal.energy,
                    "confidence": signal.confidence,
                    "state": signal.state.value,
                },
            )

    # ── 状态查询 ─────────────────────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        """所有层级的总订阅者数。"""
        return sum(len(subs) for subs in self._subscribers.values())

    def get_echoes(self, min_depth: int = 2) -> list[EchoPattern]:
        """获取跨层级回声。"""
        return self.echo_detector.get_echoes(min_depth=min_depth)

    def get_hot_patterns(self, top_k: int = 5) -> list[EchoPattern]:
        """获取最活跃的跨层级模式（按回声计数降序）。"""
        echoes = self.echo_detector.get_echoes(min_depth=1)
        echoes.sort(key=lambda p: -p.echo_count)
        return echoes[:top_k]

    def get_stats(self) -> dict[str, Any]:
        """获取总线统计。"""
        return {
            "name": self.name,
            "subscribers_by_scale": {
                s.level_name: len(self._subscribers[s])
                for s in Scale
            },
            "total_subscribers": self.subscriber_count,
            "total_messages": self._total_messages,
            "messages_by_path": dict(self._messages_by_scale),
            "translators": self.translator.registered_count,
            "total_translations": self.translator.get_status()["total_translations"],
            "echoes": {
                "total_patterns": self.echo_detector.total_patterns,
                "cross_scale": len(self.get_echoes(min_depth=2)),
            },
            "breath_bus": self.breath_bus.get_stats(),
        }
