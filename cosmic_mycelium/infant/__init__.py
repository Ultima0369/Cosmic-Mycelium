"""
Infant layer — Single-node "silicon baby" implementation.
Six-layer fractal architecture contained within one process.
"""

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.infant.hic import HIC, BreathState
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

__all__ = [
    "SiliconInfant",
    "HIC",
    "BreathState",
    "SympNetEngine",
]
