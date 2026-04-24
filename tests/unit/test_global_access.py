"""
Unit Tests: global.access_protocol — Global Access Protocol
Tests for node admission control at civilization scale.
"""

from __future__ import annotations

import importlib
import time


def _import_global_module():
    """Dynamic import to avoid 'global' keyword in module path."""
    return importlib.import_module("cosmic_mycelium.global.access_protocol")


class TestNodeIDGeneration:
    """Tests for generate_node_id()."""

    def test_generate_node_id_format(self):
        """Node IDs follow prefix-timestamp-randomhex format."""
        mod = _import_global_module()
        node_id = mod.generate_node_id("node")
        assert node_id.startswith("node-")
        parts = node_id.split("-")
        assert len(parts) == 3
        assert parts[1].isdigit()
        assert len(parts[2]) == 8
        assert all(c in "0123456789abcdef" for c in parts[2])

    def test_generate_node_id_unique(self):
        """Multiple calls produce unique IDs."""
        mod = _import_global_module()
        ids = {mod.generate_node_id("test") for _ in range(100)}
        assert len(ids) == 100


class TestHICProof:
    """Tests for HICProof digest and structure."""

    def setup_method(self):
        mod = _import_global_module()
        self.HICProof = mod.HICProof

    def test_digest_deterministic(self):
        """Same snapshot produces same digest."""
        proof = self.HICProof(
            snapshot={"energy": 50.0, "state": "CONTRACT", "total_cycles": 100},
            signature="a" * 64,
            nonce=1,
        )
        assert proof.digest() == proof.digest()

    def test_digest_differs_with_energy(self):
        """Different energy yields different digest."""
        p1 = self.HICProof(
            snapshot={"energy": 50.0, "state": "CONTRACT", "total_cycles": 100},
            signature="a" * 64,
            nonce=1,
        )
        p2 = self.HICProof(
            snapshot={"energy": 51.0, "state": "CONTRACT", "total_cycles": 100},
            signature="a" * 64,
            nonce=1,
        )
        assert p1.digest() != p2.digest()

    def test_digest_differs_with_state(self):
        """Different state yields different digest."""
        p1 = self.HICProof(
            snapshot={"energy": 50.0, "state": "CONTRACT", "total_cycles": 100},
            signature="a" * 64,
            nonce=1,
        )
        p2 = self.HICProof(
            snapshot={"energy": 50.0, "state": "DIFFUSE", "total_cycles": 100},
            signature="a" * 64,
            nonce=1,
        )
        assert p1.digest() != p2.digest()


class TestReputationTracker:
    """Tests for ReputationRecord and ReputationTracker."""

    def setup_method(self):
        mod = _import_global_module()
        self.ReputationTracker = mod.ReputationTracker
        self.ReputationRecord = mod.ReputationRecord

    def test_record_starts_neutral(self):
        """New nodes start at score 50."""
        tracker = self.ReputationTracker()
        rec = tracker.ensure("node-x")
        assert rec.score == 50.0

    def test_success_increases_score(self):
        """Successful interactions boost reputation."""
        tracker = self.ReputationTracker()
        for _ in range(10):
            tracker.record_success("node-x")
        rec = tracker.get("node-x")
        assert rec.score == 55.0
        assert rec.successful_interactions == 10

    def test_score_capped_at_100(self):
        """Reputation score cannot exceed 100."""
        tracker = self.ReputationTracker()
        for _ in range(200):
            tracker.record_success("node-x")
        assert tracker.get("node-x").score == 100.0

    def test_failure_decreases_score(self):
        """Failures reduce reputation."""
        tracker = self.ReputationTracker()
        tracker.record_failure("node-x")
        rec = tracker.get("node-x")
        assert rec.score == 48.0
        assert rec.failed_interactions == 1

    def test_violation_severely_penalizes(self):
        """Violations cause major score drop."""
        tracker = self.ReputationTracker()
        tracker.record_violation("node-x")  # requires node_id
        rec = tracker.get("node-x")
        assert rec.score == 40.0
        assert rec.violations == 1

    def test_is_trusted_threshold(self):
        """is_trusted returns True only above threshold."""
        tracker = self.ReputationTracker()
        assert not tracker.is_trusted("node-x", threshold=60.0)
        tracker.record_success("node-x")  # 50.5
        assert not tracker.is_trusted("node-x", threshold=60.0)
        for _ in range(20):  # 50 + 20*0.5 = 60
            tracker.record_success("node-x")
        assert tracker.is_trusted("node-x", threshold=60.0)


class TestGlobalAccessProtocolProof:
    """Tests for proof-based admission (Phase 4.1)."""

    def setup_method(self):
        mod = _import_global_module()
        self.GlobalAccessProtocol = mod.GlobalAccessProtocol
        self.NodeIdentity = mod.NodeIdentity
        self.HICProof = mod.HICProof
        self.NodeMetadata = mod.NodeMetadata
        self.generate_node_id = mod.generate_node_id
        self.protocol = self.GlobalAccessProtocol()

    def _make_valid_proof(self, energy=50.0, state="CONTRACT", nonce=0):
        return self.HICProof(
            snapshot={
                "energy": energy,
                "state": state,
                "total_cycles": 100,
                "fp": "a1b2c3d4e5f6a7b8",
            },
            signature="s" * 64,
            timestamp=time.time(),
            nonce=nonce,
        )

    def test_verify_proof_public_valid(self):
        """Valid proof passes verification."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof()
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is True
        assert reason == "valid"

    def test_verify_proof_rejects_replay(self):
        """Reusing nonce is rejected."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof(nonce=42)
        self.protocol.verify_proof_public(identity, proof, node_id)  # first use
        valid2, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid2 is False
        assert "replay" in reason

    def test_verify_proof_rejects_low_energy(self):
        """Proof with energy < 20 is rejected."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof(energy=10.0)
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is False
        assert "energy-too-low" in reason

    def test_verify_proof_rejects_suspend_state(self):
        """Proof with SUSPEND state is rejected."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof(state="SUSPEND")
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is False
        assert "suspend" in reason.lower()

    def test_verify_proof_rejects_bad_signature_format(self):
        """Signature must be 64-char hex string."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof()
        proof.signature = "short"
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is False
        assert "signature" in reason

    def test_verify_proof_rejects_fingerprint_mismatch(self):
        """Snapshot fp must match identity fingerprint."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof()
        proof.snapshot["fp"] = "ffffffffffffffff"
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is False
        assert "fingerprint-mismatch" in reason

    def test_verify_proof_rejects_stale_timestamp(self):
        """Proof older than 5 minutes is rejected."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self._make_valid_proof()
        proof.timestamp = time.time() - 400
        valid, reason = self.protocol.verify_proof_public(identity, proof, node_id)
        assert valid is False
        assert "stale" in reason


class TestGlobalAccessProtocolAdmission:
    """Tests for admit() with proof-based admission."""

    def setup_method(self):
        mod = _import_global_module()
        self.GlobalAccessProtocol = mod.GlobalAccessProtocol
        self.NodeIdentity = mod.NodeIdentity
        self.HICProof = mod.HICProof
        self.NodeMetadata = mod.NodeMetadata
        self.generate_node_id = mod.generate_node_id
        self.protocol = self.GlobalAccessProtocol()

    def _make_node(self, node_id, energy=50.0, capabilities=None):
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self.HICProof(
            snapshot={
                "energy": energy,
                "state": "CONTRACT",
                "total_cycles": 100,
                "fp": "a1b2c3d4e5f6a7b8",
            },
            signature="s" * 64,
            timestamp=time.time(),
            nonce=0,
        )
        caps = capabilities if capabilities is not None else ["sensing"]
        return self.NodeMetadata(
            node_id=node_id,
            identity=identity,
            hic_proof=proof,
            capabilities=caps,
        )

    def test_admit_with_valid_proof(self):
        """Valid proof results in admission."""
        node_id = self.generate_node_id()
        node = self._make_node(node_id)
        success, reason = self.protocol.admit(node)
        assert success is True
        assert reason == "admitted"
        assert self.protocol.is_admitted(node_id)

    def test_admit_rejects_replay_proof(self):
        """Replayed proof rejected."""
        node_id = self.generate_node_id()
        node = self._make_node(node_id)
        self.protocol.admit(node)  # first admit
        success, reason = self.protocol.admit(node)  # second admit
        assert success is False
        assert "replay" in reason

    def test_admit_requires_capabilities(self):
        """Node must declare capabilities."""
        node_id = self.generate_node_id()
        node = self._make_node(node_id, capabilities=[])
        success, reason = self.protocol.admit(node)
        assert success is False
        assert "capabilities" in reason.lower()


class TestPublicVerificationEndpoint:
    """Tests for create_verification_response()."""

    def setup_method(self):
        mod = _import_global_module()
        self.GlobalAccessProtocol = mod.GlobalAccessProtocol
        self.HICProof = mod.HICProof
        self.NodeIdentity = mod.NodeIdentity
        self.NodeMetadata = mod.NodeMetadata
        self.generate_node_id = mod.generate_node_id
        self.protocol = self.GlobalAccessProtocol()

    def test_verification_response_for_admitted_node(self):
        """Returns full node metadata for admitted node."""
        node_id = self.generate_node_id()
        identity = self.NodeIdentity(
            node_id=node_id,
            public_key="p" * 64,
            fingerprint="a1b2c3d4e5f6a7b8",
        )
        proof = self.HICProof(
            snapshot={
                "energy": 75.0,
                "state": "CONTRACT",
                "total_cycles": 50,
                "fp": identity.fingerprint,
            },
            signature="s" * 64,
            timestamp=time.time(),
        )
        node = self.NodeMetadata(
            node_id=node_id,
            identity=identity,
            hic_proof=proof,
            capabilities=["sensing", "routing"],
        )
        ok, reason = self.protocol.admit(node)
        assert ok is True, f"admit failed: {reason}"
        resp = self.protocol.create_verification_response(node_id)
        assert resp["verified"] is True
        assert resp["node_id"] == node_id
        assert resp["fingerprint"] == "a1b2c3d4e5f6a7b8"
        assert resp["energy_at_admission"] == 75.0
        assert resp["capabilities"] == ["sensing", "routing"]
        assert resp["state"] == "CONTRACT"
        assert resp["reputation_score"] is not None

    def test_verification_response_unknown_node(self):
        """Unknown node returns not-verified."""
        resp = self.protocol.create_verification_response("unknown-node")
        assert resp["verified"] is False
        assert resp["reason"] == "node-not-found"
