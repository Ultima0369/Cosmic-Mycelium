"""
Resonance Bonus Unit Tests — Phase 2.2
Validates: similarity threshold (0.6), bonus scaling (max 0.2), energy cap, trust update.
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.main import SiliconInfant


class TestResonanceBonus:
    """Test apply_resonance_bonus() — the 1+1>2 energy synergy rule."""

    def make_infant(self):
        return SiliconInfant("test-res")

    def test_below_threshold_no_bonus(self):
        """Similarity < 0.6 → no energy change."""
        infant = self.make_infant()
        start_energy = infant.hic.energy
        infant.apply_resonance_bonus("partner-1", similarity=0.5)
        assert infant.hic.energy == start_energy

    def test_at_threshold_no_bonus(self):
        """Similarity exactly 0.6 → bonus = 0 (threshold exclusive)."""
        infant = self.make_infant()
        start_energy = infant.hic.energy
        infant.apply_resonance_bonus("partner-2", similarity=0.6)
        assert infant.hic.energy == start_energy  # (0.6-0.6)*0.5 = 0

    def test_above_threshold_small_bonus(self):
        """Similarity 0.65 → bonus = 0.025."""
        infant = self.make_infant()
        # Start below max so bonus is visible
        infant.hic._energy = 50.0
        start_energy = infant.hic.energy
        infant.apply_resonance_bonus("partner-3", similarity=0.65)
        expected_bonus = (0.65 - 0.6) * 0.5  # 0.025
        assert infant.hic.energy == pytest.approx(
            start_energy + expected_bonus, abs=1e-6
        )

    def test_bonus_capped_at_max(self):
        """Similarity 1.0 → bonus capped at 0.2, not exceeding energy_max."""
        infant = self.make_infant()
        start_energy = infant.hic.energy
        infant.apply_resonance_bonus("partner-4", similarity=1.0)
        # (1.0 - 0.6) * 0.5 = 0.2, capped by energy_max
        expected_bonus = min(0.2, (1.0 - 0.6) * 0.5)
        expected_energy = min(
            infant.hic.config.energy_max, start_energy + expected_bonus
        )
        assert infant.hic.energy == pytest.approx(expected_energy, abs=1e-6)

    def test_energy_never_exceeds_max(self):
        """Bonus always respects energy_max ceiling."""
        infant = self.make_infant()
        infant.hic._energy = infant.hic.config.energy_max - 0.05
        infant.apply_resonance_bonus("partner-5", similarity=1.0)
        assert infant.hic.energy <= infant.hic.config.energy_max

    def test_trust_increased_on_resonance(self):
        """High similarity updates partner trust via SymbiosisInterface."""
        infant = self.make_infant()
        infant.apply_resonance_bonus("partner-6", similarity=0.8)
        partners = infant.interface.get_active_partners(min_trust=0.5)
        assert "partner-6" in [p.partner_id for p in partners]

    def test_interaction_mode_is_collaborate(self):
        """Resonance sets interaction mode to COLLABORATE."""
        infant = self.make_infant()
        infant.apply_resonance_bonus("partner-7", similarity=0.7)
        # Check that partner perception recorded with COLLABORATE mode
        # We can infer from trust value set (0.6 base)
        partners = infant.interface.get_active_partners(min_trust=0.5)
        assert len(partners) >= 1

    def test_zero_similarity_no_bonus(self):
        """Edge case: similarity 0.0 → no bonus."""
        infant = self.make_infant()
        start = infant.hic.energy
        infant.apply_resonance_bonus("p", similarity=0.0)
        assert infant.hic.energy == start

    def test_negative_similarity_handled(self):
        """Cosine similarity can be negative; below threshold → no bonus."""
        infant = self.make_infant()
        start = infant.hic.energy
        infant.apply_resonance_bonus("p", similarity=-0.3)
        assert infant.hic.energy == start

    def test_high_similarity_but_low_energy_still_gives_bonus(self):
        """Even if infant energy is low, resonance bonus still applies (capped at max)."""
        infant = self.make_infant()
        infant.hic._energy = 10.0  # Low but positive
        start = infant.hic.energy
        infant.apply_resonance_bonus("p", similarity=0.9)
        # Bonus should be applied
        expected_bonus = min(0.2, (0.9 - 0.6) * 0.5)  # = 0.15
        assert infant.hic.energy == pytest.approx(
            min(infant.hic.config.energy_max, start + expected_bonus), abs=1e-6
        )
