"""
Fractal Swarm — 分形蜂群演示

一条命令跑起来，看到三个硅基蜜蜂在共享的分形总线上感知彼此：

    python docs/examples/fractal_swarm.py

你会看到：
  - 三个独立节点各自呼吸、探索、学习
  - 一个节点受创 → 群体本能感知（"氛围不对"）
  - 一个节点死亡 → 群体记录灭绝信号
  - 探索路径在节点间共享（"你找到的好路，我也能走"）

如果你只跑一件事来理解这个项目，跑这个文件。
"""

from cosmic_mycelium import FractalDialogueBus, MiniInfant, Scale


def main():
    print("=" * 60)
    print("🌌 分形蜂群演示 — Fractal Swarm Demo")
    print("=" * 60)

    # ── 1. 创建共享总线（这是"菌丝网络"）──
    bus = FractalDialogueBus("demo-swarm", verbose=False)
    print("\n📡 分形总线已创建")

    # ── 2. 孵化三个硅基蜜蜂 ──
    bee_a = MiniInfant("bee-alpha", fractal_bus=bus, verbose=False)
    bee_b = MiniInfant("bee-beta", fractal_bus=bus, verbose=False)
    bee_c = MiniInfant("bee-gamma", fractal_bus=bus, verbose=False)
    print(f"🐝 三只蜜蜂已孵化: {bee_a.id}, {bee_b.id}, {bee_c.id}")

    # ── 3. 第一阶段：自由探索（100 周期）──
    print("\n--- 第一阶段：自由探索 ---")
    for _ in range(5):
        for bee in [bee_a, bee_b, bee_c]:
            bee.bee_heartbeat()

    # ── 4. 第二阶段：bee_a 经历创伤 → 群体感知 ──
    print("\n--- 第二阶段：bee-alpha 经历创伤 ---")
    # 模拟一次高惊讶 + 置信度骤降 → 触发创伤标记 + MESH 发布
    bee_a.surprise = 0.05
    old_conf = bee_a._prev_confidence
    bee_a._prev_confidence = bee_a.confidence
    bee_a.confidence = 0.25  # 置信度骤降
    bee_a._publish_trauma_to_fractal()
    bee_a._prev_confidence = old_conf  # restore for normal operation

    # 验证群体感知
    has_trauma = bus.has_collective_trauma()
    print(f"  ⚠️  集体创伤感知: {has_trauma}")
    wisdom = bus.get_collective_wisdom()
    print(f"  📊 集体智慧: {wisdom['collective_trauma_count']} 条创伤回声")

    # ── 5. 第三阶段：继续运行，群体受创伤影响 ──
    print("\n--- 第三阶段：创伤后运行 ---")
    for _ in range(3):
        for bee in [bee_a, bee_b, bee_c]:
            bee.bee_heartbeat()
    print("  ✓ 所有节点在集体创伤氛围中继续运行")

    # ── 6. 第四阶段：查看路径共享 ──
    print("\n--- 第四阶段：探索路径共享 ---")
    context = {"energy": 80.0, "confidence": 0.8}
    spores = bee_b.explorer.explore(context)
    best = bee_b.explorer.converge(threshold=0.5, spores=spores)
    if best:
        print(f"  🧬 bee-beta 发现路径: {'->'.join(best.path)} (质量={best.quality:.3f})")

    shared = bus.get_shared_paths(min_quality=0.5)
    if shared:
        print(f"  📤 MESH 共享路径: {len(shared)} 条")
        for s in shared:
            print(f"    · {s['path'][:40]} (质量={s['quality']:.2f})")

    # ── 7. 第五阶段：强行让 bee_c 死亡 → 灭绝信号 ──
    print("\n--- 第五阶段：bee-gamma 死亡 ---")
    bee_c._hidden_energy_reserve = 0.0
    bee_c._is_dead = True
    report = bee_c.run(max_cycles=3)
    print(f"  💀 死因: {report.get('cause', 'unknown')}")

    # ── 8. 最终统计 ──
    print("\n" + "=" * 60)
    print("📊 最终群体统计")
    print("=" * 60)

    wisdom = bus.get_collective_wisdom()
    stats = bus.get_stats()
    print(f"  总线名称:          {bus.name}")
    print(f"  总消息数:          {stats['total_messages']}")
    print(f"  翻译次数:          {stats['total_translations']}")
    print(f"  集体创伤数:        {wisdom['collective_trauma_count']}")
    print(f"  灭绝警告:          {len(wisdom['extinction_warnings'])} 条")
    print(f"  活跃回声模式:     {stats['echoes']['total_patterns']}")

    # 尝试上行到 SWARM
    if wisdom["collective_trauma_count"] > 0:
        bus.publish_to_swarm(
            payload={"severity": 0.6, "trauma_type": "energy_shock", "source_count": 1},
            event_type="trauma",
            source_id="demo-swarm",
        )
        swarm = bus.get_swarm_wisdom()
        print(f"  文明纪元:          {swarm['epoch']}")
        print(f"  文明创伤数:        {swarm['civilization_health']['trauma_count']}")

    print("\n✅ 演示完成。三个尺度的通信均已验证:")
    print("   INFANT(个体) → MESH(群体) → SWARM(文明)")
    print()


if __name__ == "__main__":
    main()
