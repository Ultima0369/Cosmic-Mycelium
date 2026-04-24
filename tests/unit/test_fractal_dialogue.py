"""
Unit Tests: Fractal Dialogue Protocol — 跨尺度对话协议

测试层级:
  1. Scale 枚举与层级关系
  2. MessageEnvelope 生命周期与翻译链追踪
  3. TranslationTable 注册与跨尺度翻译
  4. EchoDetector 跨层级回声检测
  5. FractalDialogueBus 发布/订阅与自动翻译
"""

from typing import Any

import pytest

from cosmic_mycelium.common.fractal import (
    EchoDetector,
    EchoPattern,
    MessageEnvelope,
    Scale,
    TranslationTable,
    _situation_infant_to_mesh,
    _situation_mesh_to_infant,
)
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus


# 测试用恒等翻译器（替代已移除的 _identity）
def _identity(payload: Any, metadata: dict) -> tuple[Any, float, float]:
    return payload, 1.0, 0.0


class TestScale:
    """分形层级枚举测试。"""

    def test_scale_values(self):
        assert Scale.NANO.value == 0
        assert Scale.INFANT.value == 1
        assert Scale.MESH.value == 2
        assert Scale.SWARM.value == 3

    def test_level_name(self):
        assert Scale.NANO.level_name == "NANO"
        assert Scale.INFANT.level_name == "INFANT"
        assert Scale.MESH.level_name == "MESH"

    def test_is_adjacent(self):
        assert Scale.INFANT.is_adjacent(Scale.NANO) is True
        assert Scale.INFANT.is_adjacent(Scale.MESH) is True
        assert Scale.NANO.is_adjacent(Scale.MESH) is False  # 跳级
        assert Scale.INFANT.is_adjacent(Scale.SWARM) is False

    def test_direction(self):
        assert Scale.INFANT.direction(Scale.MESH) == "up"
        assert Scale.MESH.direction(Scale.INFANT) == "down"
        assert Scale.INFANT.direction(Scale.INFANT) == "same"
        assert Scale.NANO.direction(Scale.SWARM) == "skip"


class TestMessageEnvelope:
    """消息信封测试。"""

    def test_create_envelope(self):
        env = MessageEnvelope(
            source_scale=Scale.INFANT,
            target_scale=Scale.MESH,
            payload={"energy": 85.0},
            source_id="bee_001",
        )
        assert env.source_scale == Scale.INFANT
        assert env.target_scale == Scale.MESH
        assert env.fidelity == 1.0
        assert env.trace_id is not None
        assert len(env.trace_id) == 12

    def test_is_lossless(self):
        env = MessageEnvelope(Scale.INFANT, Scale.MESH, "data", fidelity=1.0)
        assert env.is_lossless is True

        env2 = MessageEnvelope(Scale.INFANT, Scale.MESH, "data", fidelity=0.6)
        assert env2.is_lossless is False

    def test_is_upward(self):
        env = MessageEnvelope(Scale.INFANT, Scale.MESH, "data")
        assert env.is_upward is True
        assert env.is_downward is False

    def test_is_downward(self):
        env = MessageEnvelope(Scale.MESH, Scale.INFANT, "data")
        assert env.is_downward is True
        assert env.is_upward is False

    def test_with_payload_creates_new_envelope(self):
        env = MessageEnvelope(
            Scale.INFANT, Scale.MESH, {"raw": "data"},
            source_id="bee_001",
        )
        translated = env.with_payload(
            new_payload={"abstracted": "pattern"},
            fidelity=0.6,
            compression_ratio=0.7,
        )
        assert translated.payload == {"abstracted": "pattern"}
        assert translated.fidelity == 0.6
        assert translated.compression_ratio == 0.7
        # trace_id 继承自原信封
        assert translated.trace_id == env.trace_id
        assert translated.parent_id == env.trace_id
        assert translated.source_id == "bee_001"

    def test_unique_trace_ids(self):
        env1 = MessageEnvelope(Scale.INFANT, Scale.MESH, "a")
        env2 = MessageEnvelope(Scale.INFANT, Scale.MESH, "b")
        assert env1.trace_id != env2.trace_id


class TestTranslationTable:
    """翻译表测试。"""

    def test_register_translator(self):
        table = TranslationTable()
        table.register(Scale.INFANT, Scale.MESH, _identity)
        assert table.registered_count == 1

    def test_register_non_adjacent_raises(self):
        table = TranslationTable()
        with pytest.raises(ValueError, match="只能注册相邻层级"):
            table.register(Scale.NANO, Scale.SWARM, _identity)

    def test_translate_up(self):
        table = TranslationTable()
        table.register(Scale.INFANT, Scale.MESH, _situation_infant_to_mesh)

        env = MessageEnvelope(
            Scale.INFANT, Scale.MESH,
            {"energy": 15.0, "confidence": 0.3, "surprise": 0.5,
             "trauma_flag": True, "resonance_intensity": 0.9},
            source_id="bee_001",
        )
        result = table.translate(env)
        assert result is not None
        assert result.target_scale == Scale.MESH
        assert result.source_scale == Scale.INFANT
        assert result.payload["energy_profile"]["critical"] is True
        assert result.payload["trauma_flag"] is True
        assert result.fidelity < 1.0  # 有损压缩

    def test_translate_down(self):
        table = TranslationTable()
        table.register(Scale.MESH, Scale.INFANT, _situation_mesh_to_infant)

        env = MessageEnvelope(
            Scale.MESH, Scale.INFANT,
            {
                "stability": {"confidence": 0.8, "surprise": 0.1, "is_stable": True},
                "trauma_flag": False,
            },
            source_id="mesh_001",
        )
        result = table.translate(env)
        assert result is not None
        assert result.target_scale == Scale.INFANT
        assert result.payload["recommendation"] == "stable"
        assert result.payload["peer_confidence"] == 0.8

    def test_translate_no_translator_returns_none(self):
        table = TranslationTable()
        # 没有注册 NANO↔INFANT
        env = MessageEnvelope(Scale.NANO, Scale.INFANT, "data")
        result = table.translate(env)
        assert result is None

    def test_translate_wrong_direction_returns_none(self):
        """翻译方向与实际注册相反时返回 None（不自动反向匹配）。"""
        table = TranslationTable()
        table.register(Scale.MESH, Scale.INFANT, _situation_mesh_to_infant)

        env = MessageEnvelope(
            Scale.INFANT, Scale.MESH,  # 反向请求，没有注册
            {"energy": 50.0},
        )
        result = table.translate(env)
        assert result is None

    def test_total_translations_counter(self):
        table = TranslationTable()
        table.register(Scale.INFANT, Scale.MESH, _identity)

        env = MessageEnvelope(Scale.INFANT, Scale.MESH, "data")
        table.translate(env)
        table.translate(env)
        assert table.get_status()["total_translations"] == 2

    def test_get_status(self):
        table = TranslationTable()
        table.register(Scale.INFANT, Scale.MESH, _identity,
                       description="test translator")
        status = table.get_status()
        assert status["registered_translators"] == 1


class TestEchoDetector:
    """回声探测测试。"""

    def test_record_new_pattern(self):
        detector = EchoDetector()
        pattern = detector.record("high_shock", Scale.INFANT)
        assert pattern.signature == "high_shock"
        assert pattern.depth == 1
        assert detector.total_patterns == 1

    def test_cross_scale_echo(self):
        detector = EchoDetector()
        detector.record("pattern_x", Scale.INFANT)
        detector.record("pattern_x", Scale.MESH)
        echoes = detector.get_echoes(min_depth=2)
        assert len(echoes) == 1
        assert echoes[0].signature == "pattern_x"
        assert echoes[0].depth == 2
        assert echoes[0].echo_count == 2  # 两次记录（INFANT + MESH）

    def test_same_scale_no_echo(self):
        detector = EchoDetector()
        detector.record("pattern_y", Scale.INFANT)
        detector.record("pattern_y", Scale.INFANT)  # 同层级重复不增加回声
        echoes = detector.get_echoes(min_depth=2)
        assert len(echoes) == 0

    def test_is_universal(self):
        detector = EchoDetector()
        for scale in Scale:
            detector.record("universal_pattern", scale)
        echoes = detector.get_echoes(min_depth=4)
        assert len(echoes) == 1
        assert echoes[0].is_universal is True
        assert echoes[0].depth == 4

    def test_get_status(self):
        detector = EchoDetector()
        detector.record("a", Scale.INFANT)
        detector.record("a", Scale.MESH)
        status = detector.get_status()
        assert status["total_patterns"] == 1
        assert status["cross_scale_echoes"] == 1
        assert status["universal_patterns"] == 0


class TestFractalDialogueBus:
    """跨尺度对话总线测试。"""

    def test_bus_initialization(self):
        bus = FractalDialogueBus("test-bus")
        assert bus.name == "test-bus"
        assert bus.subscriber_count == 0
        assert bus.translator.registered_count >= 1  # 内置翻译器

    def test_subscribe_and_publish_same_scale(self):
        bus = FractalDialogueBus()
        received = []

        def handler(env):
            received.append(env)

        bus.subscribe(Scale.INFANT, handler, "test-handler")
        bus.broadcast_to_scale(Scale.INFANT, {"msg": "hello"}, "test-node")

        assert len(received) == 1
        assert received[0].payload == {"msg": "hello"}
        assert received[0].target_scale == Scale.INFANT

    def test_publish_auto_translates_up(self):
        bus = FractalDialogueBus()
        received = []

        def mesh_handler(env):
            received.append(env)

        bus.subscribe(Scale.MESH, mesh_handler, "mesh-handler")

        # 发布 INFANT → MESH，应自动触发翻译
        bus.publish_situation(
            {"energy": 15.0, "confidence": 0.3, "surprise": 0.5,
             "trauma_flag": True, "resonance_intensity": 0.9},
            source_scale=Scale.INFANT,
            target_scale=Scale.MESH,
            source_id="bee_001",
        )

        assert len(received) == 1
        # 应收到翻译后的 MESH 层级消息
        assert received[0].source_scale == Scale.INFANT
        assert received[0].target_scale == Scale.MESH
        assert "energy_profile" in received[0].payload
        assert received[0].fidelity < 1.0  # 有损

    def test_publish_without_subscriber_no_error(self):
        bus = FractalDialogueBus()
        # 没有任何订阅者，不应报错
        bus.broadcast_to_scale(Scale.INFANT, "data", "test")
        bus.publish_situation({"energy": 50.0}, Scale.INFANT, Scale.MESH, "test")
        # 通过 — 没有异常

    def test_register_infant(self):
        bus = FractalDialogueBus()
        infant_received = []
        mesh_received = []

        def infant_handler(env):
            infant_received.append(env)

        def mesh_handler(env):
            mesh_received.append(env)

        bus.register_infant("bee_001", infant_handler, mesh_handler)
        assert bus.subscriber_count >= 2  # INFANT + MESH 两个订阅

        # 同级消息
        bus.broadcast_to_scale(Scale.INFANT, "hi", "bee_001")
        assert len(infant_received) == 1

        # MESH 层消息
        bus.broadcast_to_scale(Scale.MESH, "group-update", "mesh")
        assert len(mesh_received) == 1

    def test_echo_detection_integration(self):
        """总线应通过呼吸信号自动探测异常回声。"""
        bus = FractalDialogueBus()

        # 模拟低能量呼吸信号（触发回声探测）
        from cosmic_mycelium.infant.breath_bus import BreathSignal
        from cosmic_mycelium.infant.hic import BreathState

        signal = BreathSignal(state=BreathState.CONTRACT, energy=10.0, confidence=0.2)
        bus.breath_bus.broadcast(signal)

        echoes = bus.get_echoes(min_depth=1)
        assert len(echoes) >= 1
        assert echoes[0].signature == "critical_state"

    def test_get_stats(self):
        bus = FractalDialogueBus()

        def handler(env):
            pass

        bus.subscribe(Scale.INFANT, handler, "h1")
        bus.subscribe(Scale.MESH, handler, "h2")
        bus.broadcast_to_scale(Scale.INFANT, "test", "node")

        stats = bus.get_stats()
        assert stats["name"] == "fractal-bus"
        assert stats["total_subscribers"] == 2
        assert stats["total_messages"] == 1
        assert stats["translators"] >= 1

    def test_multiple_subscribers_same_scale(self):
        """同一层级多个订阅者应收到同一份消息。"""
        bus = FractalDialogueBus()
        received = {"a": [], "b": []}

        def make_handler(key):
            def h(env):
                received[key].append(env)
            return h

        bus.subscribe(Scale.INFANT, make_handler("a"), "a")
        bus.subscribe(Scale.INFANT, make_handler("b"), "b")

        bus.broadcast_to_scale(Scale.INFANT, "broadcast", "node")

        assert len(received["a"]) == 1
        assert len(received["b"]) == 1
        assert received["a"][0].payload == "broadcast"

    def test_unsubscribe(self):
        bus = FractalDialogueBus()
        received = []

        def handler(env):
            received.append(env)

        name = bus.subscribe(Scale.INFANT, handler, "removable")
        assert bus.subscriber_count == 1

        bus.unsubscribe(Scale.INFANT, name)
        assert bus.subscriber_count == 0

        bus.broadcast_to_scale(Scale.INFANT, "should_not_arrive", "node")
        assert len(received) == 0


class TestIntegrationSituationScale:
    """Situation + Scale 集成测试。"""

    def test_situation_default_scale(self):
        from cosmic_mycelium.common.situation import Situation
        s = Situation()
        assert s.scale == Scale.INFANT  # 默认层级

    def test_situation_to_dict_includes_scale(self):
        from cosmic_mycelium.common.situation import Situation
        s = Situation(energy=50.0, scale=Scale.MESH)
        d = s.to_dict()
        assert d["scale"] == Scale.MESH.value

    def test_situation_mesh_to_infant_translation(self):
        """Situation 数据通过翻译管线从 MESH → INFANT。"""
        bus = FractalDialogueBus()
        received = []

        def handler(env):
            received.append(env)

        bus.subscribe(Scale.INFANT, handler, "infant-receiver")

        # MESH 层发布群体统计
        mesh_situation = {
            "stability": {"confidence": 0.85, "surprise": 0.05, "is_stable": True},
            "trauma_flag": False,
            "resonance_intensity": 0.3,
        }
        env = MessageEnvelope(Scale.MESH, Scale.INFANT, mesh_situation, source_id="mesh")
        bus.publish(env)

        assert len(received) == 1
        assert received[0].payload["recommendation"] == "stable"
        assert received[0].payload["peer_confidence"] == 0.85
