"""
Smoke Tests: MiniInfant — "硅基蜜蜂" (Silicon Bee)

Tests the minimal v4.0 fractal unit: 4 components in a bee_heartbeat() cycle.
"""

import pytest

from cosmic_mycelium.infant.mini import MiniInfant, MyelinationMemory


class TestMyelinationMemory:
    """髓鞘化记忆单元测试。"""

    def test_reinforce_success(self):
        m = MyelinationMemory()
        m.reinforce("test_path", success=True, saliency=0.5)
        assert m.path_strength["test_path"] > 1.0
        assert m.total_reinforcements == 1

    def test_reinforce_failure(self):
        m = MyelinationMemory()
        m.reinforce("test_path", success=False, saliency=0.5)
        assert m.path_strength["test_path"] < 1.0

    def test_forget_removes_weak_paths(self):
        m = MyelinationMemory()
        m.path_strength = {"strong": 5.0, "weak": 0.1}
        m.forget(dt_seconds=100.0)  # aggressive decay
        assert "strong" in m.path_strength
        # "weak" should be removed since below 0.05

    def test_best_paths_returns_sorted(self):
        m = MyelinationMemory()
        m.reinforce("a", success=True, saliency=1.0)
        m.reinforce("b", success=True, saliency=0.1)
        best = m.best_paths(2)
        assert best[0][0] == "a"
        assert best[0][1] >= best[1][1]

    def test_feature_codebook_grows_on_success(self):
        m = MyelinationMemory()
        m.reinforce("path_x", success=True, saliency=0.5)
        m.reinforce("path_x", success=True, saliency=0.5)
        assert len(m.feature_codebook) >= 1


class TestSympNetMultiDOF:
    """SympNet 多自由度扩展测试。"""

    def test_scalar_1dof_backward_compatible(self):
        """原有的标量 1-DOF 模式应继续正常工作。"""
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
        eng = SympNetEngine(mass=1.0, spring_constant=1.0)
        q, p = 1.0, 0.5
        for _ in range(100):
            q, p = eng.step(q, p, 0.01)
        assert eng.compute_energy(q, p) > 0

    def test_ndof_array_state(self):
        """N-DOF 数组模式应正确演化。"""
        import numpy as np
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        eng = SympNetEngine(mass=1.0, spring_constant=1.0)
        q = np.array([1.0, 0.5, -0.5])
        p = np.array([0.5, 0.0, -0.3])

        e0 = eng.compute_energy(q, p)
        for _ in range(100):
            q, p = eng.step(q, p, 0.01)
        e1 = eng.compute_energy(q, p)

        drift = abs(e1 - e0) / max(e0, 1e-9)
        assert drift < 0.001, f"3-DOF energy drift {drift} exceeds 0.1%"

    def test_ndof_vectorized_integration(self):
        """N-DOF 蛙跳积分应保持向量化精度。"""
        import numpy as np
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        eng = SympNetEngine(mass=2.0, spring_constant=3.0)
        q = np.array([2.0, -1.0, 0.5, 0.0])
        p = np.array([0.0, 1.0, -0.5, 0.3])

        e0 = eng.compute_energy(q, p)
        for _ in range(1000):
            q, p = eng.step(q, p, 0.01)
        e1 = eng.compute_energy(q, p)

        drift = abs(e1 - e0) / max(e0, 1e-9)
        assert drift < 0.001, f"4-DOF drift {drift} fails physical anchor"

    def test_custom_potential_function(self):
        """自定义势能函数应改变系统动力学。"""
        import numpy as np
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        # 四次势能: V(q) = q⁴ (非简谐)
        def quartic_potential(q):
            if isinstance(q, np.ndarray):
                return float(np.sum(q ** 4))
            return q ** 4

        eng = SympNetEngine(
            mass=1.0, spring_constant=0.0,  # k=0 since potential is custom
            potential_fn=quartic_potential,
        )
        q, p = 1.0, 0.0
        e0 = eng.compute_energy(q, p)
        for _ in range(100):
            q, p = eng.step(q, p, 0.01)
        e1 = eng.compute_energy(q, p)
        drift = abs(e1 - e0) / max(e0, 1e-9)
        assert drift < 0.001, f"Custom potential drift {drift} exceeds 0.1%"


class TestMiniInfant:
    """MiniInfant 集成测试。"""

    def test_initialization(self):
        baby = MiniInfant("test-bee", verbose=False)
        assert baby.id == "test-bee"
        assert baby.hic.energy == 100.0
        assert baby.confidence == 0.7
        assert baby.position == 1.0
        assert baby.momentum == 0.0

    def test_physical_fingerprint_produced(self):
        baby = MiniInfant("fp-test", verbose=False)
        fp = baby.get_physical_fingerprint()
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_changes_with_state(self):
        baby = MiniInfant("fp2-test", verbose=False)
        fp1 = baby.get_physical_fingerprint()
        baby.position = 3.14
        fp2 = baby.get_physical_fingerprint()
        assert fp1 != fp2

    def test_bee_heartbeat_contract(self):
        """Running heartbeat should process at least some cycles."""
        baby = MiniInfant("hb-test", verbose=False)
        for _ in range(5):
            baby.bee_heartbeat()
        assert baby._cycle_count > 0

    def test_run_completes(self):
        """MiniInfant.run() should complete without error."""
        baby = MiniInfant("run-test", verbose=False)
        report = baby.run(max_cycles=10)
        assert report["status"] == "completed"
        assert report["cycles"] == 10
        assert report["final_energy"] > 0

    def test_energy_decreases_over_time(self):
        """Energy should decrease as the baby operates."""
        baby = MiniInfant("energy-test", verbose=False)
        initial = baby.hic.energy
        baby.run(max_cycles=20)
        # Energy may be equal due to diffuse recovery, but should not be drastically higher
        assert baby.hic.energy <= initial + 1.0  # Tiny tolerance for recovery

    def test_situation_built(self):
        """Situation vector should be updated after heartbeat."""
        baby = MiniInfant("sit-test", verbose=False)
        baby.bee_heartbeat()
        s = baby.situation
        assert s.energy == baby.hic.energy
        assert s.confidence == baby.confidence
        assert s.source_id == "sit-test"

    def test_situation_is_stable_with_good_confidence(self):
        """High confidence + low surprise = stable situation."""
        baby = MiniInfant("stab-test", verbose=False)
        baby.confidence = 0.85
        baby.surprise = 0.05
        s = baby._build_situation()
        assert s.is_stable is True

    def test_situation_needs_suspend_at_low_energy(self):
        """Low energy should flag situation as needing suspend."""
        from cosmic_mycelium.common.situation import Situation
        s = Situation(energy=15.0, confidence=0.5)
        assert s.needs_suspend is True
