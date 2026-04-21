"""
Global Access Protocol — Planet-Scale Node Admission
Handles node authentication and network admission at civilization scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint


@dataclass
class GlobalRhythm:
    """Civilization-scale rhythm pattern."""
    name: str
    frequency: float
    amplitude: float
    phase: float = 0.0


@dataclass
class NodeMetadata:
    """Metadata for a joining node."""
    node_id: str
    fingerprint: str
    hic_snapshot: Dict
    capabilities: List[str]


class GlobalAccessProtocol:
    """
    Global layer: admission control for planet-scale mycelium.

    Principles:
      1. Physical fingerprint is the root of trust
      2. HIC energy must be > 20 (not in suspend)
      3. Node must demonstrate capability to contribute
    """

    def __init__(self):
        self.admitted: Dict[str, NodeMetadata] = {}
        self.fp_verifier = PhysicalFingerprint()

    def can_join(self, node: NodeMetadata) -> bool:
        """Check if node meets admission criteria."""
        # 1. Fingerprint must be valid format
        if len(node.fingerprint) != 16:
            return False
        # 2. Energy check
        if node.hic_snapshot.get("energy", 0) < 20:
            return False
        # 3. Must have at least one capability
        if not node.capabilities:
            return False
        return True

    def admit(self, node: NodeMetadata) -> bool:
        """Admit node to global network."""
        if self.can_join(node):
            self.admitted[node.node_id] = node
            return True
        return False

    def is_admitted(self, node_id: str) -> bool:
        """Check if node is admitted."""
        return node_id in self.admitted
