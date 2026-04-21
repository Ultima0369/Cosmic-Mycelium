"""
Unit Tests: common.physical_fingerprint — Trust Anchor
Tests fingerprint generation and verification.
"""

from __future__ import annotations

import pytest
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint


class TestPhysicalFingerprint:
    """Tests for physical fingerprint generation and verification."""

    def test_generate_returns_16_char_string(self):
        """generate() returns a 16-character hex string."""
        data = {"sensor": "vibration", "value": 0.5}
        fp = PhysicalFingerprint.generate(data)
        assert isinstance(fp, str)
        assert len(fp) == 16
        # All characters should be hex
        assert all(c in "0123456789abcdef" for c in fp)

    def test_generate_is_deterministic(self):
        """Same data produces same fingerprint."""
        data = {"a": 1, "b": 2}
        fp1 = PhysicalFingerprint.generate(data)
        fp2 = PhysicalFingerprint.generate(data)
        assert fp1 == fp2

    def test_generate_is_sensitive_to_changes(self):
        """Different data produces different fingerprints."""
        fp1 = PhysicalFingerprint.generate({"x": 1})
        fp2 = PhysicalFingerprint.generate({"x": 2})
        assert fp1 != fp2

    def test_generate_handles_non_serializable_with_default_str(self):
        """Objects not JSON-serializable are converted via default=str."""
        # datetime objects, etc. should work via default=str
        import datetime
        data = {"timestamp": datetime.datetime(2026, 4, 22, 12, 0, 0)}
        fp = PhysicalFingerprint.generate(data)
        assert len(fp) == 16

    def test_verify_returns_true_for_valid_fingerprint(self):
        """verify() returns True when data matches fingerprint."""
        data = {"energy": 50.0, "state": "contract"}
        fp = PhysicalFingerprint.generate(data)
        assert PhysicalFingerprint.verify(data, fp) is True

    def test_verify_returns_false_for_invalid(self):
        """verify() returns False when data doesn't match fingerprint."""
        data1 = {"x": 1}
        data2 = {"x": 2}
        fp = PhysicalFingerprint.generate(data1)
        assert PhysicalFingerprint.verify(data2, fp) is False

    def test_fingerprint_pair_returns_two_fingerprints(self):
        """fingerprint_pair returns tuple of two 16-char strings."""
        a = {"sensor": "temp", "value": 25.0}
        b = {"sensor": "temp", "value": 25.0}
        fp_a, fp_b = PhysicalFingerprint.fingerprint_pair(a, b)
        assert len(fp_a) == 16
        assert len(fp_b) == 16

    def test_fingerprints_equal_for_identical_data(self):
        """fingerprints_equal returns True when data items have same fingerprint."""
        a = {"key": "value", "num": 42}
        b = {"key": "value", "num": 42}
        assert PhysicalFingerprint.fingerprints_equal(a, b) is True

    def test_fingerprints_not_equal_for_different_data(self):
        """fingerprints_equal returns False when fingerprints differ."""
        a = {"x": 1}
        b = {"x": 2}
        assert PhysicalFingerprint.fingerprints_equal(a, b) is False

    def test_fingerprint_order_does_not_matter_for_equality(self):
        """Dict key ordering does not affect fingerprint equality."""
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}  # Different insertion order
        # generate uses sort_keys=True, so they should be equal
        assert PhysicalFingerprint.fingerprints_equal(a, b) is True
