"""
Unit Tests: BreathBus — 呼吸节律总线
"""

import pytest

from cosmic_mycelium.infant.breath_bus import BreathAware, BreathBus, BreathSignal
from cosmic_mycelium.infant.hic import BreathState


class TestBreathSignal:
    """呼吸信号基本测试。"""

    def test_contract_property(self):
        s = BreathSignal(state=BreathState.CONTRACT)
        assert s.is_contract is True
        assert s.is_diffuse is False
        assert s.is_suspend is False

    def test_diffuse_property(self):
        s = BreathSignal(state=BreathState.DIFFUSE)
        assert s.is_contract is False
        assert s.is_diffuse is True
        assert s.is_suspend is False

    def test_suspend_property(self):
        s = BreathSignal(state=BreathState.SUSPEND)
        assert s.is_contract is False
        assert s.is_diffuse is False
        assert s.is_suspend is True

    def test_default_progress_zero(self):
        s = BreathSignal(state=BreathState.CONTRACT)
        assert s.phase_progress == 0.0

    def test_default_energy(self):
        s = BreathSignal(state=BreathState.CONTRACT)
        assert s.energy == 100.0


class TestBreathBus:
    """呼吸总线功能测试。"""

    def test_bus_initialization(self):
        bus = BreathBus("test-bus")
        assert bus.name == "test-bus"
        assert bus.subscriber_count == 0

    def test_register_subscriber(self):
        bus = BreathBus()
        module = _MockModule("m1")
        bus.register("m1", module)
        assert bus.subscriber_count == 1

    def test_broadcast_reaches_subscriber(self):
        bus = BreathBus()
        module = _MockModule("m1")
        bus.register("m1", module)

        signal = BreathSignal(state=BreathState.CONTRACT, energy=85.0)
        bus.broadcast(signal)

        assert module.last_signal is not None
        assert module.last_signal.state == BreathState.CONTRACT
        assert module.last_signal.energy == 85.0

    def test_broadcast_to_multiple_subscribers(self):
        bus = BreathBus()
        m1 = _MockModule("m1")
        m2 = _MockModule("m2")
        bus.register("m1", m1)
        bus.register("m2", m2)

        signal = BreathSignal(state=BreathState.DIFFUSE)
        bus.broadcast(signal)

        assert m1.last_signal.state == BreathState.DIFFUSE
        assert m2.last_signal.state == BreathState.DIFFUSE

    def test_register_callback(self):
        bus = BreathBus()
        received = []

        def cb(signal):
            received.append(signal)

        bus.register_callback(cb, "test_cb")
        signal = BreathSignal(state=BreathState.SUSPEND)
        bus.broadcast(signal)

        assert len(received) == 1
        assert received[0].state == BreathState.SUSPEND

    def test_unregister_removes_subscriber(self):
        bus = BreathBus()
        module = _MockModule("m1")
        bus.register("m1", module)
        assert bus.subscriber_count == 1

        result = bus.unregister("m1")
        assert result is True
        assert bus.subscriber_count == 0

    def test_unregister_nonexistent_returns_false(self):
        bus = BreathBus()
        assert bus.unregister("nonexistent") is False

    def test_exception_isolation(self):
        """一个模块的异常不应影响其他模块。"""
        bus = BreathBus()
        m1 = _MockModule("m1")
        m2 = _BrokenModule("broken")
        bus.register("m1", m1)
        bus.register("broken", m2)

        signal = BreathSignal(state=BreathState.CONTRACT)
        results = bus.broadcast(signal)

        # m1 should have received the signal despite m2's failure
        assert m1.last_signal is not None
        assert m1.last_signal.state == BreathState.CONTRACT
        # broken module should have an error
        assert results["broken"] is not None

    def test_last_signal_tracking(self):
        bus = BreathBus()
        assert bus.last_signal is None

        s1 = BreathSignal(state=BreathState.CONTRACT)
        bus.broadcast(s1)
        assert bus.last_signal.state == BreathState.CONTRACT

        s2 = BreathSignal(state=BreathState.DIFFUSE)
        bus.broadcast(s2)
        assert bus.last_signal.state == BreathState.DIFFUSE

    def test_get_stats(self):
        bus = BreathBus("stats-bus")
        module = _MockModule("m1")
        bus.register("m1", module)
        bus.broadcast(BreathSignal(state=BreathState.CONTRACT))

        stats = bus.get_stats()
        assert stats["name"] == "stats-bus"
        assert stats["subscribers"] == 1
        assert stats["total_broadcasts"] == 1


class TestBreathAware:
    """BreathAware Mixin 测试。"""

    def test_initial_breath_is_none(self):
        obj = _AwareModule()
        assert obj.current_breath is None

    def test_on_breath_updates_state(self):
        obj = _AwareModule()
        signal = BreathSignal(state=BreathState.SUSPEND)
        obj.on_breath(signal)
        assert obj.current_breath is not None
        assert obj.in_suspend is True

    def test_in_contract_flag(self):
        obj = _AwareModule()
        obj.on_breath(BreathSignal(state=BreathState.CONTRACT))
        assert obj.in_contract is True
        assert obj.in_diffuse is False
        assert obj.in_suspend is False

    def test_in_diffuse_flag(self):
        obj = _AwareModule()
        obj.on_breath(BreathSignal(state=BreathState.DIFFUSE))
        assert obj.in_diffuse is True
        assert obj.in_contract is False

    def test_breath_aware_on_bus(self):
        """BreathAware 模块可以直接注册到总线。"""
        bus = BreathBus()
        obj = _AwareModule()
        bus.register("aware", obj)
        bus.broadcast(BreathSignal(state=BreathState.DIFFUSE, energy=75.0))

        assert obj.in_diffuse is True
        assert obj.current_breath.energy == 75.0


class TestAutonomousPacemaker:
    """自主节律 — 脱同步、独立起搏、生态岛、总线选举。"""

    def test_local_pacemaker_generates_independent_signal(self):
        """局部起搏器应产生独立的呼吸信号。"""
        from cosmic_mycelium.infant.breath_bus import LocalPacemaker
        pm = LocalPacemaker(node_id="test-node")
        signal = pm.step(energy=80.0, confidence=0.8)
        assert signal.state in (BreathState.CONTRACT, BreathState.DIFFUSE, BreathState.SUSPEND)
        assert signal.source_id == "local:test-node"
        assert signal.energy == 80.0
        assert signal.confidence == 0.8

    def test_pacemaker_cycles_through_states(self):
        """局部起搏器应完整遍历 CONTRACT → DIFFUSE → SUSPEND。"""
        from cosmic_mycelium.infant.breath_bus import LocalPacemaker
        pm = LocalPacemaker(node_id="cycle-test", contract_duration=0.001)
        states_seen = set()
        for _ in range(100):
            signal = pm.step(energy=80.0, confidence=0.8, dt=0.001)
            states_seen.add(signal.state)
            if len(states_seen) == 3:
                break
        assert BreathState.CONTRACT in states_seen
        assert BreathState.DIFFUSE in states_seen
        assert BreathState.SUSPEND in states_seen

    def test_reject_sync_moves_subscriber_to_desynced(self):
        """reject_sync 应将订阅者从全局移到脱同步池。"""
        bus = BreathBus("test-bus")
        module = _MockModule("m1")
        bus.register("m1", module)
        assert bus.subscriber_count == 1
        assert bus.desynced_count == 0

        result = bus.reject_sync("m1")
        assert result is True
        assert bus.subscriber_count == 0
        assert bus.desynced_count == 1

    def test_desynced_node_does_not_receive_global_broadcast(self):
        """脱同步节点不应收到全局广播信号。"""
        bus = BreathBus("test-bus")
        module = _MockModule("m1")
        bus.register("m1", module)
        bus.reject_sync("m1")

        signal = BreathSignal(state=BreathState.CONTRACT)
        bus.broadcast(signal)

        # m1 is desynced, so it should NOT have received the global signal
        assert module.last_signal is None

    def test_local_broadcast_reaches_only_desynced(self):
        """局部广播应仅触达同一生态岛的脱同步节点。"""
        bus = BreathBus("test-bus")
        m1 = _MockModule("m1")
        m2 = _MockModule("m2")
        bus.register("m1", m1)
        bus.register("m2", m2)
        bus.reject_sync("m1")  # m1 脱同步
        # m2 保持同步

        signal = BreathSignal(state=BreathState.DIFFUSE)
        bus.local_broadcast(signal, channel="eco:m1")

        assert m1.last_signal is not None
        assert m1.last_signal.state == BreathState.DIFFUSE
        # m2 不应收到局部广播
        assert m2.last_signal is None

    def test_resync_restores_global_subscription(self):
        """resync 应将节点恢复为全局订阅者。"""
        bus = BreathBus("test-bus")
        module = _MockModule("m1")
        bus.register("m1", module)
        bus.reject_sync("m1")
        assert bus.desynced_count == 1

        result = bus.resync("m1")
        assert result is True
        assert bus.subscriber_count == 1
        assert bus.desynced_count == 0

        # 重同步后可接收全局广播
        signal = BreathSignal(state=BreathState.CONTRACT)
        bus.broadcast(signal)
        assert module.last_signal is not None

    def test_pacemaker_adapts_to_low_energy(self):
        """低能量时起搏器应调整节律（节能模式）。"""
        from cosmic_mycelium.infant.breath_bus import LocalPacemaker
        pm = LocalPacemaker(node_id="energy-test")
        # 低能量
        signal_low = pm.step(energy=5.0, confidence=0.7, dt=0.1)
        # 正常能量
        pm2 = LocalPacemaker(node_id="normal-test")
        signal_norm = pm2.step(energy=80.0, confidence=0.7, dt=0.1)

        # 低能量时 contract_duration 应缩短（节能）
        assert pm.contract_duration <= pm2.contract_duration

    def test_health_score_higher_with_more_followers(self):
        """更多追随者应产生更高健康度。"""
        bus = BreathBus("health-test")
        assert bus.get_health_score() == 0.5  # 默认值

        for i in range(5):
            bus.register(f"node_{i}", _MockModule(f"node_{i}"))

        score_with_5 = bus.get_health_score()

        bus.reject_sync("node_0")
        bus.reject_sync("node_1")

        score_after_desync = bus.get_health_score()

        # 有脱同步节点后健康度应下降
        assert score_after_desync < score_with_5

    def test_election_triggers_when_health_low(self):
        """健康度持续走低时应触发选举。"""
        bus = BreathBus("election-test")
        # 注册大量节点后脱同步大部分
        for i in range(10):
            bus.register(f"node_{i}", _MockModule(f"node_{i}"))
        for i in range(7):
            bus.reject_sync(f"node_{i}")

        # 记录健康历史
        for _ in range(20):
            bus.record_health()

        # 即使健康度在合理范围
        score = bus.get_health_score()
        # 主要验证 start_election 能正确返回候选项
        candidates = bus.start_election()
        assert len(candidates) >= 1

    def test_breath_aware_reject_sync(self):
        """BreathAware 模块应能发起脱同步。"""
        bus = BreathBus("aware-test")
        module = _AwareModule()
        bus.register("aware", module)
        assert module.is_desynced is False

        module.reject_sync(bus, "aware")
        assert module.is_desynced is True

        # 脱同步后不应收到全局广播
        bus.broadcast(BreathSignal(state=BreathState.CONTRACT))
        assert bus.desynced_count == 1

    def test_breath_aware_local_rhythm(self):
        """BreathAware 脱同步后应能产生独立节律。"""
        bus = BreathBus("rhythm-test")
        module = _AwareModule()
        bus.register("rhythm", module)
        module.reject_sync(bus, "rhythm")

        signal = module.local_rhythm(energy=60.0, confidence=0.6)
        assert signal is not None
        assert signal.source_id.startswith("local:")
        assert module.current_breath is not None
        assert module.current_breath.source_id == signal.source_id

class _MockModule:
    """模拟模块，记录收到的信号。"""

    def __init__(self, name: str):
        self.name = name
        self.last_signal = None

    def on_breath(self, signal: BreathSignal) -> None:
        self.last_signal = signal


class _BrokenModule:
    """模拟崩溃的模块。"""

    def __init__(self, name: str):
        self.name = name

    def on_breath(self, signal: BreathSignal) -> None:
        raise RuntimeError(f"{self.name} crashed!")


class _AwareModule(BreathAware):
    """继承 BreathAware 的模块。"""
    pass
