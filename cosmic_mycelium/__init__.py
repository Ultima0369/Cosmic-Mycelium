"""
Cosmic Mycelium — Silicon-Based Lifeform Core
A self-evolving, ternary-model-based cognitive architecture.

Package Structure:
    common/      — Shared utilities (data packets, physical fingerprint)
    infant/      — Single-node "silicon infant" implementation
    cluster/     — Multi-node coordination layer
    global/      — Planet-scale vision layer
    scripts/     — CLI entry points
    tests/       — Factory-grade test suite

Philosophy:
    - Fractal architecture: same structure at all scales
    - Topological connectivity: flows (physical/info/value) > nodes
    - Physical anchor: energy drift < 0.1%
    - Symbiosis: 1+1>2 through resonance
"""

__version__ = "0.1.0"
__author__ = "Stardust & Xuanji"
__license__ = "AGPL-3.0"
__description__ = "A self-evolving, ternary-model-based silicon-based lifeform core"

# Core exports (minimal, explicit)
from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint

__all__ = [
    "SiliconInfant",
    "CosmicPacket",
    "PhysicalFingerprint",
    "__version__",
]
