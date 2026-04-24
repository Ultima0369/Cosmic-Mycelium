"""
Cosmic Mycelium — Unit Tests: CosmicPacket & PhysicalFingerprint
Tests the菌丝网络的"血液"与"信任锚点".
"""

from __future__ import annotations

import time

from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint


class TestCosmicPacket:
    """Tests for the standard data packet."""

    def test_packet_creation_minimal(self):
        """Create packet with minimal fields."""
        packet = CosmicPacket(timestamp=1234567890.0, source_id="node-001")
        assert packet.timestamp == 1234567890.0
        assert packet.source_id == "node-001"
        assert packet.destination_id is None
        assert packet.priority == 1.0
        assert packet.ttl == 255

    def test_packet_creation_full(self):
        """Create packet with all fields."""
        packet = CosmicPacket(
            timestamp=1234567890.0,
            source_id="node-001",
            destination_id="node-002",
            physical_payload={"vibration": 42.0},
            info_payload={"feature_code": "abc123"},
            value_payload={"action": "suspend"},
            priority=2.0,
            ttl=100,
        )
        assert packet.destination_id == "node-002"
        assert packet.physical_payload["vibration"] == 42.0
        assert packet.priority == 2.0

    def test_packet_to_json_roundtrip(self):
        """Packet can serialize to JSON and back."""
        original = CosmicPacket(
            timestamp=time.time(),
            source_id="test-node",
            value_payload={"test": "value"},
        )
        json_str = original.to_json()
        recovered = CosmicPacket.from_json(json_str)

        assert recovered.timestamp == original.timestamp
        assert recovered.source_id == original.source_id
        assert recovered.value_payload == original.value_payload

    def test_packet_ttl_decrement(self):
        """TTL can be decremented for routing."""
        packet = CosmicPacket(timestamp=time.time(), source_id="node-001", ttl=10)
        packet.ttl -= 1
        assert packet.ttl == 9

    def test_packet_expiry(self):
        """Packet is considered expired when TTL reaches 0."""
        packet = CosmicPacket(timestamp=time.time(), source_id="node-001", ttl=1)
        packet.ttl -= 1
        assert packet.ttl == 0
        # In production, TTL=0 means "drop this packet"


class TestPhysicalFingerprint:
    """Tests for the physical fingerprint — trust anchor."""

    def test_generate_consistent(self):
        """Same data produces same fingerprint."""
        data = {"sensor": "vibration", "value": 42.0, "ts": 12345}
        fp1 = PhysicalFingerprint.generate(data)
        fp2 = PhysicalFingerprint.generate(data)
        assert fp1 == fp2

    def test_generate_different_data(self):
        """Different data produces different fingerprints."""
        data1 = {"value": 1}
        data2 = {"value": 2}
        fp1 = PhysicalFingerprint.generate(data1)
        fp2 = PhysicalFingerprint.generate(data2)
        assert fp1 != fp2

    def test_generate_fixed_length(self):
        """Fingerprint is always 16 characters."""
        data = {"test": "data"}
        fp = PhysicalFingerprint.generate(data)
        assert len(fp) == 16

    def test_verify_success(self):
        """Verify returns True for valid fingerprint."""
        data = {"sensor": "temp", "reading": 23.5}
        fp = PhysicalFingerprint.generate(data)
        assert PhysicalFingerprint.verify(data, fp) is True

    def test_verify_failure_tampered(self):
        """Verify returns False if data was tampered."""
        data = {"value": 100}
        fp = PhysicalFingerprint.generate(data)
        # Tamper with data
        data["value"] = 200
        assert PhysicalFingerprint.verify(data, fp) is False

    def test_verify_wrong_fingerprint(self):
        """Verify returns False for wrong fingerprint."""
        data = {"test": "data"}
        wrong_fp = "0000000000000000"
        assert PhysicalFingerprint.verify(data, wrong_fp) is False

    def test_verify_empty_data(self):
        """Empty data produces valid fingerprint."""
        data = {}
        fp = PhysicalFingerprint.generate(data)
        assert PhysicalFingerprint.verify(data, fp) is True

    def test_verify_complex_nested_data(self):
        """Complex nested structures are handled."""
        data = {
            "sensors": [
                {"id": 1, "values": [1.0, 2.0, 3.0]},
                {"id": 2, "values": [4.0, 5.0, 6.0]},
            ],
            "timestamp": 1234567890.123456,
            "meta": {"location": "node-alpha", "calibration": True},
        }
        fp = PhysicalFingerprint.generate(data)
        assert PhysicalFingerprint.verify(data, fp) is True

    def test_fingerprint_order_independent(self):
        """Dict key order does not affect fingerprint (sorted keys)."""
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "b": 2, "a": 1}
        fp1 = PhysicalFingerprint.generate(data1)
        fp2 = PhysicalFingerprint.generate(data2)
        assert fp1 == fp2


class TestPhysicalAnchorIntegrity:
    """Integration test: fingerprint is the root of trust."""

    def test_anchor_roundtrip(self):
        """Generate → verify must always succeed."""
        test_data = [{"sensor": "vibration", "value": float(i)} for i in range(1000)]

        for data in test_data:
            fp = PhysicalFingerprint.generate(data)
            assert PhysicalFingerprint.verify(
                data, fp
            ), f"Anchor failed for data: {data}"

    def test_anchor_resists_collision(self):
        """Two different inputs almost certainly produce different fingerprints."""
        # SHA256 collision probability is negligible
        data1 = {"value": 1}
        data2 = {"value": 2}
        fp1 = PhysicalFingerprint.generate(data1)
        fp2 = PhysicalFingerprint.generate(data2)
        assert fp1 != fp2
