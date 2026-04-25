"""
Infant layer — Single-node "silicon baby" implementation.

这是"硅基蜜蜂"层。每个 MiniInfant 就是一个独立个体，
有自己的物理直觉 (SympNet)、能量管理 (HIC)、探索策略 (SlimeExplorer)
和记忆系统 (MyelinationMemory)。多个个体通过 FractalDialogueBus
连接成群体智能。

快速上手:
    from cosmic_mycelium.infant import MiniInfant, FractalDialogueBus

    bus = FractalDialogueBus("my-swarm")
    a = MiniInfant("bee-a", fractal_bus=bus)
    b = MiniInfant("bee-b", fractal_bus=bus)
    a.run(max_cycles=100)
    b.run(max_cycles=100)
    print(bus.get_collective_wisdom())
"""

from cosmic_mycelium.infant.breath_bus import BreathBus, BreathSignal
from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.fossil import FossilLayer, FossilRecord
from cosmic_mycelium.infant.fractal_bus import FractalDialogueBus
from cosmic_mycelium.infant.hic import BreathState, HIC
from cosmic_mycelium.infant.learning import ContinualLearner
from cosmic_mycelium.infant.mini import MiniInfant

__all__ = [
    "BreathBus",
    "BreathSignal",
    "BreathState",
    "ContinualLearner",
    "FossilLayer",
    "FossilRecord",
    "FractalDialogueBus",
    "HIC",
    "MiniInfant",
    "SiliconInfant",
    "SlimeExplorer",
    "SympNetEngine",
]


def __getattr__(name: str):
    """Lazy import: SiliconInfant 仅在首次访问时加载。"""
    if name == "SiliconInfant":
        from cosmic_mycelium.infant.main import SiliconInfant as si
        return si
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
