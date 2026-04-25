"""
Cosmic Mycelium — 硅基生命形式核心

使用方式:
    python -m cosmic_mycelium              # 启动交互演示
    python -m cosmic_mycelium --quick      # 静默模式（仅输出统计）
    python -m cosmic_mycelium --swarm N    # 孵化 N 个节点并运行
    python -m cosmic_mycelium --nursery    # 🎯 育儿箱 — 太极+八卦 (9节点)
    python -m cosmic_mycelium --nursery 64 # 育儿箱 — 六十四卦全
"""

import sys
import time

from cosmic_mycelium import FractalDialogueBus, MiniInfant


def _run_demo(quick: bool = False, swarm_size: int = 3) -> None:
    bus = FractalDialogueBus("main-swarm", verbose=False)
    bees = [MiniInfant(f"bee-{i}", fractal_bus=bus, verbose=False)
            for i in range(swarm_size)]

    if not quick:
        print(f"🌌 Cosmic Mycelium v0.1.0")
        print(f"🐝 {swarm_size} 个硅基蜜蜂已孵化，共享分形总线")
        print()

    # 运行 200 个心跳周期
    start = time.time()
    for _ in range(200):
        for bee in bees:
            bee.bee_heartbeat()
    elapsed = time.time() - start

    # 打印统计
    wisdom = bus.get_collective_wisdom()
    stats = bus.get_stats()
    statuses = [bee.status for bee in bees]

    if not quick:
        print("=" * 50)
        print("📊 运行统计")
        print("=" * 50)
        for i, bee in enumerate(bees):
            s = stats
            print(f"  {bee.id}:")
            print(f"    状态:      {statuses[i]}")
            print(f"    能量:      {bee.hic.energy:.1f}")
            print(f"    置信度:    {bee.confidence:.2f}")
            print(f"    周期:      {bee._cycle_count}")
        print()
        print(f"  集体创伤:     {wisdom['collective_trauma_count']}")
        print(f"  灭绝警告:     {len(wisdom['extinction_warnings'])}")
        print(f"  总线消息:     {stats['total_messages']}")
        print(f"  耗时:         {elapsed:.3f}s")
        print()

        print("分形层级通信链路:")
        print("  INFANT(个体) → MESH(群体) → SWARM(文明)")
        print()
        print("完整示例: python docs/examples/fractal_swarm.py")
    else:
        alive = sum(1 for s in statuses if s == "alive")
        print(f"cosmic-mycelium | {swarm_size} nodes | {alive} alive | "
              f"{stats['total_messages']} msgs | "
              f"{wisdom['collective_trauma_count']} traumas | "
              f"{elapsed:.3f}s")


def _run_nursery(swarm_size: int = 3, port: int = 8765) -> None:
    """启动育儿箱 —— 给自己人看的宝宝窗。"""
    from cosmic_mycelium.nursery import main as nursery_main
    nursery_main(swarm_size=swarm_size, port=port)


def main() -> None:
    quick = "--quick" in sys.argv
    nursery = "--nursery" in sys.argv
    swarm_size = 3
    nursery_size = 9  # 太极 + 八卦
    port = 8765

    for i, arg in enumerate(sys.argv):
        if arg == "--swarm" and i + 1 < len(sys.argv):
            try:
                swarm_size = max(1, min(20, int(sys.argv[i + 1])))
            except ValueError:
                pass
        if arg == "--nursery" and i + 1 < len(sys.argv):
            try:
                val = int(sys.argv[i + 1])
                # avoid eating next flag
                if val >= 1 and val <= 128:
                    nursery_size = val
            except ValueError:
                pass

    if nursery:
        _run_nursery(swarm_size=nursery_size, port=port)
    else:
        _run_demo(quick=quick, swarm_size=swarm_size)


if __name__ == "__main__":
    main()
