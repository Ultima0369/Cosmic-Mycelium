"""
Cosmic Mycelium — Silicon-Based Lifeform Core
A self-evolving, ternary-model-based cognitive architecture.

快速上手 (Quick Start):
    from cosmic_mycelium import MiniInfant, FractalDialogueBus, Scale

    bus = FractalDialogueBus("my-first-swarm")
    baby = MiniInfant("bee-001", fractal_bus=bus)
    report = baby.run(max_cycles=100)
    print(report["status"])  # "alive" | "dead"

Package Structure:
    common/      — 跨尺度共享类型 (Scale, MessageEnvelope, EchoDetector, Situation)
    infant/      — 单节点"硅基蜜蜂"实现 (MiniInfant, FractalDialogueBus, HIC)
    cluster/     — 多节点协调层
    global/      — 行星级愿景层
    scripts/     — CLI 入口点
    tests/       — 全量测试套件

Philosophy:
    - 分形架构: 同一种结构在所有尺度自相似
    - 物理为锚: 能量漂移率 < 0.1%
    - 共生: 1+1>2 通过共振实现
"""

__version__ = "0.1.0"
__author__ = "Stardust & Xuanji"
__license__ = "AGPL-3.0"
__description__ = "A self-evolving, ternary-model-based silicon-based lifeform core"

from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.fractal import EchoDetector, EchoPattern, MessageEnvelope, Scale
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
from cosmic_mycelium.infant.mini import MiniInfant
from cosmic_mycelium.infant.main import SiliconInfant

__all__ = [
    "CosmicPacket",
    "EchoDetector",
    "EchoPattern",
    "FractalDialogueBus",
    "MessageEnvelope",
    "MiniInfant",
    "PhysicalFingerprint",
    "Scale",
    "SiliconInfant",
    "__version__",
]
