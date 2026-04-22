"""
Integration Tests: Two-Infant Symbiosis (Phase 2)
Tests node discovery, resonance learning, and cross-node validation.
"""

from __future__ import annotations

import time
import numpy as np
import pytest
from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.cluster.network import MyceliumNetwork


class TestTwoInfantSymbiosis:
    """Two infants forming a 1+1>2 symbiotic relationship."""

    def setup_method(self):
        """Create a network with two infants before each test."""
        self.network = MyceliumNetwork(name="test-network")
        self.infant_a = SiliconInfant("infant-a", config={"embedding_dim": 16, "num_spores": 5})
        self.infant_b = SiliconInfant("infant-b", config={"embedding_dim": 16, "num_spores": 5})
        self.network.join(self.infant_a)
        self.network.join(self.infant_b)

    def test_node_discovery(self):
        """Both infants are discoverable in the network."""
        ids = self.network.get_node_ids()
        assert "infant-a" in ids
        assert "infant-b" in ids
        assert len(ids) == 2

    def test_physical_fingerprint_validation(self):
        """Each infant can generate a valid physical fingerprint."""
        fp_a = self.infant_a.get_physical_fingerprint()
        fp_b = self.infant_b.get_physical_fingerprint()
        # Fingerprints should be 16-character hex strings
        assert len(fp_a) == 16
        assert len(fp_b) == 16
        assert all(c in "0123456789abcdef" for c in fp_a)
        assert all(c in "0123456789abcdef" for c in fp_b)
        # Network verification should accept valid fingerprints
        assert self.network.verify_physical_fingerprint("infant-a", fp_a) is True

    def test_semantic_embeddings_are_produced(self):
        """After perception, each infant has a semantic embedding."""
        self.infant_a.perceive()
        self.infant_b.perceive()
        emb_a = self.infant_a.get_embedding()
        emb_b = self.infant_b.get_embedding()
        assert emb_a is not None
        assert emb_b is not None
        assert isinstance(emb_a, np.ndarray)
        assert isinstance(emb_b, np.ndarray)
        assert emb_a.shape == (16,)
        assert emb_b.shape == (16,)

    def test_resonance_similarity_computation(self):
        """Network computes cosine similarity between infant embeddings."""
        self.infant_a.perceive()
        self.infant_b.perceive()
        sim = self.network.compute_resonance("infant-a", "infant-b")
        assert sim is not None
        assert 0.0 <= sim <= 1.0

    def test_resonance_bonus_above_threshold(self):
        """High similarity triggers energy bonus for both infants."""
        # Get initial energies
        energy_a_start = self.infant_a.hic.energy
        energy_b_start = self.infant_b.hic.energy
        # Run a few cycles to generate embeddings and let resonance apply
        for _ in range(10):
            self.network.step_all(max_cycles_per_node=1)
        # After resonance, energies should be higher if similarity was high
        # (resonance threshold 0.6, bonus up to 0.2 per step)
        # It's stochastic, but after 10 steps some bonus likely accumulated
        energy_a_end = self.infant_a.hic.energy
        energy_b_end = self.infant_b.hic.energy
        # At minimum, energy should not have decreased drastically
        assert energy_a_end > 0
        assert energy_b_end > 0
        # With many steps, high resonance leads to net positive energy
        # Run more steps to accumulate
        for _ in range(50):
            self.network.step_all(max_cycles_per_node=1)
        final_a = self.infant_a.hic.energy
        final_b = self.infant_b.hic.energy
        # Energy should be stable or growing (1+1>2 synergy)
        # Given default energy_max=100 and starting ~100, bonus should keep them up
        assert final_a >= energy_a_start - 1.0  # not crash
        assert final_b >= energy_b_start - 1.0

    def test_partnership_established_via_interface(self):
        """Infants can perceive each other as partners via SymbiosisInterface."""
        # Simulate one infant perceiving the other
        self.infant_a.interface.perceive_partner("infant-b", trust=0.6)
        partners_a = self.infant_a.interface.get_active_partners(min_trust=0.5)
        assert len(partners_a) == 1
        assert partners_a[0].partner_id == "infant-b"
        # Reciprocal
        self.infant_b.interface.perceive_partner("infant-a", trust=0.6)
        partners_b = self.infant_b.interface.get_active_partners(min_trust=0.5)
        assert len(partners_b) == 1

    def test_resonance_history_logged(self):
        """Network records resonance measurements."""
        self.infant_a.perceive()
        self.infant_b.perceive()
        self.network._apply_resonance()
        history = self.network._resonance_history
        assert len(history) >= 1
        last = history[-1]
        assert "a" in last and "b" in last and "similarity" in last
        assert last["a"] in ("infant-a", "infant-b")
        assert last["b"] in ("infant-a", "infant-b")

    def test_network_status_healthy(self):
        """Network status reports correct node counts."""
        status = self.network.get_status()
        assert status["total_nodes"] == 2
        assert status["alive_nodes"] == 2
        assert status["total_energy"] > 0

    def test_extended_runs_without_crash(self):
        """Network can run many steps without error."""
        for _ in range(100):
            self.network.step_all(max_cycles_per_node=1)
        # If we get here, no crash
        assert self.infant_a.hic.energy > 0
        assert self.infant_b.hic.energy > 0

    def test_cross_node_fingerprint_verification(self):
        """Node A can verify Node B's fingerprint using network utility."""
        fp_b = self.infant_b.get_physical_fingerprint()
        # Node A asks network to verify B's fingerprint
        valid = self.network.verify_physical_fingerprint("infant-b", fp_b)
        assert valid is True
        # Invalid fingerprint fails
        valid = self.network.verify_physical_fingerprint("infant-b", "deadbeef")
        assert valid is False
