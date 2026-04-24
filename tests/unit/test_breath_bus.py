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


# ── Mock 辅助 ───────────────────────────────────────────────────────

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
