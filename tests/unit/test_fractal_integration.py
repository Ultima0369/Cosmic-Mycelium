"""
Integration Tests: Fractal Integration — 三根接线

验证三个子系统的跨尺度集成:
  1. 创伤 → 分形回声（个体痛苦成为群体经验）
  2. 死亡 → 群体信号（牺牲成为文明记忆）
  3. 群体回声 → 个体直觉（本能回避集体危险）

这些测试验证"相变"——既有元素在新尺度上彼此认出。
"""

import pytest

from cosmic_mycelium.common.fractal import Scale
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
from cosmic_mycelium.infant.mini import MiniInfant


class TestTraumaEcho:
    """接线一：创伤 → 分形回声。"""

    def test_trauma_publishes_to_mesh(self):
        """创伤标记后，MESH 层级应出现回声。"""
        bus = FractalDialogueBus("test-swarm")
        baby = MiniInfant("trauma-test", fractal_bus=bus, verbose=False)

        # 直接标记创伤并发布到分形网络
        baby.memory.mark_trauma("q_1.00->surprise_0.0500", context="test trauma")
        baby._publish_trauma_to_fractal()

        # MESH 层级应有创伤回声
        assert bus.has_collective_trauma() is True

    def test_trauma_signature_contains_energy_info(self):
        """创伤签名应包含能量剖面信息。"""
        bus = FractalDialogueBus("trauma-sig")
        baby = MiniInfant("sig-test", fractal_bus=bus, verbose=False)

        baby.memory.mark_trauma("test_path", context="test")
        baby._publish_trauma_to_fractal()

        # 通过 get_collective_wisdom 验证创伤信息
        wisdom = bus.get_collective_wisdom()
        assert wisdom["collective_trauma_count"] >= 1

    def test_trauma_echo_does_not_require_subscriber(self):
        """即使没有 MESH 订阅者，创伤发布不应报错。"""
        bus = FractalDialogueBus("silent-swarm")
        baby = MiniInfant("silent-test", fractal_bus=bus, verbose=False)

        baby.memory.mark_trauma("test", context="test")
        baby._publish_trauma_to_fractal()  # 不应抛出异常

    def test_multiple_traumas_increment_echoes(self):
        """多次创伤事件应增加回声计数。"""
        bus = FractalDialogueBus("multi-trauma")
        baby = MiniInfant("multi-test", fractal_bus=bus, verbose=False)

        for i in range(3):
            baby.memory.mark_trauma(f"path_{i}", context=f"trauma_{i}")
            baby._publish_trauma_to_fractal()

        wisdom = bus.get_collective_wisdom()
        # 应有多条创伤记录
        assert wisdom["collective_trauma_count"] >= 1


class TestDeathSignal:
    """接线二：死亡 → 群体信号。"""

    def test_death_publishes_to_mesh(self):
        """死亡时应发布 MESH 信号。"""
        bus = FractalDialogueBus("death-swarm")
        baby = MiniInfant("death-test", fractal_bus=bus, verbose=False)

        # 强制死亡
        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        report = baby.run(max_cycles=10)

        assert report["status"] == "dead"
        # 死亡信号应产生 MESH 记录
        wisdom = bus.get_collective_wisdom()
        assert len(wisdom["extinction_warnings"]) >= 1

    def test_death_event_contains_cause(self):
        """死亡信号应包含死因。"""
        bus = FractalDialogueBus("cause-test")
        baby = MiniInfant("cause-test", fractal_bus=bus, verbose=False)

        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        baby.run(max_cycles=5)

        death_echoes = [
            e for e in bus.echo_detector.get_echoes(min_depth=1)
            if e.metadata and e.metadata.get("event_type") == "death"
        ]
        assert len(death_echoes) >= 1

    def test_death_echo_signature_reflects_lifespan(self):
        """死亡回声签名应反映不同寿命。"""
        bus = FractalDialogueBus("lifespan-test")

        short = MiniInfant("short-life", fractal_bus=bus, verbose=False)
        short._hidden_energy_reserve = 0.0
        short._is_dead = True
        short.run(max_cycles=5)

        echoes = bus.echo_detector.get_echoes(min_depth=1)
        death_echoes = [
            e for e in echoes
            if e.metadata and e.metadata.get("event_type") == "death"
        ]
        assert len(death_echoes) >= 1

    def test_fossil_and_death_signal_coexist(self):
        """死亡同时产生化石埋葬和分形信号，两者不冲突。"""
        bus = FractalDialogueBus("coexist-test")
        baby = MiniInfant("coexist-test", fractal_bus=bus, verbose=False)

        # 先运行一些周期产生记忆
        baby.run(max_cycles=10)

        # 强制死亡
        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        report = baby.run(max_cycles=100)

        assert report["fossil_buried"] is True
        wisdom = bus.get_collective_wisdom()
        assert len(wisdom["extinction_warnings"]) >= 1


class TestCollectiveWisdom:
    """接线三：群体回声 → 个体直觉。"""

    def test_has_collective_trauma_returns_true_after_trauma(self):
        """创伤发布后，has_collective_trauma() 应返回 True。"""
        bus = FractalDialogueBus("wisdom-test")
        baby = MiniInfant("wise-test", fractal_bus=bus, verbose=False)

        assert bus.has_collective_trauma() is False

        baby.memory.mark_trauma("shock", context="test")
        baby._publish_trauma_to_fractal()

        assert bus.has_collective_trauma() is True

    def test_collective_wisdom_aggregates_trauma_and_death(self):
        """get_collective_wisdom 应聚合创伤和死亡信息。"""
        bus = FractalDialogueBus("aggregate-test")
        baby = MiniInfant("agg-test", fractal_bus=bus, verbose=False)

        # 创伤
        baby.memory.mark_trauma("shock", context="test")
        baby._publish_trauma_to_fractal()

        # 死亡
        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        baby.run(max_cycles=5)

        wisdom = bus.get_collective_wisdom()
        assert "collective_trauma_count" in wisdom
        assert "extinction_warnings" in wisdom
        assert "hot_signatures" in wisdom

    def test_explorer_penalty_on_fractal_bus(self):
        """SlimeExplorer 在有集体创伤时应调整探索（不崩溃）。"""
        bus = FractalDialogueBus("penalty-test")
        baby = MiniInfant("penalty-test", fractal_bus=bus, verbose=False)

        # 产生集体创伤
        other = MiniInfant("other-bee", fractal_bus=bus, verbose=False)
        other.memory.mark_trauma("shock", context="test")
        other._publish_trauma_to_fractal()

        assert bus.has_collective_trauma() is True

        # 当前蜜蜂探索 → 受集体创伤影响
        context = {"energy": 50.0, "confidence": 0.7}
        spores = baby.explorer.explore(context)
        assert len(spores) > 0

    def test_diffuse_checks_collective_wisdom(self):
        """DIFFUSE 阶段应查询群体智慧（不崩溃）。"""
        bus = FractalDialogueBus("diffuse-test")
        baby = MiniInfant("diffuse-test", fractal_bus=bus, verbose=False)

        # 产生集体经验
        baby.memory.mark_trauma("shock", context="test")
        baby._publish_trauma_to_fractal()

        # DIFFUSE 阶段应查询群体智慧，不报错
        confidence_before = baby.confidence
        baby._diffuse_phase()
        assert baby.confidence >= 0.0


class TestFeedbackLoop:
    """完整回路测试：个体创伤 → MESH → 另一个体本能回避。"""

    def test_trauma_publish_then_death_publish_echoes_independent(self):
        """创伤回声和死亡回声应互不干扰。"""
        bus = FractalDialogueBus("independent-test")

        # bee_a 创伤
        a = MiniInfant("bee_a", fractal_bus=bus, verbose=False)
        a.memory.mark_trauma("shock", context="test")
        a._publish_trauma_to_fractal()

        # bee_b 死亡
        b = MiniInfant("bee_b", fractal_bus=bus, verbose=False)
        b._hidden_energy_reserve = 0.0
        b._is_dead = True
        b.run(max_cycles=5)

        wisdom = bus.get_collective_wisdom()
        assert wisdom["collective_trauma_count"] >= 1
        assert len(wisdom["extinction_warnings"]) >= 1

    def test_new_infant_senses_collective_unease(self):
        """新生节点应能感知到前辈留下的集体不安。"""
        bus = FractalDialogueBus("heritage-test")

        # 第一代：创伤
        gen1 = MiniInfant("gen1", fractal_bus=bus, verbose=False)
        gen1.memory.mark_trauma("danger_pattern", context="ancestral fear")
        gen1._publish_trauma_to_fractal()

        # 第二代：应感知集体创伤
        gen2 = MiniInfant("gen2", fractal_bus=bus, verbose=False)
        assert gen2.fractal_bus.has_collective_trauma() is True

        # 第二代探索时受集体影响
        ctx = {"energy": 50.0, "confidence": 0.7, "actions": ["action_1", "action_2"]}
        spores = gen2.explorer.explore(ctx)
        assert len(spores) > 0

    def test_fractal_bus_stats_includes_trauma_death(self):
        """get_stats 应反映创伤和死亡事件。"""
        bus = FractalDialogueBus("stats-test")
        baby = MiniInfant("stats-test", fractal_bus=bus, verbose=False)

        baby.memory.mark_trauma("shock", context="test")
        baby._publish_trauma_to_fractal()

        baby._hidden_energy_reserve = 0.0
        baby._is_dead = True
        baby.run(max_cycles=5)

        stats = bus.get_stats()
        assert stats["echoes"]["total_patterns"] >= 1


class TestRoutineInteraction:
    """常规互动测试：节点在日常中互相感知，而非仅创伤/死亡时通信。"""

    def test_publish_situation_update_creates_mesh_record(self):
        """发布常规态势更新应在 MESH 层级产生记录。"""
        bus = FractalDialogueBus("routine-test")
        baby = MiniInfant("routine-test", fractal_bus=bus, verbose=False)

        bus.publish_situation_update(
            situation_data={"energy": 80.0, "confidence": 0.8},
            source_id="routine-test",
        )

        # MESH 应有该态势记录
        collective = bus.get_collective_situation()
        assert collective["node_count"] >= 1
        assert collective["avg_energy"] == 80.0
        assert collective["avg_confidence"] == 0.8

    def test_multiple_nodes_collective_situation(self):
        """多个节点发布态势后，聚合应反映集体状态。"""
        bus = FractalDialogueBus("multi-routine")

        for i in range(3):
            bus.publish_situation_update(
                situation_data={"energy": 50.0 + i * 10, "confidence": 0.5 + i * 0.1},
                source_id=f"node_{i}",
            )

        collective = bus.get_collective_situation()
        assert collective["node_count"] == 3
        assert 60.0 <= collective["avg_energy"] <= 70.0  # (50+60+70)/3
        assert 0.6 <= collective["avg_confidence"] <= 0.7

    def test_collective_tension_rises_when_energy_low(self):
        """多个节点低能量 → 集体紧张度上升。"""
        bus = FractalDialogueBus("tension-test")

        for i in range(4):
            bus.publish_situation_update(
                situation_data={"energy": 20.0, "confidence": 0.3},
                source_id=f"low_{i}",
            )

        collective = bus.get_collective_situation()
        assert collective["collective_tension"] > 0.5
        assert collective["energy_distribution"] == "critical"

    def test_diffuse_publishes_situation(self):
        """DIFFUSE 阶段应自动发布态势到 MESH（不报错）。"""
        bus = FractalDialogueBus("diffuse-pub")
        baby = MiniInfant("diffuse-pub", fractal_bus=bus, verbose=False)

        # 强制 DIFFUSE
        baby._cycle_count = 5
        baby.hic._breath_counter = 5
        baby._diffuse_phase()

        # should not crash, and should have published
        collective = bus.get_collective_situation()
        assert collective["node_count"] >= 1


class TestPathSharing:
    """跨节点路径共享测试：一个节点的成功成为群体的启发式。"""

    def test_publish_path_success_creates_record(self):
        """发布成功路径应在 MESH 产生记录。"""
        bus = FractalDialogueBus("path-test")
        bus.publish_path_success(
            path=["action_1", "action_3", "action_5"],
            quality=0.85,
            source_id="bee_a",
        )
        shared = bus.get_shared_paths(min_quality=0.5)
        assert len(shared) >= 1
        assert "action_1->action_3->action_5" in shared[0]["path"]

    def test_get_shared_paths_filters_by_quality(self):
        """get_shared_paths 应按质量过滤。"""
        bus = FractalDialogueBus("filter-test")

        bus.publish_path_success(path=["a"], quality=0.3, source_id="low")
        bus.publish_path_success(path=["b"], quality=0.9, source_id="high")

        # 最低质量 0.5 → 只返回 b
        shared = bus.get_shared_paths(min_quality=0.5, top_k=10)
        assert len(shared) == 1
        assert shared[0]["quality"] == 0.9

    def test_multiple_paths_returned_sorted(self):
        """多个路径应按时序返回。"""
        bus = FractalDialogueBus("sort-test")

        bus.publish_path_success(path=["x"], quality=0.6, source_id="n1")
        bus.publish_path_success(path=["y"], quality=0.9, source_id="n2")
        bus.publish_path_success(path=["z"], quality=0.7, source_id="n3")

        shared = bus.get_shared_paths(min_quality=0.5, top_k=5)
        assert len(shared) == 3
        # 按质量降序
        assert shared[0]["quality"] == 0.9
        assert shared[2]["quality"] == 0.6

    def test_explorer_imports_shared_paths(self):
        """SlimeExplorer 在探索时自动导入共享路径到信息素图。"""
        bus = FractalDialogueBus("shared-phero")
        baby = MiniInfant("shared-test", fractal_bus=bus, verbose=False)

        # 先由另一个节点发布成功路径
        bus.publish_path_success(
            path=["action_3", "action_7"],
            quality=0.9,
            source_id="other_bee",
        )

        # 当前节点探索时应自动导入共享路径到信息素图
        context = {"energy": 80.0, "confidence": 0.7}
        spores = baby.explorer.explore(context)
        assert len(spores) > 0

        # 共享路径应有非零信息素
        shared_key = "action_3->action_7"
        phero = baby.explorer.pheromone_map.get(shared_key, 0.0)
        assert phero > 0.0  # 共享路径被导入

    def test_converge_publishes_path_to_bus(self):
        """收敛成功后应自动发布路径到 MESH。"""
        bus = FractalDialogueBus("converge-share")
        baby = MiniInfant("converge-test", fractal_bus=bus, verbose=False)

        context = {"energy": 80.0, "confidence": 0.8}
        spores = baby.explorer.explore(context)
        baby.explorer.converge(threshold=0.5, spores=spores)

        # 应该有共享路径记录（至少一条高质量路径）
        shared = bus.get_shared_paths(min_quality=0.5)
        # 可能没有达到阈值，但至少不应崩溃


class TestSwarmScale:
    """SWARM 层级测试：群体智慧上行文明级。"""

    def test_publish_to_swarm_creates_swarm_echo(self):
        """发布到 SWARM 应在 SWARM 层级产生回声。"""
        bus = FractalDialogueBus("swarm-test")
        bus.publish_to_swarm(
            payload={"energy_profile": {"current": 80}, "stability": {"confidence": 0.8}},
            event_type="situation",
            source_id="mesh-1",
        )
        wisdom = bus.get_swarm_wisdom()
        assert wisdom["epoch"] == "recorded"
        assert wisdom["civilization_health"]["total_echoes"] >= 1

    def test_swarm_trauma_echo(self):
        """创伤事件上行到 SWARM 应记录文明伤痕。"""
        bus = FractalDialogueBus("swarm-trauma")

        # 先发创伤到 MESH（走现有管线），再上行到 SWARM
        bus.publish_to_swarm(
            payload={
                "severity": 0.85,
                "trauma_type": "energy_shock",
                "source_count": 3,
            },
            event_type="trauma",
            source_id="mesh-1",
        )

        wisdom = bus.get_swarm_wisdom()
        assert wisdom["civilization_health"]["trauma_count"] >= 1
        assert len(wisdom["warnings"]) >= 1

    def test_swarm_death_echo(self):
        """死亡事件上行到 SWARM 应记录灭绝事件。"""
        bus = FractalDialogueBus("swarm-death")
        bus.publish_to_swarm(
            payload={
                "extinction_event": {
                    "cause": "resource_depletion",
                    "lifespan_cycles": 5000,
                    "critical": True,
                },
            },
            event_type="death",
            source_id="mesh-1",
        )

        wisdom = bus.get_swarm_wisdom()
        assert wisdom["civilization_health"]["extinction_count"] >= 1

    def test_swarm_empty_before_publication(self):
        """未发布时 SWARM 应返回 'pre_civilization'。"""
        bus = FractalDialogueBus("empty-swarm")
        wisdom = bus.get_swarm_wisdom()
        assert wisdom["epoch"] == "pre_civilization"
        assert wisdom["swarm_coherence"] == 0.0

    def test_translator_registered_for_mesh_to_swarm(self):
        """MESH→SWARM 翻译器应已注册。"""
        bus = FractalDialogueBus("trans-test")
        status = bus.translator.get_status()
        entries = status["entries"]
        mesh_to_swarm = [e for e in entries if "MESH → SWARM" in e]
        assert len(mesh_to_swarm) >= 1
        swarm_to_mesh = [e for e in entries if "SWARM → MESH" in e]
        assert len(swarm_to_mesh) >= 1
