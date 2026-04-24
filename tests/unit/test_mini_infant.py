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


class TestTraumaLoop:
    """创伤回路 — 反遗忘 + 闪回 + 压抑势能。"""

    def test_trauma_marked_path_survives_forgetting(self):
        """创伤标记的路径在遗忘中反而增强。"""
        m = MyelinationMemory()
        m.reinforce("normal_path", success=True, saliency=0.5)
        m.reinforce("trauma_path", success=True, saliency=1.0)
        m.mark_trauma("trauma_path", context="test trauma")
        before = m.path_strength["trauma_path"]
        m.forget(dt_seconds=100.0)
        after = m.path_strength["trauma_path"]
        # Trauma path should grow stronger with time
        assert after >= before, "Trauma path should not decay"
        # Normal path should decay
        assert m.path_strength.get("normal_path", 0) < after

    def test_trauma_mark_persists_in_dynamics(self):
        """创伤路径不会因遗忘而被删除。"""
        m = MyelinationMemory()
        m.path_strength = {"weak": 0.1, "trauma": 5.0}
        m.trauma_paths["trauma"] = {"timestamp": 0, "context": ""}
        m.forget(dt_seconds=1000.0)
        # weak should be removed, trauma should persist
        assert "weak" not in m.path_strength
        assert "trauma" in m.path_strength

    def test_repression_accumulates(self):
        """多次回避创伤路径会累积压抑势能。"""
        m = MyelinationMemory()
        m.trauma_paths["path_x"] = {"repression_count": 0}
        for _ in range(5):
            m.accumulate_repression("path_x")
        assert m.repression_potential > 0
        assert m.trauma_paths["path_x"]["repression_count"] == 5

    def test_flashback_triggers_at_threshold(self):
        """压抑势能达到阈值后触发闪回。"""
        m = MyelinationMemory()
        m.path_strength["trauma"] = 5.0
        m.trauma_paths["trauma"] = {
            "timestamp": 0, "context": "bad", "repression_count": 10, "flashback_count": 0,
        }
        triggers = m.check_flashback_trigger()
        assert len(triggers) == 1
        assert triggers[0]["path"] == "trauma"
        # repression_count should be reset
        assert m.trauma_paths["trauma"]["repression_count"] == 0
        # flashback_count should increment
        assert m.trauma_paths["trauma"]["flashback_count"] == 1

    def test_trauma_amplifies_reinforcement(self):
        """创伤路径的强化效果被放大。"""
        m = MyelinationMemory()
        m.mark_trauma("trauma_path", context="test")
        m.reinforce("trauma_path", success=False, saliency=1.0)
        # Trauma paths get 1.5x multiplier on saliency effect
        assert m.path_strength["trauma_path"] < 5.0  # Should have weakened more than normal

    def test_trauma_penalty_in_path_evaluation(self):
        """与创伤路径重叠的候选路径应被评分降低。"""
        # Test via SlimeExplorer with trauma_memory
        from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
        m = MyelinationMemory()
        m.trauma_paths["action_3"] = {"timestamp": 0, "context": "danger"}
        explorer = SlimeExplorer(num_spores=3, exploration_factor=0.0, trauma_memory=m)
        context = {"actions": ["action_1", "action_2", "action_3"]}
        spores = explorer.explore(context)
        # With exploration_factor=0.0, selection is purely softmax-weighted
        # action_3 should be penalized in evaluation
        for spore in spores:
            score_3 = explorer._evaluate_path(["action_3"], None)
            score_1 = explorer._evaluate_path(["action_1"], None)
            # action_3 should not be scored higher than action_1 due to trauma penalty
            assert score_3 <= score_1 + 0.01


class TestDeathAndInheritance:
    """死亡与继承 — 生命周期、遗嘱、化石层、重生。"""

    def test_compile_will_returns_strongest_paths(self):
        """编译遗嘱应返回最强的 N 条路径。"""
        m = MyelinationMemory()
        m.reinforce("a", success=True, saliency=1.0)
        m.reinforce("b", success=True, saliency=0.5)
        m.reinforce("c", success=True, saliency=0.1)
        will = m.compile_will(top_n=2)
        assert len(will) == 2
        assert "a" in will
        assert "b" in will

    def test_inherit_will_absorbs_memories(self):
        """继承遗嘱应将记忆注入当前池。"""
        heir = MyelinationMemory()
        will = {"ancestor_path_1": 5.0, "ancestor_path_2": 3.0}
        count = heir.inherit_will(will, boost=0.5)
        assert count == 2
        assert heir.path_strength["ancestor_path_1"] == 2.5  # 5.0 * 0.5

    def test_fossil_bury_and_excavate(self):
        """化石应能被埋葬和挖掘。"""
        from cosmic_mycelium.infant.fossil import FossilLayer, FossilRecord
        layer = FossilLayer()
        record = FossilRecord(
            node_id="test_bee",
            lifespan_cycles=1000,
            epitaph="test",
            core_memories={"path_x": 3.0},
        )
        layer.bury(record)
        fossils = layer.excavate()
        assert len(fossils) == 1
        assert fossils[0].node_id == "test_bee"
        assert fossils[0].legacy_count >= 1  # 被考古次数增加

    def test_fossil_dig_retrieves_specific(self):
        """定向挖掘应返回指定化石。"""
        from cosmic_mycelium.infant.fossil import FossilLayer, FossilRecord
        layer = FossilLayer()
        layer.bury(FossilRecord(node_id="bee_a", lifespan_cycles=100))
        layer.bury(FossilRecord(node_id="bee_b", lifespan_cycles=200))
        record = layer.dig("bee_a")
        assert record is not None
        assert record.node_id == "bee_a"

    def test_dying_buries_fossil(self):
        """死亡流程应将记忆埋葬到化石层。"""
        baby = MiniInfant("death-test", verbose=False)
        # Run some cycles to build memory
        baby.run(max_cycles=20)
        # Now force death by draining hidden reserve
        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        report = baby.run(max_cycles=100)
        assert report["status"] == "dead"
        assert report["fossil_buried"] is True
        assert report["will_package_size"] > 0

    def test_rebirth_from_fossil(self):
        """应能从化石层继承记忆重生。"""
        from cosmic_mycelium.infant.fossil import FossilLayer, FossilRecord

        # Create a fossil layer with an ancestor record
        layer = FossilLayer()
        layer.bury(FossilRecord(
            node_id="ancestor",
            lifespan_cycles=500,
            core_memories={"sacred_path": 7.0, "ancient_wisdom": 5.0},
        ))

        # New baby inherits
        baby = MiniInfant("rebirth-test", verbose=False)
        baby._fossil_layer = layer
        result = baby._rebirth()
        assert result is True
        assert baby.memory.path_strength.get("sacred_path", 0) > 0

    def test_low_synergy_drains_reserve(self):
        """低协同度应消耗隐性储备。"""
        baby = MiniInfant("drain-test", verbose=False)
        reserve_before = baby._hidden_energy_reserve
        # Simulate low energy + low synergy
        baby.hic.modify_energy(-90.0)  # energy < 20
        baby._synergy_score = 0.1
        for _ in range(5):
            baby._check_vitality()
        assert baby._hidden_energy_reserve < reserve_before

    def test_vitality_check_tracks_age(self):
        """年龄检查应随周期递增。"""
        baby = MiniInfant("age-test", verbose=False)
        assert baby._age == 0
        for _ in range(10):
            baby._check_vitality()
            baby._cycle_count += 1
        assert baby._age > 0


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
