"""
Cosmic Mycelium — Silicon Infant (Simplified MVP)
The "breathing" core of a single silicon-based lifeform node.

This is the minimal viable implementation that demonstrates:
- HIC energy management & breath cycles
- SympNet physics anchor (energy conservation)
- Slime exploration & convergence
- Myelination memory reinforcement
- Symbiosis interface
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from cosmic_mycelium.cluster.node_manager import NodeManager
    from cosmic_mycelium.infant.engines.engine_bitnet import BitNetReasoningResult
    from cosmic_mycelium.infant.feature_manager import FeatureManager

from cosmic_mycelium.cluster.collective_intelligence import CollectiveIntelligence
from cosmic_mycelium.cluster.consensus import ValueAlignment
from cosmic_mycelium.cluster.node_discovery import NodeDiscovery
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint
from cosmic_mycelium.infant.core.layer_1_timescale_segmenter import TimescaleSegmenter
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper
from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
from cosmic_mycelium.infant.core.layer_4_myelination_memory import MyelinationMemory
from cosmic_mycelium.infant.core.layer_5_superbrain import SuperBrain
from cosmic_mycelium.infant.core.layer_6_symbiosis_interface import (
    InteractionMode,
    SymbiosisInterface,
)
from cosmic_mycelium.infant.core.active_perception import ActivePerceptionGate
from cosmic_mycelium.infant.core.embodied_loop import SensorimotorContingencyLearner
from cosmic_mycelium.infant.engines.engine_bitnet import BitNetAdapter
from cosmic_mycelium.infant.engines.engine_lnn import LNNEngine
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.engines.engine_theia import THEIAEngine
from cosmic_mycelium.infant.feature_manager import FeatureManager
from cosmic_mycelium.infant.hic import HIC, BreathState, HICConfig
from cosmic_mycelium.infant.network.rate_limiter import RateLimiter
from cosmic_mycelium.infant.sensors import SensorArray
from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.loader import SkillLoader
from cosmic_mycelium.infant.skills.lifecycle import SkillLifecycleManager
from cosmic_mycelium.infant.skills.registry import SkillRegistry
from cosmic_mycelium.utils.metrics import (
    PACKETS_RECEIVED,
    PACKETS_SENT,
    MetricsCollector,
)
from cosmic_mycelium.utils.tracing import DistributedTracer


class SiliconInfant:
    """
    Cosmic Mycelium — Silicon Infant.

    A single, autonomous silicon-based lifeform node.
    Exhibits: breathing, self-adaptation, memory formation, symbiosis.
    """

    # Energy costs for neural operations (deducted from HIC budget)
    LNN_ENERGY_COST: float = 0.5       # per LNN prediction
    BITNET_ENERGY_COST: float = 2.0    # per BitNet reasoning (expensive!)
    THEIA_ENERGY_COST: float = 1.0     # per THEIA intuition check
    PERCEPTION_ENERGY_COST: float = 0.1
    ACTION_ENERGY_COST: float = 0.3

    def __init__(
        self,
        infant_id: str,
        config: dict | None = None,
    ):
        self.infant_id = infant_id
        self.config = config or {}

        self._init_energy_system(self.config)
        self._init_cluster_services(self.config)
        self._init_research_loop(self.config)
        self._init_skill_system(self.config)
        self._init_embodied_cognition(self.config)
        self._init_runtime_state(self.config)
        self._init_neural_engines(self.config)

        self._log(f"Infant '{self.infant_id}' initialized. Energy: {self.hic.energy}")

    def _init_energy_system(self, config) -> None:
        # Core components
        self.hic = HIC(
            config=HICConfig(
                energy_max=self.config.get("energy_max", 100.0),
                contract_duration=self.config.get("contract_duration", 0.055),
                diffuse_duration=self.config.get("diffuse_duration", 0.005),
                suspend_duration=self.config.get("suspend_duration", 5.0),
                recovery_energy=self.config.get("recovery_energy", 60.0),
                recovery_rate=self.config.get("recovery_rate", 0.5),
            ),
            name=f"hic-{self.infant_id}",
        )
        self.sympnet = SympNetEngine()
        # Layer 1: TimescaleSegmenter — multi-scale time/space segmentation
        self.layer_1_segmenter = TimescaleSegmenter()
        # Layer 2: Semantic Mapper — maps physical → semantic concepts
        embedding_dim = self.config.get("embedding_dim", 16)
        self.semantic_mapper = SemanticMapper(embedding_dim=embedding_dim)
        self.explorer = SlimeExplorer(num_spores=self.config.get("num_spores", 10))
        self.memory = MyelinationMemory(semantic_mapper=self.semantic_mapper)
        self.brain = SuperBrain()
        self.interface = SymbiosisInterface(self.infant_id)
        self.collective = CollectiveIntelligence(self.infant_id)

        # Phase 4.2.1: Feature Manager — Hermes-inspired skill extraction & myelination
        # 借鉴 Hermes 的"技能创造"和"跨会话记忆"，将成功路径提炼为特征码
        self.feature_manager = FeatureManager(self.infant_id, semantic_mapper=self.semantic_mapper)
        # 当前任务轨迹记录（用于事后提炼特征码）
        self._current_task_trace: list[dict[str, Any]] = []
        self._current_task_success: bool = False
        # Cross-cycle saliency boost (e.g., from value resonance) — IMP-06
        self._current_saliency: float = 1.0

    def _init_cluster_services(self, config) -> None:
        # Cluster: node discovery service (enabled in cluster mode)
        self.node_manager: Any | None = None  # set by MyceliumNetwork.join
        self.discovery: NodeDiscovery | None = None
        if self.config.get("cluster_mode", False):
            self.discovery = NodeDiscovery(self)

        # Monitoring: distributed tracing + metrics
        self._tracer = DistributedTracer(service_name=f"infant-{self.infant_id}")
        self._metrics_collector = MetricsCollector()

        # SEC-004: Rate limiting per source_id
        self._rate_limiter = RateLimiter(
            default_rate=self.config.get("rate_limit_per_sec", 10.0),
            default_capacity=self.config.get("rate_limit_burst", 20.0),
        )

    def _init_research_loop(self, config) -> None:
        # Phase 4.1: Research loop — knowledge store + question generator + experimenter
        self._research_enabled = self.config.get("research_enabled", False)
        if self._research_enabled:
            from cosmic_mycelium.infant.knowledge_store import KnowledgeStore
            from cosmic_mycelium.infant.skills.research.question_generator import (
                QuestionGenerator,
            )
            from cosmic_mycelium.infant.skills.research.experiment_designer import (
                ExperimentDesigner,
            )

            self.knowledge_store = KnowledgeStore(
                self.infant_id, self.semantic_mapper
            )
            self.question_generator = QuestionGenerator(self.knowledge_store)
            self.experiment_designer = ExperimentDesigner()
        else:
            self.knowledge_store = None
            self.question_generator = None
            self.experiment_designer = None

    def _init_skill_system(self, config) -> None:
        # Phase 4.3: Skill Plugin System — load, inject, initialize
        self.skill_registry = SkillRegistry()
        self.skill_loader = SkillLoader(self.skill_registry)
        self.skill_loader.load_all()
        self.skill_lifecycle = SkillLifecycleManager(self.skill_registry)

        # Inject KnowledgeStore into ResearchSkill if research enabled
        if self._research_enabled and self.knowledge_store:
            research_skill = self.skill_registry.get("research")
            if research_skill:
                research_skill.knowledge = self.knowledge_store

        # Initialize all skills (topological order)
        init_ctx = SkillContext(
            infant_id=self.infant_id,
            cycle_count=0,
            energy_available=self.hic.energy,
            hic_suspended=False,
            timestamp=time.time(),
        )
        self.skill_registry.initialize_all(init_ctx)

    def _init_embodied_cognition(self, config) -> None:
        # Sensor array — real-world multi-modal perception
        self.sensors = SensorArray()
        # Phase 5.1: Sensorimotor contingency learner
        self._sensorimotor_learner = SensorimotorContingencyLearner()
        # Phase 5.1-2: Active perception gate
        self._active_perception_gate = ActivePerceptionGate()

    def _init_runtime_state(self, config) -> None:
        # Physical state (derived from sensors, cached)
        self.state = {"q": 1.0, "p": 0.0}
        self._last_perception: dict | None = None
        self._latest_embedding: object | None = None  # np.ndarray from SemanticMapper
        self._last_bitnet_result: BitNetReasoningResult | None = None

        # Network reference (set by MyceliumNetwork.join or orchestrator)
        self.network: Any | None = None
        self.node_manager: NodeManager | None = None

        # Messaging
        self.inbox: list[CosmicPacket] = []
        self.outbox: list[CosmicPacket] = []

        # Statistics
        self.start_time = time.time()
        self._cycle_count = 0
        self.log: deque[dict[str, Any]] = deque(maxlen=1000)

        # Meta-cognitive monitoring (IMP-04): detect internal state fluctuation
        self._internal_fluctuation_history: deque[dict[str, float]] = deque(maxlen=20)
        self.META_SUSPEND_THRESHOLD: float = 0.3  # Fluctuation coefficient threshold
        self._meta_suspend_until: float = 0.0
        self._meta_suspend_active: bool = False

    def _init_neural_engines(self, config) -> None:
        # Phase 4.2: LNN 液态神经网络引擎 — 动态时序预测
        # 输入维度 = 能量历史序列长度，hidden_units = 液态神经元数
        self.lnn_engine = LNNEngine(input_dim=16, hidden_units=64)
        # 能量历史队列（用于 LNN 预测）
        self._energy_history: deque[float] = deque(maxlen=50)
        self.predicted_energy_cost: float = 0.0  # 未来能量消耗预测值

        # Phase 4.2.1: BitNet 节能髓鞘 — 能量门控的深度语义推理
        # 仅在能量充足（>70）且置信度低时触发，利用三进制权重的保守推理特性
        bitnet_model_path = self.config.get(
            "bitnet_model_path",
            "/home/lg/L00/Bitnet/models/bitnet-2b-q4_0.gguf",
        )
        self.bitnet_adapter = BitNetAdapter(
            model_path=bitnet_model_path,
            hic=self.hic,
            energy_threshold=self.config.get("bitnet_energy_threshold", 70.0),
            confidence_threshold=self.config.get("bitnet_confidence_threshold", 0.7),
        )
        self._last_bitnet_result: BitNetReasoningResult | None = None

        # Phase 4.2.2: THEIA 物理直觉引擎 — 延迟判定的独立物理验证模块
        # 独立预训练，不参与自我演化；用于物理状态可行性预判
        self.theia: THEIAEngine | None = None
        if self.config.get("theia_enabled", False):
            theia_model_path = self.config.get(
                "theia_model_path",
                "models/theia_physics.pt",
            )
            try:
                self.theia = THEIAEngine(
                    model_path=theia_model_path,
                    probe_lambda=self.config.get("theia_probe_lambda", 0.5),
                )
                self._log(f"THEIA engine loaded from {theia_model_path}", "INFO")
            except Exception as e:
                self._log(f"THEIA 引擎加载失败: {e}", "ERROR")



    def _log(self, msg: str, level: str = "INFO") -> None:
        """Internal logging — structured + local history."""
        # Structured log entry (for local deque and potential external ingestion)
        entry = {
            "ts": time.time(),
            "level": level,
            "msg": msg,
            "energy": self.hic.energy,
            "state": self.hic.state.value,
        }
        self.log.append(entry)

        # Use Python's standard logging for immediate output
        logger = logging.getLogger(f"infant.{self.infant_id}")
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            msg,
            extra={
                "infant_id": self.infant_id,
                "energy": self.hic.energy,
                "state": self.hic.state.value,
            },
        )

    def _deduct_energy(self, amount: float, reason: str = "") -> None:
        """Deduct energy from HIC budget for computational work."""
        self.hic._energy = max(0.0, self.hic._energy - amount)
        if amount > 0.5:
            self._log(f"Energy -{amount:.2f}: {reason}", "DEBUG")

    def perceive(self) -> dict:
        """
        Sense the world via multi-modal sensor array.
        Reads vibration, temperature, spectrum and maps to physical state (q, p).
        Also maps physical state to semantic concept (L2).
        """
        # Read all sensors
        sensor_data = self.sensors.read_all()

        # Map multi-modal sensors → physical state (q, p)
        vibration = sensor_data["vibration"]
        temperature = sensor_data["temperature"]
        spectrum = sensor_data["spectrum_power"]

        # Update physical state with bounded random walk
        self.state["p"] = max(
            -1.0,
            min(
                1.0, self.state["p"] + vibration * 0.01 + random.uniform(-0.005, 0.005)
            ),
        )
        self.state["q"] = max(
            -1.0,
            min(1.0, self.state["q"] + (temperature - 22.0) * 0.001 + spectrum * 0.005),
        )

        # L2: Map physical state to semantic concept
        physical_state = self.state.copy()
        concept = self.semantic_mapper.map(physical_state)
        self._latest_embedding = concept.feature_vector.copy()

        # Attach raw sensor data and semantic embedding to perception
        perception = {
            "timestamp": time.time(),
            "physical": physical_state,
            "sensors": sensor_data,
            "semantic_embedding": self._latest_embedding,
            "external": {},
        }
        self._last_perception = perception
        return perception

    def disambiguate_intent(self, perception: dict, confidence: float) -> str | None:
        """
        Intent disambiguation: when confidence is low, generate clarification question.

        Returns:
            Clarification question string, or None if confidence is adequate.
        """
        if confidence >= 0.5:
            return None  # No ambiguity

        # Analyze sensor pattern to infer likely cause of low confidence
        sensors = perception.get("sensors", {})
        vibration = sensors.get("vibration", 0)
        temperature = sensors.get("temperature", 22.0)
        spectrum = sensors.get("spectrum_power", 1.0)  # Default: normal illumination

        # Heuristic: match low-confidence patterns to question templates
        if vibration > 0.2:
            return "Is that vibration from machinery or environmental movement?"
        if temperature > 28.0 or temperature < 16.0:
            return f"Temperature is {temperature:.1f}°C — is that expected?"
        if spectrum < 0.2:
            return "Light level very low — should I wait for more illumination?"
        if spectrum > 2.0:
            return "Very bright environment — requires adaptation?"

        # Generic fallback
        return "Perception unclear — what should I focus on?"

    def act(
        self,
        perception: dict,
        predicted: dict,
        confidence: float,
    ) -> CosmicPacket | None:
        """
        Decide and act.
        This is the "conscious choice" point.
        """
        # Check suspend conditions
        if confidence < 0.3 or self.hic.energy < 20:
            return self.hic.get_suspend_packet(self.infant_id)

        # Intent disambiguation: if low confidence, emit a clarification request
        question = self.disambiguate_intent(perception, confidence)
        if question:
            # Enter low-confidence SUSPEND but with a clarifying question
            self._log(f"Clarification needed: {question}", "WARN")
            # Emit a query packet to potential partners (suspended until answered)
            return CosmicPacket(
                timestamp=time.time(),
                source_id=self.infant_id,
                destination_id="broadcast",
                value_payload={
                    "action": "query",
                    "question": question,
                    "context": perception.get("sensors", {}),
                },
            )

        # Plan using slime explorer
        plan, plan_conf = self.explorer.plan(perception, "stable_orbit")
        if plan is None:
            return self.hic.get_suspend_packet(self.infant_id)

        # Phase 4.2.2: THEIA 物理直觉验证 (若启用)
        # 独立预训练模块，评估当前物理状态的可行性
        if self.theia is not None:
            plan_conf = self._apply_theia_intuition(perception, plan, plan_conf)

        # Compute saliency for memory reinforcement.
        # Start with any cross-cycle boost (e.g., from value resonance), then
        # apply energy/confidence multipliers.
        saliency = self._current_saliency
        self._current_saliency = 1.0  # reset for next cycle

        if self.hic.energy < 25.0:
            saliency *= 1.5
        if self.hic.energy < self.hic.config.energy_max * 0.3:
            saliency *= 1.8
        if plan_conf < 0.4:
            saliency *= 1.5

        # Record successful path in myelination memory (saliency-weighted)
        self.memory.reinforce(
            plan["path"],
            success=True,
            saliency=saliency,
            end_state=perception.get("physical", {}),
        )

        # Build packet — action broadcast to network
        action_payload = {
            "action": "plan_execution",
            "plan": plan,
            "confidence": plan_conf,
            "sensor_snapshot": perception.get("sensors", {}),
        }

        # Phase 4.2.1: 记录行动轨迹用于事后提炼特征码 (include saliency)
        self.record_action(perception, action_payload, saliency=saliency)

        return CosmicPacket(
            timestamp=time.time(),
            source_id=self.infant_id,
            value_payload=action_payload,  # confidence 已包含 plan_conf (THEIA 已调整)
        )

    def _apply_theia_intuition(
        self,
        perception: dict,
        plan: dict,
        plan_confidence: float,
    ) -> float:
        """
        Phase 4.2.2: 应用 THEIA 物理直觉来调整计划置信度。

        THEIA 独立评估当前物理状态 (q, p) 的可行性:
        - verdict=1 (True): 物理可行 → confidence += 0.1
        - verdict=0 (False): 物理不可行 → confidence -= 0.3
        - verdict=2 (Unknown): 不确定 → confidence -= 0.1

        同时更新 self.hic.value_vector 的 caution 维度。
        """
        if self.theia is None:
            return plan_confidence

        physical = perception.get("physical", {})
        q = physical.get("q", 0.0)
        p = physical.get("p", 0.0)

        # THEIA 输入: a=q, b=p (简谐振子状态)
        try:
            result = self.theia.intuit({"a": q, "b": p})
            verdict = result.verdict
            theia_conf = result.confidence

            # Energy cost: THEIA intuition (configurable)
            self._deduct_energy(
                self.config.get("theia_energy_cost", self.THEIA_ENERGY_COST),
                "THEIA intuition",
            )

            # 根据 THEIA 判定调整计划置信度
            if verdict == 1:  # True — 物理可行
                adjusted = min(1.0, plan_confidence + 0.1 * theia_conf)
                self._log(f"THEIA ✅ 物理可行 (+conf), verdict_conf={theia_conf:.2f}", "DEBUG")
            elif verdict == 0:  # False — 物理不可行
                adjusted = max(0.0, plan_confidence - 0.3 * theia_conf)
                self._log(f"THEIA ⚠️ 物理不可行 (-conf), verdict_conf={theia_conf:.2f}", "WARN")
                # 触发 caution 适应
                self.hic.adapt_value_vector({"caution": 0.02})
            else:  # Unknown
                adjusted = max(0.0, plan_confidence - 0.1)
                self._log(f"THEIA❓ 判定未知 (-conf)", "INFO")

            # THEIA 推理已完成 (THEIAEngine.intuit() 内部已更新统计)
            return adjusted

        except Exception as e:
            self._log(f"THEIA 推理失败: {e}", "ERROR")
            return plan_confidence

    def predict(self, perception: dict) -> tuple[dict, float]:
        """Predict next state using SympNet."""
        q = perception["physical"]["q"]
        p = perception["physical"]["p"]

        # Predict 10 steps ahead
        q_pred, p_pred = self.sympnet.predict(q, p, steps=10)

        predicted = {"q": q_pred, "p": p_pred}

        # Confidence based on energy drift health
        health = self.sympnet.get_health()
        confidence = max(0.0, 1.0 - health["avg_drift"] * 1000)

        return predicted, confidence

    def verify(self, predicted: dict, actual: dict) -> float:
        """Compute prediction error."""
        q_pred = float(predicted.get("q", 0))
        p_pred = float(predicted.get("p", 0))
        q_actual = float(actual["physical"]["q"])
        p_actual = float(actual["physical"]["p"])
        q_err = abs(q_pred - q_actual)
        p_err = abs(p_pred - p_actual)
        return (q_err + p_err) / 2.0

    def adapt(self, error: float) -> None:
        """Self-modify based on prediction error."""
        if error > self.config.get("adaptation_threshold", 0.001):
            self._log(f"Prediction error {error:.4f} → adapting", "WARN")
            self.sympnet.adapt()
            self.hic.adapt_value_vector({"caution": 0.01})
            self.memory.reinforce(["predict", "error"], success=False)

    def process_inbox(self) -> None:
        """Handle incoming messages."""
        # ── SEC-003: inbox DoS 防护 — 限制最大消息数 ─────────────────────────
        MAX_INBOX_SIZE = 1000
        if len(self.inbox) > MAX_INBOX_SIZE:
            excess = len(self.inbox) - MAX_INBOX_SIZE
            # 丢弃最旧的消息 (保留最新的)
            self.inbox = self.inbox[-MAX_INBOX_SIZE:]
            self._log(f"Inbox overflow: dropped {excess} old messages (DoS mitigation)", "WARN")
        # ────────────────────────────────────────────────────────────────────

        for packet in self.inbox:
            # ── SEC-004: 速率限制 (per source_id) ───────────────────────────────
            if not self._rate_limiter.check(packet.source_id):
                self._log(f"Rate limit exceeded from {packet.source_id} — dropped", "WARN")
                continue
            # ────────────────────────────────────────────────────────────────────

            # Record packet received metric
            # Record packet received metric
            flow_type = packet.get_flow_type()
            PACKETS_RECEIVED.labels(infant_id=self.infant_id, flow_type=flow_type).inc()

            if packet.value_payload:
                vp = packet.value_payload
                msg_type = vp.get("type")

                # ── SEC-001: 白名单 + 来源认证 ───────────────────────────────────
                ALLOWED_MSG_TYPES = {
                    "suspend",
                    "consensus_proposal",
                    "value_broadcast",
                    "cluster_proposal",
                    "QUERY",
                    "node_announce",
                }
                if msg_type not in ALLOWED_MSG_TYPES:
                    self._log(
                        f"Unknown msg_type '{msg_type}' from {packet.source_id} — dropped",
                        "WARN",
                    )
                    continue

                # value_broadcast 必须来自已知活跃伙伴 (信任 ≥0.5)
                if msg_type == "value_broadcast":
                    active_partner_ids = [
                        p.partner_id for p in self.interface.get_active_partners(min_trust=0.5)
                    ]
                    if packet.source_id not in active_partner_ids:
                        self._log(
                            f"Drop value_broadcast from untrusted/unknown {packet.source_id}",
                            "WARN",
                        )
                        continue
                # ────────────────────────────────────────────────────────────────────

                # ── Node Discovery: peer announcement ───────────────────────────
                if msg_type == "node_announce" and self.discovery:
                    self.discovery.process_announcement(vp)

                # ── Existing handlers ───────────────────────────────────────────
                elif msg_type == "suspend":
                    self.hic.adapt_value_vector({"caution": 0.005})
                    self._log(f"Node {packet.source_id} suspended — increased caution")

                elif msg_type == "consensus_proposal":
                    self.hic.adapt_value_vector({"mutual_benefit": 0.01})
                    self._log(
                        f"Consensus from {packet.source_id} — increased cooperation"
                    )

                elif msg_type == "value_broadcast":
                    # IMP-06: Value alignment protocol — "和而不同"
                    # ── SEC-002: value_vector 输入验证 ───────────────────────────────
                    other_vector = vp.get("value_vector", {})
                    if not isinstance(other_vector, dict):
                        self._log(
                            f"value_broadcast: value_vector must be dict, got {type(other_vector)} — dropped",
                            "WARN",
                        )
                        continue

                    # 验证所有键为字符串、值在 [0.0, 1.0] 范围内
                    invalid = []
                    for k, v in other_vector.items():
                        if not isinstance(k, str):
                            invalid.append(f"{k}(key-not-str)")
                        elif not isinstance(v, (int, float)):
                            invalid.append(f"{k}(value-type={type(v).__name__})")
                        elif float(v) < 0.0 or float(v) > 1.0:
                            invalid.append(f"{k}(value={v} OOR)")
                    if invalid:
                        self._log(
                            f"value_broadcast: invalid entries {invalid} — dropped",
                            "WARN",
                        )
                        continue
                    # ────────────────────────────────────────────────────────────────────

                    if other_vector:
                        aligner = ValueAlignment()
                        new_vector, resonated = aligner.align(
                            self.hic.value_vector, other_vector
                        )
                        self.hic.value_vector = new_vector
                        if resonated:
                            self._log(f"与 {packet.source_id} 价值共振", "INFO")
                            self._current_saliency = 2.0  # high-saliency event
                        else:
                            self._log(
                                f"与 {packet.source_id} 价值差异大，保持距离", "INFO"
                            )

                elif msg_type == "cluster_proposal":
                    # Forward to collective intelligence
                    self.collective.receive_proposal(
                        proposal_id=vp["proposal_id"],
                        node_id=vp["node_id"],
                        region=vp["region"],
                        content=vp["content"],
                        priority=vp["priority"],
                        activation=vp["activation"],
                        timestamp=vp["timestamp"],
                    )
                    self._log(f"Cluster proposal from {packet.source_id}")

    def _record_metrics(self) -> None:
        """Record infant metrics to Prometheus."""
        self._metrics_collector.collect_infant_metrics(self.infant_id, self)

    def _propagate_global_workspace(self) -> None:
        """Push current SuperBrain global workspace to cluster as proposal."""
        if not self.brain.global_workspace:
            return
        meta_region = self.brain.regions.get("meta")
        activation = meta_region.activation if meta_region else 0.5
        self.collective.propose(
            region="meta",
            content=self.brain.global_workspace.copy(),
            priority=activation,
            activation=activation,
        )

    def _run_collective_cycle(self) -> None:
        """Run collective intelligence step and integrate any new workspace."""
        state = self.collective.step()
        if state:
            self.collective.integrate_cluster_workspace(self.brain)

    def breath_cycle(self) -> CosmicPacket | None:
        """
        One breath cycle — the main loop.
        Contract (explore) → Diffuse (evaluate) → (maybe) Suspend.
        """

        # Tracing span for this breath cycle
        span_id = self._tracer.start_span(
            "breath_cycle",
            attributes={
                "infant_id": self.infant_id,
                "state": self.hic.state.value,
            },
        )

        try:
            # Check meta-cognitive suspend
            now = time.time()
            suspend_packet = self._check_meta_suspend(now)
            if suspend_packet:
                return suspend_packet

            # Update HIC state (this updates breath state and energy)
            self.hic.update_breath(confidence=0.7, work_done=False)

            state = self.hic.state

            if state == BreathState.SUSPEND:
                self._log("In suspend state — recovering", "WARN")
                time.sleep(self.hic.config.suspend_duration)
                return self.hic.get_suspend_packet(self.infant_id)

            elif state == BreathState.CONTRACT:
                return self._contract_phase()

            else:  # DIFFUSE
                self._diffuse_phase()
                return None
        finally:
            # Record metrics after every cycle
            self._record_metrics()
            self._tracer.end_span(span_id)

    def _check_meta_suspend(self, now: float) -> CosmicPacket | None:
        """Check meta-cognitive fluctuation and apply suspend if needed.

        Returns:
            CosmicPacket if should suspend, None to continue.
        """
        # Meta-cognitive check (IMP-04): detect internal state fluctuation
        now = time.time()
        if self._meta_suspend_active and now < self._meta_suspend_until:
            # Still in meta-suspend period — pause and return suspend
            time.sleep(0.1)
            return self.hic.get_suspend_packet(self.infant_id)

        # Monitor internal fluctuation
        fluctuation = self._monitor_internal_fluctuation()
        if fluctuation > self.META_SUSPEND_THRESHOLD:
            self._log(
                f"Internal state fluctuation {fluctuation:.2f} exceeds threshold "
                f"{self.META_SUSPEND_THRESHOLD:.2f} — triggering meta-suspend",
                "WARN",
            )
            self._meta_suspend_active = True
            self._meta_suspend_until = now + 30.0  # 30-second suspension

            # Pause FeatureManager adaptation to prevent runaway learning
            if hasattr(self.feature_manager, "pause_adaptation"):
                self.feature_manager.pause_adaptation = True

            return self.hic.get_suspend_packet(self.infant_id)
        else:
            # Fluctuation正常，确保元悬置解除且适应恢复
            self._meta_suspend_active = False
            if hasattr(self.feature_manager, "pause_adaptation"):
                self.feature_manager.pause_adaptation = False

    def _contract_phase(self) -> CosmicPacket | None:
        """Contract phase: perceive, predict, act.

        Includes: LNN prediction, BitNet reasoning, THEIA intuition,
        brain processing, action execution, task completion, skill cycle.
        """
        # Contract phase: perceive, predict, act

        # Phase 4.2: LNN 液态引擎 — 基于历史能量序列预测未来趋势
        self._energy_history.append(self.hic.energy)
        if len(self._energy_history) >= 10:
            try:
                self.predicted_energy_cost = self.lnn_engine.predict_energy_trend(
                    list(self._energy_history)[-10:]
                )
                self._log(
                    f"LNN prediction: energy_trend={self.predicted_energy_cost:.3f}, "
                    f"lnn_energy={self.lnn_engine.energy():.3f}"
                )
            except Exception as e:
                self._log(f"LNN prediction failed: {e}", "WARN")
                self.predicted_energy_cost = 0.0

        # Energy cost: LNN prediction (configurable)
        self._deduct_energy(
            self.config.get("lnn_energy_cost", self.LNN_ENERGY_COST),
            "LNN prediction",
        )

        # 正常的感知-预测-适应循环
        # Save previous sensors for cross-cycle learner recording
        if hasattr(self, "_last_sensors"):
            self._prev_sensors = self._last_sensors
        perception = self.perceive()
        self._last_sensors = perception.get("sensors", {})

        # Six-layer pipeline: route perception through all layers (L1→L6)
        # Runs alongside existing logic, formalizing the fractal architecture
        self.process_through_layers(perception)

        predicted, confidence = self.predict(perception)

        # Energy cost: perception (configurable)
        self._deduct_energy(
            self.config.get("perception_energy_cost", self.PERCEPTION_ENERGY_COST),
            "perception",
        )

        # Phase 4.2.1: BitNet 深度语义推理（能量门控）
        # 仅在能量充足且置信度低时触发，利用三进制权重的保守推理
        bitnet_result = None
        if self.bitnet_adapter and self.bitnet_adapter.should_invoke(
            self.hic.energy, confidence
        ):
            bitnet_result = self.bitnet_adapter.reason(perception)
            if bitnet_result:
                self._last_bitnet_result = bitnet_result
                self._log(
                    f"BitNet reasoning invoked: {bitnet_result.answer[:60]}... "
                    f"(cost={bitnet_result.energy_cost:.2f} energy)",
                    "INFO"
                )
                # 将深度推理结果注入大脑工作空间
                self.brain.workspace["deep_reasoning"] = {
                    "answer": bitnet_result.answer,
                    "confidence": bitnet_result.confidence,
                    "energy_cost": bitnet_result.energy_cost,
                    "tokens_used": bitnet_result.tokens_used,
                }
                # Energy cost: BitNet reasoning (configurable)
                self._deduct_energy(
                    self.config.get("bitnet_energy_cost", self.BITNET_ENERGY_COST),
                    "BitNet reasoning",
                )

        error = self.verify(predicted, perception)
        self.adapt(error)

        # Phase 5.1: Active perception gate — update with prediction error per sensor
        sensors = perception.get("sensors", {})
        per_sensor_error = {k: error for k in sensors}
        self._active_perception_gate.update(per_sensor_error)

        # Brain regions process
        self.brain.perceive(perception)
        # 将 BitNet 推理结果（若有）一并广播到集群
        if bitnet_result:
            self.brain.workspace["bitnet_reasoning"] = {
                "answer": bitnet_result.answer,
                "confidence": bitnet_result.confidence,
            }
        self.brain.broadcast_global_workspace(
            {
                "confidence": confidence,
                "error": error,
                "bitnet_used": bitnet_result is not None,
            }
        )
        # Share local workspace with cluster
        self._propagate_global_workspace()

        # Phase 4.2.1: 执行行动并记录任务完成（特征码提炼）
        action = self.act(perception, predicted, confidence)
        # 任务完成标记：成功行动（非SUSPEND）触发特征码提炼
        if action and action.value_payload.get("action") != "suspend":
            self.on_task_complete(
                success=True,
                task_description="stable_orbit_plan"
            )
            # Energy cost: action generation (configurable)
            self._deduct_energy(
                self.config.get("action_energy_cost", self.ACTION_ENERGY_COST),
                "action",
            )

            # Phase 5.1: Sensorimotor contingency learner — record action→sensor delta
            prev_sensors = getattr(self, "_prev_sensors", perception.get("sensors", {}))
            cur_sensors = perception.get("sensors", {})
            self._sensorimotor_learner.record("breath_cycle_action", prev_sensors, cur_sensors)
        # Run skill cycle (background skills)
        self._run_skill_cycle()
        return action

    def _diffuse_phase(self) -> None:
        """Diffuse phase: process inbox, collective cycle, memory forget,
        semantic consolidation, feature reflection, skill cycle.
        """
        # Diffuse phase: process messages, forget old paths
        # Energy cost: process_inbox — 0.05 per message, capped at 1.0
        inbox_msg_count = min(len(self.inbox), 20)  # 20 * 0.05 = 1.0 cap
        self.process_inbox()
        self._deduct_energy(
            inbox_msg_count * 0.05,
            f"process_inbox ({inbox_msg_count} messages)",
        )
        # Collective intelligence: select cluster workspace and integrate
        self._run_collective_cycle()
        # Energy cost: memory forget
        self.memory.forget()
        self._deduct_energy(0.1, "memory forget")
        # Epic 3: periodic semantic path consolidation (every 100 cycles)
        if self.hic.total_cycles % 100 == 0 and self.memory.semantic_mapper is not None:
            merged = self.memory.consolidate_semantic_paths()
            if merged > 0:
                self._log(f"Semantic consolidation merged {merged} paths", "INFO")
        self.brain.decay_activations()

        # Phase 4.2.1: 主动反思（借鉴 Hermes "反刍"机制）
        # 每 100 个呼吸周期主动审视特征码效能
        if self.hic.total_cycles % 100 == 0:
            self._reflect_on_features()

        # Run background skill cycle (includes ResearchSkill if enabled)
        self._run_skill_cycle()

        time.sleep(self.hic.config.diffuse_duration)
        return None

    def process_through_layers(self, perception: dict) -> dict:
        """Route perception through all six layers sequentially (L1→L6).

        L1 (TimescaleSegmenter) → accumulate data, create_segment
        L2 (SemanticMapper) → map physical to semantic concept
        L3 (SlimeExplorer) → plan exploration paths from the concept
        L4 (MyelinationMemory) → reinforce/forget based on success signals
        L5 (SuperBrain) → broadcast to brain regions, workspace
        L6 (SymbiosisInterface) → share with partners if interaction needed

        Returns dict with keys: segment, concept, plan, plan_confidence,
                memory_paths, workspace, partner_actions.
        """
        result: dict[str, Any] = {}

        # L1: TimescaleSegmenter — accumulate data, create segment
        sensor_data = perception.get("sensors", {})
        data_point = {**sensor_data, "v": sensor_data.get("vibration", 0.0)}
        self.layer_1_segmenter.accumulate(data_point)
        segment = self.layer_1_segmenter.create_segment()
        result["segment"] = segment

        # L2: SemanticMapper — map physical to semantic concept
        concept = self.semantic_mapper.map(perception.get("physical", {}))
        result["concept"] = concept

        # L3: SlimeExplorer — plan exploration paths from the concept
        plan, plan_conf = self.explorer.plan(perception, "stable_orbit")
        result["plan"] = plan
        result["plan_confidence"] = plan_conf

        # L4: MyelinationMemory — reinforce based on success signals
        if plan:
            self.memory.reinforce(
                plan["path"],
                success=True,
                saliency=self._current_saliency,
                end_state=perception.get("physical", {}),
            )
        result["memory_paths"] = self.memory.get_status()

        # L5: SuperBrain — broadcast to brain regions, workspace
        self.brain.broadcast_global_workspace(
            {
                "layer_pipeline": True,
                "segment_features": segment.features,
                "concept_id": concept.concept_id,
                "plan_quality": plan_conf,
            }
        )
        result["workspace"] = (
            self.brain.global_workspace.copy() if self.brain.global_workspace else {}
        )

        # L6: SymbiosisInterface — share with partners if interaction needed
        partner_actions: list[str] = []
        active_partners = self.interface.get_active_partners(min_trust=0.5)
        for partner in active_partners[:3]:
            self.interface.perceive_partner(
                partner.partner_id,
                trust=partner.trust,
                mode=InteractionMode.COLLABORATE,
            )
            partner_actions.append(partner.partner_id)
        result["partner_actions"] = partner_actions

        return result

    # =============================================================================
    # Phase 4.2.1: Feature Manager Integration — Hermes-inspired self-learning
    # =============================================================================

    def record_action(
        self,
        perception: dict,
        action: dict[str, Any],
        saliency: float = 1.0,
    ) -> None:
        """
        Record each action taken, for later feature extraction.

        Args:
            perception: The perception that led to the action
            action: The action payload that was executed
            saliency: Saliency factor of this event (for weighted memory reinforcement)
        """
        self._current_task_trace.append({
            "perception_pattern": self._extract_pattern(perception),
            "action": action,
            "timestamp": time.time(),
            "saliency": saliency,  # Record saliency for weighted learning
        })

    def _extract_pattern(self, perception: dict) -> str:
        """
        从感知数据中提取"模式"特征（简化版）。

        实际应用中可从振动频谱提取主频、温度梯度等物理特征。
        当前实现使用简化的能量区间分类。
        """
        physical = perception.get("physical", {})
        q = physical.get("q", 0.0)
        p = physical.get("p", 0.0)
        # 简谐振子能量 E = p²/(2m) + ½kq²，取 m=k=1
        energy = 0.5 * (q**2 + p**2)

        sensors = perception.get("sensors", {})
        vibration = sensors.get("vibration", 0.0)

        # 模式分类（可根据需要扩展）
        if vibration > 0.3:
            return "high_vibration"
        elif vibration > 0.1:
            return "medium_vibration"
        elif energy > 1.0:
            return "high_energy"
        elif energy > 0.5:
            return "medium_energy"
        else:
            return "low_energy"

    def _monitor_internal_fluctuation(self) -> float:
        """
        Monitor internal state fluctuation (variance across key metrics).

        Returns:
            Fluctuation coefficient in [0, 1]. Higher = more unstable.
        """
        snapshot = {
            "energy": self.hic.energy,
            "value_caution": self.hic.value_vector.get("caution", 0.5),
            "value_curiosity": self.hic.value_vector.get("curiosity", 0.5),
            "sympnet_damping": self.sympnet.damping,
        }
        self._internal_fluctuation_history.append(snapshot)

        if len(self._internal_fluctuation_history) < 10:
            return 0.0

        # Compute coefficient of variation (std/mean) for each dimension
        recent = list(self._internal_fluctuation_history)[-10:]
        fluctuation = 0.0
        for key in ["energy", "value_caution", "value_curiosity"]:
            values = [s[key] for s in recent]
            mean_val = sum(values) / len(values)
            if mean_val > 1e-9:
                std_val = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5
                fluctuation += std_val / mean_val

        return fluctuation / 3.0  # Average across dimensions

    def on_task_complete(self, success: bool, task_description: str | None = None) -> None:
        """
        任务完成时调用。如果成功，自动提炼特征码。

        这是 Hermes "从经验中创造技能" 的直接对应——将成功路径
        髓鞘化为可复用的 FeatureCode。

        Args:
            success: 任务是否成功完成
            task_description: 任务描述（用于生成特征码名称）
        """
        if not self._current_task_trace:
            return

        if success and len(self._current_task_trace) >= 2:
            # 提取触发模式（任务开始时感知到的模式）
            first_perception = self._current_task_trace[0].get("perception_pattern", "unknown")
            trigger_patterns = [first_perception]

            # 提取行动序列（保留动作参数）
            action_sequence = [
                step["action"] for step in self._current_task_trace
            ]

            # 生成物理指纹（基于任务完成的最终状态）
            # 使用当前物理状态作为验证指纹
            current_fp = self.get_physical_fingerprint()
            validation_fp = current_fp if success else None

            # 任务描述
            task_desc = task_description or f"auto_task_{int(time.time())}"

            # 创建或更新特征码
            self.feature_manager.create_or_update(
                name=f"success_{task_desc.replace(' ', '_')[:30]}",
                description=f"自动提炼：{task_desc}（成功路径）",
                trigger_patterns=trigger_patterns,
                action_sequence=action_sequence,
                validation_fingerprint=validation_fp,
            )

            self._log(f"任务成功，已提炼特征码: {task_desc}", "INFO")

        # 清空当前任务轨迹
        self._current_task_trace = []
        self._current_task_success = False

    def _reflect_on_features(self) -> None:
        """
        主动反思：审视特征码的效能，标记需要改进的。

        借鉴 Hermes 的"反刍"机制，在 DIFFUSE 态触发。
        每 100 个呼吸周期执行一次，审查前5个最常用的特征码。
        """
        features = self.feature_manager.list_all()

        if not features:
            return

        # 只审视最常用的前5个（算力约束）
        for fc in features[:5]:
            efficacy = fc.efficacy()
            usage_count = fc.success_count + fc.failure_count

            if efficacy < 0.3 and usage_count > 5:
                # 效能低的特征码，标记为"待修正"
                self._log(
                    f"特征码效能低，建议重新审视: {fc.name} "
                    f"(效能={efficacy:.2f}, 使用={usage_count}次)",
                    "WARN"
                )
                # 未来可触发"主动学习"任务重新验证

            elif efficacy > 0.8 and usage_count > 3:
                # 高效特征码，考虑"固化"为更底层的直觉
                self._log(
                    f"高效特征码（可髓鞘化）: {fc.name} "
                    f"(效能={efficacy:.2f})",
                    "INFO"
                )

    def _run_skill_cycle(self) -> None:
        """Execute enabled skills for the current cycle."""
        context = SkillContext(
            infant_id=self.infant_id,
            cycle_count=self._cycle_count,
            energy_available=self.hic.energy,
            hic_suspended=self.hic.state == BreathState.SUSPEND,
            timestamp=time.time(),
        )
        try:
            records = self.skill_lifecycle.tick(context)
            for rec in records:
                if not rec.success:
                    self._log(f"Skill '{rec.skill_name}' failed: {rec.error}", "WARN")
        except Exception as e:
            self._log(f"Skill cycle error: {e}", "ERROR")

    def _maybe_research(self) -> None:
        """
        Phase 4.1: 自主科研触发器。

        在 DIFFUSE 态、能量充足、且具备知识库时，自主运行一个微型研究循环：
        1. 提出 1 个问题
        2. 设计实验
        3. 执行实验
        4. 存储 KnowledgeEntry
        """
        if not self._research_enabled:
            return
        if self.hic.energy < 50:
            return  # 能量不足，优先恢复
        # 不必每个周期都研究，降低频率避免干扰主线
        if self.hic.total_cycles % 10 != 0:
            return  # 每 10 个周期尝试一次

        try:
            # Record cycle attempt
            MetricsCollector.record_research_cycle(self.infant_id, success=False, error=False)

            # Bootstrap: 若知识库为空，提出一个初始自检问题
            if self.knowledge_store.get_stats()["total_entries"] == 0:
                self._log("Knowledge store empty — initiating bootstrap self-test", "INFO")
                bootstrap_question = "调整呼吸节律对能量恢复有何影响？"
                bootstrap_hypothesis = "延长 CONTRACT 可能提升能量恢复率"
                plan = self.experiment_designer.design(bootstrap_question, bootstrap_hypothesis)
                entry = self.knowledge_store.execute_experiment(plan)
                self._log(f"Bootstrap experiment result: {entry.conclusion}", "INFO")
                MetricsCollector.record_research_cycle(self.infant_id, success=True, error=False)
                return

            # 正常：从历史中生成问题
            questions = self.question_generator.generate(num_questions=1, recency_days=30.0)
            if not questions:
                return  # 暂无灵感

            q = questions[0]
            self._log(f"Research Q: {q.question}", "INFO")

            # 设计实验
            plan = self.experiment_designer.design(q.question, q.hypothesis)

            # 执行并存储
            entry = self.knowledge_store.execute_experiment(plan)
            self._log(
                f"Experiment result: {entry.conclusion} (conf={entry.confidence:.2f})",
                "INFO",
            )
            MetricsCollector.record_research_cycle(self.infant_id, success=True, error=False)
        except Exception as e:
            self._log(f"Research cycle error: {e}", "WARN")
            MetricsCollector.record_research_cycle(self.infant_id, success=False, error=True)

    def run(self, max_cycles: int | None = None) -> None:
        """
        Main run loop.
        Runs until interrupt or energy depletion.
        """
        self._log("Breathing cycle started", "INFO")

        # NodeDiscovery is an async service requiring an event loop.
        # Start externally via the cluster supervisor (e.g., asyncio.run).

        try:
            while self.hic.energy > 0:
                action = self.breath_cycle()
                if action:
                    self.outbox.append(action)
                    # Record packet sent metric
                    flow_type = action.get_flow_type()
                    PACKETS_SENT.labels(
                        infant_id=self.infant_id, flow_type=flow_type
                    ).inc()

                # Heartbeat to NodeManager every ~10 cycles (≈550ms)
                self._cycle_count += 1
                if self._cycle_count % 10 == 0 and self.node_manager:
                    self.node_manager.record_heartbeat(self.infant_id)

                if max_cycles and self._cycle_count >= max_cycles:
                    break

        except KeyboardInterrupt:
            self._log("Interrupted by user", "INFO")
        finally:
            self._log(f"Stopped after {self._cycle_count} cycles", "INFO")

    def get_status(self) -> dict:
        """Full status report."""
        bitnet_stats = self.bitnet_adapter.get_stats() if self.bitnet_adapter else {}
        feature_stats = self.feature_manager.get_stats() if hasattr(self, 'feature_manager') else {}
        theia_stats = self.theia.get_stats() if self.theia is not None else {}
        return {
            "infant_id": self.infant_id,
            "uptime": time.time() - self.start_time,
            "hic": self.hic.get_status(),
            "sympnet": self.sympnet.get_health(),
            "memory": {
                "paths": len(self.memory.traces),
                "features": len(self.memory.feature_codebook),
                "coverage": self.memory.get_coverage_ratio(),
                "best_paths": self.memory.get_best_paths(3),
            },
            "brain": self.brain.get_status(),
            "interface": self.interface.get_status(),
            "log_tail": list(self.log)[-5:],
            "bitnet": bitnet_stats,
            "features": feature_stats,  # Phase 4.2.1: 特征码统计
            "theia": theia_stats,  # Phase 4.2.2: THEIA 物理直觉统计
        }

    def get_embedding(self) -> object | None:
        """Return latest semantic embedding (for resonance)."""
        return self._latest_embedding

    def get_physical_fingerprint(self) -> str:
        """Generate physical fingerprint from current physical state."""
        return PhysicalFingerprint.generate(self.state)

    def apply_resonance_bonus(self, partner_id: str, similarity: float) -> None:
        """
        Apply 1+1>2 energy bonus from high-resonance with partner.

        Args:
            partner_id: The partner infant ID.
            similarity: Cosine similarity [0,1] of semantic embeddings.
        """
        if similarity < 0.6:
            return  # Below resonance threshold
        # Synergy bonus: max 0.2 energy, scaled by similarity above threshold
        bonus = min(0.2, (similarity - 0.6) * 0.5)
        self.hic._energy = min(self.hic.config.energy_max, self.hic._energy + bonus)
        # Record positive interaction with partner
        self.interface.perceive_partner(
            partner_id, trust=0.6, mode=InteractionMode.COLLABORATE
        )
        self._log(
            f"Resonance bonus +{bonus:.3f} with {partner_id} (sim={similarity:.2f})"
        )

    def get_active_sensors(self, k: int = 3) -> set[str]:
        """Return top-k most interesting sensor names from active perception gate.

        Args:
            k: Number of sensors to return

        Returns:
            Set of sensor names with highest interest scores
        """
        return self._active_perception_gate.get_attention_mask(k)

    # =========================================================================
    # State Serialization — save/load the full infant
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize full infant state to a JSON-serializable dict."""
        hic_status = self.hic.get_status()
        history_entries: list[dict] = []
        for h in list(self.sympnet.history)[-50:]:
            history_entries.append({"q": h["q"], "p": h["p"], "energy": h["energy"], "drift": h["drift"]})

        # Feature manager codes
        feature_codes: list[dict] = []
        if hasattr(self, "feature_manager"):
            for fc in self.feature_manager.list_all():
                feature_codes.append({
                    "name": fc.name,
                    "description": fc.description,
                    "success_count": fc.success_count,
                    "failure_count": fc.failure_count,
                })

        # Knowledge store entries
        knowledge: dict = {}
        if self.knowledge_store is not None:
            ks_stats = self.knowledge_store.get_stats()
            knowledge = {"total_entries": ks_stats.get("total_entries", 0)}

        data: dict[str, Any] = {
            "infant_id": self.infant_id,
            "hic": {
                "energy": hic_status["energy"],
                "energy_max": hic_status["energy_max"],
                "state": hic_status["state"],
                "total_cycles": hic_status["total_cycles"],
                "suspend_count": hic_status["suspend_count"],
                "adaptation_count": hic_status["adaptation_count"],
                "value_vector": hic_status["value_vector"],
                "contract_duration": hic_status["contract_duration"],
                "diffuse_duration": hic_status["diffuse_duration"],
                "suspend_duration": hic_status["suspend_duration"],
                "dormant_state": getattr(self.hic, "_dormant_state", False),
            },
            "sympnet": {
                "mass": self.sympnet.mass,
                "spring_constant": self.sympnet.spring_constant,
                "damping": self.sympnet.damping,
                "history": history_entries,
            },
            "explorer": {
                "exploration_factor": self.explorer.exploration_factor,
            },
            "memory": {
                "trace_count": len(self.memory.traces),
            },
            "brain": self.brain.get_status(),
            "interface": self.interface.get_status(),
            "feature_codes": feature_codes,
            "knowledge": knowledge,
            "lnn_energy_history": list(self._energy_history),
            "meta": {
                "fluctuation_history": list(self._internal_fluctuation_history),
                "meta_suspend_active": self._meta_suspend_active,
                "meta_suspend_until": self._meta_suspend_until,
            },
            "cycle_count": self._cycle_count,
            "saved_at": time.time(),
        }
        return data

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore full infant state from a dict."""
        # HIC
        hic_d = data.get("hic", {})
        self.hic._energy = hic_d.get("energy", self.hic.config.energy_max)
        state_str = hic_d.get("state", "contract")
        try:
            self.hic._state = BreathState(state_str)
        except ValueError:
            self.hic._state = BreathState.CONTRACT
        self.hic.total_cycles = hic_d.get("total_cycles", 0)
        self.hic.suspend_count = hic_d.get("suspend_count", 0)
        self.hic.adaptation_count = hic_d.get("adaptation_count", 0)
        self.hic.value_vector = hic_d.get("value_vector", self.hic.value_vector)
        if hasattr(self.hic, "_dormant_state"):
            self.hic._dormant_state = hic_d.get("dormant_state", False)

        # SympNet
        symp_d = data.get("sympnet", {})
        self.sympnet.mass = symp_d.get("mass", 1.0)
        self.sympnet.spring_constant = symp_d.get("spring_constant", 1.0)
        self.sympnet.damping = symp_d.get("damping", 0.0)

        # Explorer
        explorer_d = data.get("explorer", {})
        self.explorer.exploration_factor = explorer_d.get("exploration_factor", 0.3)

        # Meta state
        meta_d = data.get("meta", {})
        fluct_list = meta_d.get("fluctuation_history", [])
        self._internal_fluctuation_history = deque(fluct_list, maxlen=20)
        self._meta_suspend_active = meta_d.get("meta_suspend_active", False)
        self._meta_suspend_until = meta_d.get("meta_suspend_until", 0.0)

        # LNN energy history
        self._energy_history = deque(data.get("lnn_energy_history", []), maxlen=50)

        # Cycle counter
        self._cycle_count = data.get("cycle_count", 0)

        # Start time: use saved_at if available, otherwise reset
        self.start_time = data.get("saved_at", time.time())

    def save(self, path: str | Path) -> None:
        """Persist full infant state to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        data["saved_at"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        self._log(f"State saved to {path}", "INFO")

    def load(self, path: str | Path) -> None:
        """Restore infant state from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Save file not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        required = {"infant_id", "hic", "sympnet"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Save file missing required keys: {missing}")
        self.from_dict(data)
        self._log(f"State loaded from {path}", "INFO")
