"""
Unit tests for Phase 5.4 Skill Abstractor — macro-action discovery from action-delta patterns.

TDD coverage:
- Bigram pattern detection and macro creation
- Trigram pattern detection
- Min support threshold respected
- Combined delta is sum of component deltas
- Mine is idempotent (no duplicate macros)
- Macro signature format
- Max n-gram limit enforced
- Window size enforces sliding history
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.core.skill_abstractor import SkillAbstractor, MacroDefinition


@pytest.fixture
def abstractor():
    """SkillAbstractor with small thresholds and large window for most tests."""
    return SkillAbstractor(min_support=3, max_ngram=3, window_size=100)


def record_sequence(abstractor: SkillAbstractor, actions: list[str], deltas: list[dict]):
    """Helper: record a sequence of (action, delta)."""
    for a, d in zip(actions, deltas):
        abstractor.record(a, d)


class TestSkillAbstractor:
    """Phase 5.4: Skill abstraction via n-gram mining."""

    def test_bigram_creates_macro(self, abstractor):
        """Repeated bigram (A,B) yields a macro with combined delta."""
        actions = ["A", "B"] * 5  # 10 actions: A,B,A,B,...
        deltas = [{"vib": 1.0}, {"vib": 2.0}] * 5
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()

        # Due to overlapping, both (A,B) and (B,A) may appear; check the desired one.
        ab_macros = [m for m in macros if m.sequence == ("A", "B")]
        assert len(ab_macros) == 1
        macro = ab_macros[0]
        # (A,B) appears 5 times in alternating sequence of length 10
        assert macro.support == 5
        assert pytest.approx(macro.avg_delta["vib"]) == 3.0  # 1+2

    def test_trigram_creates_macro(self, abstractor):
        """Repeated trigram (X,Y,Z) detected."""
        actions = ["X", "Y", "Z"] * 4  # 12 actions: X,Y,Z,X,Y,Z,...
        deltas = [{"vib": i} for i in [1, 2, 3]] * 4
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()

        # Overlapping trigrams: (X,Y,Z) appears 4 times, (Y,Z,X) appears 3? Actually sequence: X,Y,Z,X,Y,Z,... trigrams at i=0: X,Y,Z; i=1: Y,Z,X; i=2: Z,X,Y; i=3: X,Y,Z; etc. So (X,Y,Z) appears 4 times (i=0,3,6,9), (Y,Z,X) appears 3, (Z,X,Y) appears 3.
        xyz_macros = [m for m in macros if m.sequence == ("X", "Y", "Z")]
        assert len(xyz_macros) == 1
        macro = xyz_macros[0]
        assert macro.support == 4
        assert pytest.approx(macro.avg_delta["vib"]) == 6.0  # 1+2+3

    def test_min_support_threshold(self, abstractor):
        """Patterns below min_support do not create macros."""
        # Only 2 repetitions of bigram (threshold 3)
        actions = ["A", "B"] * 2
        deltas = [{"vib": 1.0}, {"vib": 2.0}] * 2
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()

        assert macros == []

    def test_combined_delta_sums_component_deltas(self, abstractor):
        """Macro avg_delta equals sum of avg_deltas of its steps."""
        # Two different bigrams: (A,B) and (B,C). Only (A,B) repeats.
        actions = ["A", "B", "B", "C", "A", "B"] * 3
        # deltas: A:1, B:2, B:2, C:3
        deltas = (
            [{"vib": 1.0}, {"vib": 2.0}]
            + [{"vib": 2.0}, {"vib": 3.0}]
            + [{"vib": 1.0}, {"vib": 2.0}]
        ) * 3
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()
        # Should have macro (A,B) with 3 support, combined = 3.0
        # Also maybe (B,C) appears 3 times? Let's see: pattern B,C appears at positions 2,5,... Actually sequence: A B B C A B repeated. The bigrams: (A,B), (B,B), (B,C), (C,A), (A,B) repeated. (A,B) appears 3 times; (B,B) appears 3? Actually each cycle has A B B C A B; bigrams: A->B, B->B, B->C, C->A, A->B. So A->B appears 2 per cycle? Wait A appears twice in cycle? Actually sequence length 6; bigrams: positions 0-1: (A,B); 1-2: (B,B); 2-3: (B,C); 3-4: (C,A); 4-5: (A,B). So (A,B) appears twice per cycle => total 6? Actually 3 cycles => (A,B) count = 2*3 = 6. (B,B)=3, (B,C)=3, (C,A)=3. Many meet threshold 3. So we'll get multiple macros. For simplicity, just assert (A,B) exists with correct sum.
        ab_macro = next(m for m in macros if m.sequence == ("A", "B"))
        assert pytest.approx(ab_macro.avg_delta["vib"]) == 3.0  # 1+2

    def test_mine_idempotent(self, abstractor):
        """Calling mine multiple times without new data returns no new macros."""
        actions = ["X", "Y"] * 5
        deltas = [{"v": 1.0}, {"v": 1.0}] * 5
        record_sequence(abstractor, actions, deltas)

        first = abstractor.mine()
        second = abstractor.mine()
        # Should discover at least the desired bigram (X,Y) and possibly (Y,X)
        assert any(m.sequence == ("X", "Y") for m in first)
        # No new macros after second call
        assert second == []

    def test_multiple_distinct_patterns(self, abstractor):
        """Different repeated patterns each become separate macros."""
        # Sequence: A B C D A B C D A B C D C D
        actions = ["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "C", "D"]
        # deltas: A:1, B:2, C:3, D:4 repeated, plus final C,D
        deltas = (
            [{"v": 1.0}, {"v": 2.0}, {"v": 3.0}, {"v": 4.0}]
            * 3  # first 12 entries
            + [{"v": 3.0}, {"v": 4.0}]  # final C,D
        )
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()
        sigs = {m.sequence for m in macros}

        # Expected bigrams present
        assert ("A", "B") in sigs
        assert ("C", "D") in sigs
        ab = next(m for m in macros if m.sequence == ("A", "B"))
        cd = next(m for m in macros if m.sequence == ("C", "D"))
        assert ab.support == 3
        assert cd.support == 4
        assert pytest.approx(ab.avg_delta["v"]) == 3.0  # 1+2
        assert pytest.approx(cd.avg_delta["v"]) == 7.0  # 3+4

    def test_max_ngram_limit(self, abstractor):
        """Only n-grams up to max_ngram are considered."""
        abstractor.max_ngram = 3
        actions = ["W", "X", "Y", "Z"] * 5  # 20 actions, creates 4-grams as well
        deltas = [{"v": float(i)} for i in range(4)] * 5
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()

        # Ensure no macro has sequence length > 3
        assert all(len(m.sequence) <= 3 for m in macros)
        # But trigrams should be present, e.g., (W,X,Y) or (X,Y,Z)
        seqs = [m.sequence for m in macros if len(m.sequence) == 3]
        assert len(seqs) > 0
        # Check that a known trigram exists (depends on overlap)
        # With sequence W,X,Y,Z,W,X,Y,Z,... trigrams: (W,X,Y), (X,Y,Z), (Y,Z,W), (Z,W,X), ...
        assert any(s == ("W", "X", "Y") or s == ("X", "Y", "Z") for s in seqs)

    def test_window_size_limits_history(self):
        """History deque respects window_size; old patterns drop out."""
        # Use a small window to test eviction
        abstractor = SkillAbstractor(min_support=3, max_ngram=3, window_size=10)
        # Fill beyond window (20 entries)
        actions = ["A", "B"] * 10  # 20 entries
        deltas = [{"v": 1.0}, {"v": 2.0}] * 10
        record_sequence(abstractor, actions, deltas)
        # Window holds last 10 entries: A,B,A,B,A,B,A,B,A,B -> (A,B) appears 5 times.
        macros = abstractor.mine()
        ab_macros = [m for m in macros if m.sequence == ("A", "B")]
        assert len(ab_macros) == 1
        assert ab_macros[0].support == 5

    def test_different_sensors_summed(self, abstractor):
        """Multi-sensor deltas are summed independently."""
        actions = ["P", "Q"] * 4
        deltas = [
            {"vib": 1.0, "temp": 0.5},
            {"vib": 2.0, "temp": 1.5},
        ] * 4
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()
        m = macros[0]
        assert pytest.approx(m.avg_delta["vib"]) == 3.0
        assert pytest.approx(m.avg_delta["temp"]) == 2.0

    def test_macro_signature_format(self, abstractor):
        """Macro signature is a deterministic string."""
        actions = ["alpha", "beta"] * 5
        deltas = [{"x": 1.0}, {"x": 2.0}] * 5
        record_sequence(abstractor, actions, deltas)

        macros = abstractor.mine()
        sig = macros[0].signature
        # Should be something like "macro_alpha_beta" (order preserved)
        assert sig.startswith("macro_")
        assert "alpha" in sig and "beta" in sig
