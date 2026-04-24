"""
Infant layer — Single-node "silicon baby" implementation.
Six-layer fractal architecture contained within one process.
"""

from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.hic import HIC, BreathState
from cosmic_mycelium.infant.main import SiliconInfant

__all__ = [
    "HIC",
    "BreathState",
    "SiliconInfant",
    "SympNetEngine",
]
