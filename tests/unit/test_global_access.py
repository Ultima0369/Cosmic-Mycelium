"""
Unit Tests: global.access_protocol — Global Access Protocol
Tests for node admission control at civilization scale.
"""

from __future__ import annotations

import importlib
import pytest


def _import_global_module():
    """Dynamic import to avoid 'global' keyword in module path."""
    return importlib.import_module('cosmic_mycelium.global.access_protocol')


class TestGlobalAccessProtocol:
    """Admission control tests."""

    def setup_method(self):
        """Each test gets fresh protocol."""
        mod = _import_global_module()
        self.GlobalAccessProtocol = mod.GlobalAccessProtocol
        self.NodeMetadata = mod.NodeMetadata
        self.protocol = self.GlobalAccessProtocol()

    def test_valid_fingerprint_format_hex_only(self):
        """16-character hex fingerprint passes."""
        node = self.NodeMetadata(
            node_id="node-1",
            fingerprint="a1b2c3d4e5f6a7b8",  # valid 16-char hex
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is True

    def test_fingerprint_too_short_rejected(self):
        """Fingerprint with < 16 chars rejected."""
        node = self.NodeMetadata(
            node_id="node-2",
            fingerprint="abc123",  # too short
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is False

    def test_fingerprint_too_long_rejected(self):
        """Fingerprint with > 16 chars rejected."""
        node = self.NodeMetadata(
            node_id="node-3",
            fingerprint="a1b2c3d4e5f6a7b8c9d0e1f2",  # 24 chars
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is False

    def test_fingerprint_non_hex_rejected(self):
        """Fingerprint with non-hex characters rejected."""
        node = self.NodeMetadata(
            node_id="node-4",
            fingerprint="xyz1234567890abc!",  # '!' not hex
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is False

    def test_fingerprint_uppercase_hex_accepted(self):
        """Uppercase hex characters are accepted (case-insensitive check)."""
        node = self.NodeMetadata(
            node_id="node-5",
            fingerprint="ABCDEF0123456789",
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is True

    def test_energy_threshold_enforced(self):
        """Energy must be >= 20 to join."""
        node = self.NodeMetadata(
            node_id="node-6",
            fingerprint="a1b2c3d4e5f6a7b8",
            hic_snapshot={"energy": 19.0},  # below threshold
            capabilities=["sensing"],
        )
        assert self.protocol.can_join(node) is False

        node.hic_snapshot["energy"] = 20.0  # exactly at threshold
        assert self.protocol.can_join(node) is True

    def test_capabilities_required(self):
        """Node must declare at least one capability."""
        node = self.NodeMetadata(
            node_id="node-7",
            fingerprint="a1b2c3d4e5f6a7b8",
            hic_snapshot={"energy": 50.0},
            capabilities=[],  # empty
        )
        assert self.protocol.can_join(node) is False

        node.capabilities = ["compute"]
        assert self.protocol.can_join(node) is True

    def test_admit_adds_to_registry(self):
        """Successful admit() adds node to admitted dict."""
        node = self.NodeMetadata(
            node_id="node-admit-1",
            fingerprint="a1b2c3d4e5f6a7b8",
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        result = self.protocol.admit(node)
        assert result is True
        assert self.protocol.is_admitted("node-admit-1")
        assert self.protocol.admitted["node-admit-1"] is node

    def test_admit_rejects_invalid_node(self):
        """admit() returns False for invalid node, does not add."""
        node = self.NodeMetadata(
            node_id="node-bad",
            fingerprint="invalid!",
            hic_snapshot={"energy": 10.0},
            capabilities=[],
        )
        result = self.protocol.admit(node)
        assert result is False
        assert not self.protocol.is_admitted("node-bad")

    def test_is_admitted_tracks_known_nodes(self):
        """is_admitted returns True only for admitted node IDs."""
        assert not self.protocol.is_admitted("unknown")
        node = self.NodeMetadata(
            node_id="node-known",
            fingerprint="a1b2c3d4e5f6a7b8",
            hic_snapshot={"energy": 50.0},
            capabilities=["sensing"],
        )
        self.protocol.admit(node)
        assert self.protocol.is_admitted("node-known")
