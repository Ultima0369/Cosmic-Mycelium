"""
CosmicPacket — The Standard Data Packet
The "blood cell" of the mycelium network.
Flows through physical, info, and value channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import json
import time


@dataclass
class CosmicPacket:
    """
    Standard data packet flowing through the mycelium network.

    Three payload channels:
      - physical_payload: vibration, frequency, physical fingerprint
      - info_payload: feature codes, causal gradients, exploration paths
      - value_payload: proposals, suspend requests, consensus

    Attributes:
        timestamp: Unix epoch time (physical time anchor)
        source_id: Origin node ID
        destination_id: Target node ID (None = broadcast)
        priority: Compute priority (higher = more urgent)
        ttl: Time-to-live (prevents infinite circulation)
    """

    timestamp: float = field(default_factory=time.time)
    source_id: str = ""
    destination_id: Optional[str] = None

    # Three flow channels
    physical_payload: Optional[Dict[str, Any]] = None
    info_payload: Optional[Dict[str, Any]] = None
    value_payload: Optional[Dict[str, Any]] = None

    # Metadata
    priority: float = 1.0
    ttl: int = 255

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "CosmicPacket":
        """
        Deserialize from JSON.

        Validates that required fields are present. Missing required fields
        (timestamp, source_id) raise KeyError with a clear message rather
        than failing later with an AttributeError.
        """
        data = json.loads(json_str)
        required = {"timestamp", "source_id"}
        missing = required - data.keys()
        if missing:
            raise KeyError(f"Missing required fields in CosmicPacket JSON: {missing}")
        return cls(**data)

    def decrement_ttl(self) -> bool:
        """
        Decrement TTL. Returns False if expired.
        """
        self.ttl -= 1
        return self.ttl > 0

    def is_broadcast(self) -> bool:
        """Is this packet broadcast to all?"""
        return self.destination_id is None

    def get_flow_type(self) -> str:
        """Determine primary flow type from payload."""
        if self.physical_payload is not None:
            return "physical"
        if self.info_payload is not None:
            return "info"
        if self.value_payload is not None:
            return "value"
        return "unknown"
