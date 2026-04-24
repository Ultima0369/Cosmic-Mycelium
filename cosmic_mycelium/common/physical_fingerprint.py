"""
PhysicalFingerprint — Trust Anchor
Trust is not derived from authority; it's derived from physical fact.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class PhysicalFingerprint:
    """
    Generates and verifies physical fingerprints.

    A fingerprint is a deterministic hash of data, serving as a
    "physical anchor" — proof that something existed at a specific
    state. This is the foundation of trust in the mycelium network.
    """

    @staticmethod
    def generate(data: dict[str, Any]) -> str:
        """
        Generate a fingerprint from data.

        SHA-256 → first 16 hex chars = collision-resistant for our scale.
        """
        data_str = json.dumps(data, sort_keys=True, default=str)
        full_hash = hashlib.sha256(data_str.encode()).hexdigest()
        return full_hash[:16]

    @staticmethod
    def verify(data: dict[str, Any], fingerprint: str) -> bool:
        """
        Verify data matches fingerprint.
        Returns True if fingerprint is valid for this data.
        """
        return PhysicalFingerprint.generate(data) == fingerprint

    @staticmethod
    def fingerprint_pair(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str]:
        """
        Generate fingerprints for a pair of data items.
        Useful for verifying two parties have the same physical fact.
        """
        return (
            PhysicalFingerprint.generate(a),
            PhysicalFingerprint.generate(b),
        )

    @staticmethod
    def fingerprints_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
        """
        Check if two data items have the same fingerprint.
        """
        fp_a = PhysicalFingerprint.generate(a)
        fp_b = PhysicalFingerprint.generate(b)
        return fp_a == fp_b
