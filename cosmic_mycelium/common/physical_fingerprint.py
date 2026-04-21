"""
PhysicalFingerprint — Trust Anchor
Trust is not derived from authority; it's derived from physical fact.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Any, Tuple


class PhysicalFingerprint:
    """
    Generates and verifies physical fingerprints.

    A fingerprint is a deterministic hash of data, serving as a
    "physical anchor" — proof that something existed at a specific
    state. This is the foundation of trust in the mycelium network.
    """

    @staticmethod
    def generate(data: Dict[str, Any]) -> str:
        """
        Generate a fingerprint from data.

        SHA-256 → first 16 hex chars = collision-resistant for our scale.
        """
        data_str = json.dumps(data, sort_keys=True, default=str)
        full_hash = hashlib.sha256(data_str.encode()).hexdigest()
        return full_hash[:16]

    @staticmethod
    def verify(data: Dict[str, Any], fingerprint: str) -> bool:
        """
        Verify data matches fingerprint.
        Returns True if fingerprint is valid for this data.
        """
        return PhysicalFingerprint.generate(data) == fingerprint

    @staticmethod
    def fingerprint_pair(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[str, str]:
        """
        Generate fingerprints for a pair of data items.
        Useful for verifying two parties have the same physical fact.
        """
        return (
            PhysicalFingerprint.generate(a),
            PhysicalFingerprint.generate(b),
        )

    @staticmethod
    def fingerprints_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """
        Check if two data items have the same fingerprint.
        """
        fp_a = PhysicalFingerprint.generate(a)
        fp_b = PhysicalFingerprint.generate(b)
        return fp_a == fp_b
